"""TCP socket client for communicating with the Blender addon."""

import hashlib
import hmac
import json
import logging
import os
import secrets
import select
import socket
import struct
import sys
import threading
import time
from typing import Any, NoReturn

logger = logging.getLogger(__name__)


ENV_TOKEN_FILE = "BLENDERWRIGHT_TOKEN_FILE"
ENV_PORT = "BLENDERWRIGHT_PORT"


class BlenderConnectionError(Exception):
    """Raised when connection to Blender fails."""
    pass


class BlenderAuthError(BlenderConnectionError):
    """The handshake or a signature failed, or there is no token to prove with."""


class _NotSent(Exception):
    """The request failed before it reached Blender, so it is safe to resend."""


def token_path(port: int = 9876) -> str:
    """Where the addon writes its auth token. Mirrors addon/auth.py."""
    override = os.environ.get(ENV_TOKEN_FILE)
    if override:
        return override
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    # One file per port so two Blenders cannot overwrite each other's token;
    # the default port keeps the plain name older setups know
    name = "token" if port == 9876 else f"token-{int(port)}"
    return os.path.join(base, "blenderwright", name)


def configured_port() -> int:
    """The Blender port this MCP server talks to: BLENDERWRIGHT_PORT, else 9876."""
    raw = os.environ.get(ENV_PORT)
    if raw is None:
        return 9876
    if not raw.strip().isdigit() or not 1024 <= int(raw) <= 65535:
        raise BlenderConnectionError(f"{ENV_PORT} must be a port from 1024 to 65535, "
                                     f"got {raw!r}")
    return int(raw)


def read_token(port: int = 9876) -> str:
    """Read the token the addon wrote when its server started on that port."""
    path = token_path(port)
    try:
        with open(path, encoding="utf-8") as f:
            token = f.read().strip()
    except FileNotFoundError:
        raise BlenderAuthError(
            f"No blenderwright auth token at {path}. Click Start Server in "
            f"Blender's blenderwright panel. If this MCP server runs somewhere "
            f"that can't see that file (WSL, Docker), set {ENV_TOKEN_FILE} to it."
        ) from None
    if not token:
        raise BlenderAuthError(f"The blenderwright auth token at {path} is empty.")
    return token


# Challenge-response handshake (protocol 2). Mirrored in addon/auth.py;
# tests/test_handshake.py keeps them equal.
PROTOCOL_VERSION = 2


def proof(token: str, role: str, first_nonce: str, second_nonce: str) -> str:
    """HMAC proving knowledge of the token, bound to both nonces and a role."""
    message = f"blenderwright-{role}|{first_nonce}|{second_nonce}".encode("utf-8")
    return hmac.new(token.encode("utf-8"), message, hashlib.sha256).hexdigest()


def session_key(token: str, client_nonce: str, server_nonce: str) -> bytes:
    """Per-connection key for signing commands and replies."""
    message = f"blenderwright-session|{client_nonce}|{server_nonce}".encode("utf-8")
    return hmac.new(token.encode("utf-8"), message, hashlib.sha256).digest()


def message_mac(key: bytes, direction: str, seq: int, body: dict) -> str:
    """Signature over one message body, its direction and its sequence number."""
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    message = f"{direction}|{seq}|".encode("utf-8") + canonical.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _is_unauthorized(response: Any) -> bool:
    return isinstance(response, dict) and response.get("code") == "unauthorized"


