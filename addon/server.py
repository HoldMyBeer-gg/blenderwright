"""TCP socket server that runs inside Blender.

Listens for commands from the MCP server over a TCP socket.
Commands are executed on Blender's main thread via thread_safety module.
"""

import hmac
import json
import os
import re
import secrets
import socket
import struct
import sys
import threading

from . import auth
from . import dispatcher
from . import thread_safety
from .render_guard import render_guard


def _reject_non_finite(constant: str):
    """Reject NaN and Infinity at the protocol boundary.

    Python's json parser accepts the non-standard NaN, Infinity and
    -Infinity literals by default. Assigning those into Blender properties
    writes garbage that persists into the saved .blend, so they are refused
    here rather than in each handler.
    """
    raise ValueError(f"Non-finite JSON constant '{constant}' is not accepted")


def _addon_version() -> str:
    """The add-on version from its manifest, reported in the handshake."""
    path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
    try:
        with open(path, encoding="utf-8") as f:
            match = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
    except OSError:
        return "unknown"
    return match.group(1) if match else "unknown"


ADDON_VERSION = _addon_version()
NONCE_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _claim_port(sock: socket.socket) -> None:
    """Make the listening port ours alone.

    On Windows SO_REUSEADDR lets another process bind the same port and
    receive connections meant for Blender; SO_EXCLUSIVEADDRUSE refuses that.
    On POSIX SO_REUSEADDR only permits rebinding after a quick restart.
    """
    if sys.platform == "win32":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    else:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