class BlenderConnection:
    """TCP socket client that connects to the Blender addon's socket server.

    Protocol: Each message is a 4-byte big-endian length prefix followed by
    a UTF-8 JSON payload.
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 9876
    DEFAULT_TIMEOUT = 30.0
    RENDER_TIMEOUT = 3600.0  # one still frame through the render engine
    ANIMATION_TIMEOUT = 43200.0  # a whole frame range
    BUSY_RETRY_DELAY = 2.0  # seconds between retries when Blender is rendering
    BUSY_MAX_RETRIES = 150  # ~5 minutes of waiting at 2s intervals

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._socket: socket.socket | None = None
        self._token: str | None = None
        self._key: bytes | None = None
        self._seq = 0
        self.addon_version: str | None = None
        self._lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return self._socket is not None

    def _open_socket(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._timeout)
            sock.connect((self._host, self._port))
            self._socket = sock
        except (ConnectionRefusedError, OSError) as e:
            raise BlenderConnectionError(
                f"Cannot connect to Blender at {self._host}:{self._port}. "
                "Ensure Blender is running with the blenderwright addon enabled."
            ) from e

    def connect(self) -> None:
        """Connect to the Blender addon and run the handshake.

        Blender writes a new token each time its server starts, so a failed
        proof is retried once with the token file read again.
        """
        if self._socket is not None:
            return
        for attempt in range(2):
            if self._token is None or attempt:
                stale = self._token
                self._token = read_token(self._port)
                if attempt and self._token == stale:
                    break
            self._open_socket()
            try:
                if self._handshake():
                    return
            except BaseException:
                self.disconnect()
                raise
            self.disconnect()
        raise BlenderAuthError(
            f"The process on {self._host}:{self._port} could not prove it is Blender "
            f"running blenderwright (it does not know the token in {token_path(self._port)}). "
            f"Nothing was sent to it. Restart the server from Blender's blenderwright "
            f"panel; if this keeps happening, another program may be using the port."
        )

    def _read_json(self) -> Any:
        return json.loads(self._recv_raw().decode("utf-8"))

    def _handshake(self) -> bool:
        """Prove each side knows the token without sending it.

        Returns False if Blender's proof fails, before anything but our
        nonce has been sent.
        """
        client_nonce = secrets.token_hex(32)
        self._send_raw(json.dumps({"hello": {
            "protocol": PROTOCOL_VERSION, "nonce": client_nonce}}).encode("utf-8"))
        hello = self._read_json()
        if not isinstance(hello, dict):
            raise BlenderConnectionError("Invalid handshake reply from Blender")
        if hello.get("code") == "protocol":
            raise BlenderConnectionError(f"blenderwright version mismatch: {hello.get('result')}")
        if hello.get("status") != "hello":
            raise BlenderConnectionError(
                "The Blender add-on is older than this MCP server (it does not speak "
                f"handshake protocol {PROTOCOL_VERSION}). Update the blenderwright add-on "
                "in Blender, then restart its server."
            )
        server_nonce = hello.get("nonce")
        sent_proof = hello.get("proof")
        expected = proof(self._token, "server", client_nonce, str(server_nonce))
        if not isinstance(server_nonce, str) or not isinstance(sent_proof, str) \
                or not hmac.compare_digest(sent_proof.encode(), expected.encode()):
            return False

        self._send_raw(json.dumps({"auth": proof(
            self._token, "client", server_nonce, client_nonce)}).encode("utf-8"))
        ready = self._read_json()
        if not isinstance(ready, dict) or ready.get("status") != "ready":
            raise BlenderAuthError(
                f"Blender refused this MCP server's proof: "
                f"{ready.get('result') if isinstance(ready, dict) else ready}"
            )
        self._key = session_key(self._token, client_nonce, server_nonce)
        self._seq = 0
        self.addon_version = hello.get("addon_version")
        return True

    def disconnect(self) -> None:
        """Disconnect from Blender."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        self._key = None

    def _send_raw(self, data: bytes) -> None:
        """Send length-prefixed data."""
        if self._socket is None:
            raise BlenderConnectionError("Not connected to Blender")
        header = struct.pack(">I", len(data))
        self._socket.sendall(header + data)

    def _recv_raw(self) -> bytes:
        """Receive length-prefixed data."""
        if self._socket is None:
            raise BlenderConnectionError("Not connected to Blender")
        header = self._recv_exactly(4)
        length = struct.unpack(">I", header)[0]
        if length > 100 * 1024 * 1024:  # 100MB sanity limit
            raise BlenderConnectionError(f"Response too large: {length} bytes")
        return self._recv_exactly(length)

    def _recv_exactly(self, n: int) -> bytes:
        """Receive exactly n bytes."""
        if self._socket is None:
            raise BlenderConnectionError("Not connected to Blender")
        chunks = []
        remaining = n
        while remaining > 0:
            chunk = self._socket.recv(min(remaining, 65536))
            if not chunk:
                raise BlenderConnectionError("Connection closed by Blender")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _exchange(self, message: dict[str, Any], timeout: float | None) -> Any:
        """Send one signed command and return Blender's verified reply."""
        if self._socket is None or self._key is None:
            raise BlenderConnectionError("Not connected to Blender")
        self._socket.settimeout(self._timeout if timeout is None else timeout)
        self._seq += 1
        seq = self._seq
        body = {"command": message["command"], "params": message.get("params", {})}
        try:
            self._send_raw(json.dumps({
                **body, "seq": seq, "mac": message_mac(self._key, "request", seq, body),
            }).encode("utf-8"))
        except OSError as e:
            raise _NotSent(str(e)) from e
        reply = self._read_json()
        if _is_unauthorized(reply):
            self.disconnect()
            raise BlenderAuthError(f"Blender refused the command: {reply.get('result')}")
        return self._verify_reply(reply, seq)

    def _verify_reply(self, reply: Any, seq: int) -> Any:
        """Check a reply's sequence number and signature; return it without them."""
        if not isinstance(reply, dict):
            return reply
        reply_body = {k: v for k, v in reply.items() if k not in ("seq", "mac")}
        mac = reply.get("mac")
        if reply.get("seq") != seq or not isinstance(mac, str) or not hmac.compare_digest(
                mac.encode(), message_mac(self._key, "response", seq, reply_body).encode()):
            self.disconnect()
            raise BlenderAuthError(
                "A reply from Blender failed signature verification and was discarded. "
                "Something may be interfering with the connection."
            )
        return reply_body

    def _is_stale(self) -> bool:
        """True when Blender closed this socket since the last reply, as when
        its server restarts. No reply is due between commands, so a readable
        socket means it is closed or out of step either way."""
        try:
            readable, _, _ = select.select([self._socket], [], [], 0)
        except (OSError, ValueError):
            return True
        return bool(readable)

    def _raise_lost(self, command: str, error: Exception) -> NoReturn:
        """Give up on a command whose reply was lost after it was sent.

        Blender may have run it, so a second copy could do the work twice.
        """
        self.disconnect()
        raise BlenderConnectionError(
            f"Connection to Blender lost while waiting for '{command}': {error}. "
            "The command was not resent and may have run in Blender."
        ) from error

    def _raise_unanswered(
        self, command: str, timeout: float | None, error: Exception
    ) -> NoReturn:
        """Give up on a command that was delivered but not answered in time.

        The socket is dropped because a late reply would be read as the answer
        to the next command. The command is not resent: Blender may still be
        running it, and a second copy would do the work twice.
        """
        self.disconnect()
        waited = self._timeout if timeout is None else timeout
        raise BlenderConnectionError(
            f"Blender did not answer '{command}' within {waited:.0f}s. "
            "The command was not resent and may still be running in Blender."
        ) from error

    def send_command(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a command to Blender and return the response.

        Args:
            command: The command name (must be in the addon's allowlist).
            params: Optional parameters for the command.
            timeout: Seconds to wait for the answer. Defaults to the
                connection timeout. Pass a longer value for renders.

        Returns:
            Response dict with 'status' ('ok' or 'error') and 'result'.

        Raises:
            BlenderConnectionError: If not connected or communication fails.
        """
        with self._lock:
            message = {"command": command}
            if params:
                message["params"] = params

            # A command is only ever resent when it never reached Blender:
            # a stale socket is replaced before sending, and a failed send
            # gets one retry on a fresh connection
            for attempt in range(2):
                if self._socket is not None and self._is_stale():
                    self.disconnect()
                if self._socket is None:
                    self.connect()

                try:
                    response = self._exchange(message, timeout)
                except BlenderAuthError:
                    raise
                except _NotSent as e:
                    self.disconnect()
                    if attempt == 0:
                        continue
                    raise BlenderConnectionError(f"Connection to Blender lost: {e}") from e
                except TimeoutError as e:
                    self._raise_unanswered(command, timeout, e)
                except (OSError, json.JSONDecodeError, BlenderConnectionError) as e:
                    self._raise_lost(command, e)
                else:
                    break

            if not isinstance(response, dict):
                raise BlenderConnectionError("Invalid response format from Blender")

            # If Blender is rendering, wait and retry automatically
            if response.get("status") == "busy":
                waiting_since = time.monotonic()
                for retry in range(self.BUSY_MAX_RETRIES):
                    logger.info(
                        "Blender is rendering, waiting %.1fs before retry %d/%d for '%s'",
                        self.BUSY_RETRY_DELAY, retry + 1, self.BUSY_MAX_RETRIES, command,
                    )
                    time.sleep(self.BUSY_RETRY_DELAY)

                    if self._socket is not None and self._is_stale():
                        self.disconnect()
                    if self._socket is None:
                        self.connect()
                    try:
                        response = self._exchange(message, timeout)
                    except BlenderAuthError:
                        raise
                    except _NotSent:
                        self.disconnect()
                        continue
                    except TimeoutError as e:
                        self._raise_unanswered(command, timeout, e)
                    except (OSError, json.JSONDecodeError, BlenderConnectionError) as e:
                        self._raise_lost(command, e)

                    if not isinstance(response, dict):
                        raise BlenderConnectionError("Invalid response format from Blender")

                    if response.get("status") != "busy":
                        return response

                raise BlenderConnectionError(
                    f"Blender was busy rendering for too long. "
                    f"Command '{command}' was not processed after "
                    f"{time.monotonic() - waiting_since:.0f}s of waiting."
                )

            return response

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()