class BlenderServer:
    """TCP socket server for receiving MCP commands inside Blender."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9876):
        self._host = host
        self._port = port
        self._server_socket: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._clients: list[socket.socket] = []
        self._lock = threading.Lock()
        self._token = ""
        self.rejected_connections = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def port(self) -> int:
        """The bound port; the real one when started with port 0."""
        return self._port

    def start(self) -> None:
        """Start the socket server in a background thread."""
        if self._running:
            return

        # Port first: a Blender that cannot get it must not replace the token
        # another Blender is already serving with
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            _claim_port(self._server_socket)
            self._server_socket.bind((self._host, self._port))
        except OSError:
            self._server_socket.close()
            self._server_socket = None
            raise
        self._port = self._server_socket.getsockname()[1]

        token = auth.new_token()
        auth.write_token(token, self._port)
        self._token = token
        self._server_socket.listen(1)
        self._server_socket.settimeout(0.2)  # Notice Stop Server within a fifth of a second
        self._running = True

        thread_safety.register_timer()

        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the socket server."""
        self._running = False

        with self._lock:
            for client in self._clients:
                # shutdown() first: on Linux, close() alone does not end a
                # connection another thread is reading
                try:
                    client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    client.close()
                except OSError:
                    pass
            self._clients.clear()

        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            self._thread = None

        thread_safety.unregister_timer()
        # Only the server that wrote the token removes it: another Blender may
        # be serving this port with its own
        if self._token:
            auth.clear_token(self._port)
            self._token = ""

    def _accept_loop(self) -> None:
        """Accept incoming connections."""
        while self._running and self._server_socket:
            try:
                client, addr = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                continue  # one failed accept; stop() ends the loop
            try:
                client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                client.settimeout(30.0)
            except OSError:  # the client reset before setup
                client.close()
                continue
            with self._lock:
                self._clients.append(client)
            handler_thread = threading.Thread(
                target=self._handle_client, args=(client,), daemon=True
            )
            handler_thread.start()

    def _read_json(self, client: socket.socket):
        data = self._recv_message(client)
        if data is None:
            return None
        return json.loads(data.decode("utf-8"), parse_constant=_reject_non_finite)

    def _send_json(self, client: socket.socket, obj) -> None:
        self._send_message(client, json.dumps(obj).encode("utf-8"))

    def _handshake(self, client: socket.socket):
        """Prove ourselves, then check the client's proof. Returns the session key.

        The token never crosses the socket: each side signs both nonces with it.
        Returns None, after answering, when the client fails or is outdated.
        """
        hello = self._read_json(client)
        if hello is None:
            return None
        if not isinstance(hello, dict) or "hello" not in hello:
            self._reject(client, "This blenderwright MCP server is older than the add-on "
                                 f"(it needs protocol {auth.PROTOCOL_VERSION}); update it.")
            return None
        info = hello["hello"] if isinstance(hello["hello"], dict) else {}
        if info.get("protocol") != auth.PROTOCOL_VERSION:
            self._send_json(client, {
                "status": "error", "code": "protocol", "protocol": auth.PROTOCOL_VERSION,
                "addon_version": ADDON_VERSION,
                "result": f"The add-on speaks protocol {auth.PROTOCOL_VERSION} and the MCP "
                          f"server speaks {info.get('protocol')}; update whichever is older.",
            })
            return None
        client_nonce = info.get("nonce")
        if not isinstance(client_nonce, str) or not NONCE_PATTERN.match(client_nonce) \
                or not self._token:
            self._reject(client)
            return None

        server_nonce = secrets.token_hex(32)
        self._send_json(client, {
            "status": "hello", "protocol": auth.PROTOCOL_VERSION, "nonce": server_nonce,
            "proof": auth.proof(self._token, "server", client_nonce, server_nonce),
            "addon_version": ADDON_VERSION,
        })
        answer = self._read_json(client)
        expected = auth.proof(self._token, "client", server_nonce, client_nonce)
        sent = answer.get("auth") if isinstance(answer, dict) else None
        if not isinstance(sent, str) or not hmac.compare_digest(sent.encode(), expected.encode()):
            self._reject(client)
            return None
        self._send_json(client, {"status": "ready"})
        return auth.session_key(self._token, client_nonce, server_nonce)

    def _run_command(self, command, params):
        # Check if Blender is rendering: main thread is blocked
        if render_guard.is_rendering:
            return {
                "status": "busy",
                "result": "Blender is currently rendering. "
                          "Command will not be processed until "
                          "the render completes.",
            }
        try:
            return thread_safety.execute_on_main_thread(dispatcher.dispatch, command, params)
        except thread_safety.MainThreadBusyError:
            return {
                "status": "busy",
                "result": "Blender's main thread is busy. "
                          "The command was not run; send it again.",
            }

    def _handle_client(self, client: socket.socket) -> None:
        """Handshake, then run signed commands until the client disconnects."""
        try:
            key = self._handshake(client)
            if key is None:
                return
            expected_seq = 1
            while self._running:
                try:
                    message = self._read_json(client)
                    if message is None:
                        break
                    body = {"command": message.get("command", ""),
                            "params": message.get("params", {})} \
                        if isinstance(message, dict) else None
                    mac = message.get("mac") if isinstance(message, dict) else None
                    if (body is None or message.get("seq") != expected_seq
                            or not isinstance(mac, str)
                            or not hmac.compare_digest(
                                mac.encode(),
                                auth.message_mac(key, "request", expected_seq, body).encode())):
                        self._reject(client, "Command signature or sequence did not verify. "
                                             "The connection was closed and nothing was run.")
                        break
                    response = self._run_command(body["command"], body["params"])
                    self._send_json(client, {
                        **response, "seq": expected_seq,
                        "mac": auth.message_mac(key, "response", expected_seq, response),
                    })
                    expected_seq += 1
                except json.JSONDecodeError:
                    self._reject(client, "Invalid JSON; the connection was closed.")
                    break
                except socket.timeout:
                    continue
                except OSError:
                    break
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        finally:
            with self._lock:
                if client in self._clients:
                    self._clients.remove(client)
            try:
                client.close()
            except OSError:
                pass

    def _reject(self, client: socket.socket, reason: str = "") -> None:
        """Refuse loudly, then the caller drops the connection."""
        self.rejected_connections += 1
        print(
            "blenderwright: refused a connection that did not authenticate "
            f"({self.rejected_connections} so far)"
        )
        try:
            self._send_json(client, {
                "status": "error",
                "code": "unauthorized",
                "result": reason or "Unauthorized: the client could not prove it knows the "
                                    "blenderwright auth token. The connection was closed "
                                    "and nothing was run.",
            })
        except OSError:
            pass

    def _send_message(self, sock: socket.socket, data: bytes) -> None:
        """Send a length-prefixed message.

        The header and payload are sent in two separate sendall calls rather
        than concatenated. On Blender 5.1 Windows builds, some reports
        (issue #5) showed the length prefix being silently dropped when the
        concatenated bytes were passed to sendall: every response arrived
        as raw JSON without the 4-byte header, causing the client to misread
        the first four JSON bytes as a length and bail with "Response too
        large". Splitting the call guarantees the header is transmitted
        before the body and rules out any concat atomicity edge case.
        """
        header = struct.pack(">I", len(data))
        sock.sendall(header)
        sock.sendall(data)

    def _recv_message(self, sock: socket.socket) -> bytes | None:
        """Receive a length-prefixed message. Returns None on disconnect."""
        header = self._recv_exactly(sock, 4)
        if header is None:
            return None
        length = struct.unpack(">I", header)[0]
        if length > 100 * 1024 * 1024:  # 100MB sanity limit
            raise ValueError(f"Message too large: {length} bytes")
        return self._recv_exactly(sock, length)

    def _recv_exactly(self, sock: socket.socket, n: int) -> bytes | None:
        """Receive exactly n bytes. Returns None on disconnect."""
        chunks = []
        remaining = n
        while remaining > 0:
            chunk = sock.recv(min(remaining, 65536))
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


# Global server instance
_server: BlenderServer | None = None


def get_server() -> BlenderServer:
    """Get or create the global server instance."""
    global _server
    if _server is None:
        _server = BlenderServer()
    return _server


def start_server(host: str = "127.0.0.1", port: int = 9876) -> None:
    """Start the global server."""
    global _server
    if _server is not None and _server.is_running:
        return
    _server = BlenderServer(host=host, port=port)
    _server.start()


def stop_server() -> None:
    """Stop the global server."""
    global _server
    if _server is not None:
        _server.stop()
        _server = None
