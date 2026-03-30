"""TCP socket client for communicating with the Blender addon."""

import json
import logging
import socket
import struct
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class BlenderConnectionError(Exception):
    """Raised when connection to Blender fails."""
    pass


class BlenderConnection:
    """TCP socket client that connects to the Blender addon's socket server.

    Protocol: Each message is a 4-byte big-endian length prefix followed by
    a UTF-8 JSON payload.
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 9876
    DEFAULT_TIMEOUT = 30.0
    BUSY_RETRY_DELAY = 2.0  # seconds between retries when Blender is rendering
    BUSY_MAX_RETRIES = 150  # ~5 minutes of waiting at 2s intervals

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._socket: socket.socket | None = None
        self._lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return self._socket is not None

    def connect(self) -> None:
        """Connect to the Blender addon socket server."""
        if self._socket is not None:
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._timeout)
            sock.connect((self._host, self._port))
            self._socket = sock
        except (ConnectionRefusedError, OSError) as e:
            raise BlenderConnectionError(
                f"Cannot connect to Blender at {self._host}:{self._port}. "
                "Ensure Blender is running with the blend-ai addon enabled."
            ) from e

    def disconnect(self) -> None:
        """Disconnect from Blender."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

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

    def send_command(self, command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a command to Blender and return the response.

        Args:
            command: The command name (must be in the addon's allowlist).
            params: Optional parameters for the command.

        Returns:
            Response dict with 'status' ('ok' or 'error') and 'result'.

        Raises:
            BlenderConnectionError: If not connected or communication fails.
        """
        with self._lock:
            message = {"command": command}
            if params:
                message["params"] = params

            # Try up to 2 times — reconnect on stale connection
            last_error = None
            for attempt in range(2):
                if self._socket is None:
                    self.connect()

                try:
                    payload = json.dumps(message).encode("utf-8")
                    self._send_raw(payload)
                    response_data = self._recv_raw()
                    response = json.loads(response_data.decode("utf-8"))
                except (OSError, json.JSONDecodeError, BlenderConnectionError) as e:
                    last_error = e  # noqa: F841
                    self.disconnect()
                    if attempt == 0:
                        continue  # retry with fresh connection
                    raise BlenderConnectionError(
                        f"Connection to Blender lost: {e}"
                    ) from e
                else:
                    break

            if not isinstance(response, dict):
                raise BlenderConnectionError("Invalid response format from Blender")

            # If Blender is rendering, wait and retry automatically
            if response.get("status") == "busy":
                for retry in range(self.BUSY_MAX_RETRIES):
                    logger.info(
                        "Blender is rendering, waiting %.1fs before retry %d/%d for '%s'",
                        self.BUSY_RETRY_DELAY, retry + 1, self.BUSY_MAX_RETRIES, command,
                    )
                    time.sleep(self.BUSY_RETRY_DELAY)

                    try:
                        payload = json.dumps(message).encode("utf-8")
                        self._send_raw(payload)
                        response_data = self._recv_raw()
                        response = json.loads(response_data.decode("utf-8"))
                    except (OSError, json.JSONDecodeError, BlenderConnectionError):
                        self.disconnect()
                        self.connect()
                        continue

                    if not isinstance(response, dict):
                        raise BlenderConnectionError("Invalid response format from Blender")

                    if response.get("status") != "busy":
                        return response

                raise BlenderConnectionError(
                    f"Blender was busy rendering for too long. "
                    f"Command '{command}' was not processed after "
                    f"{self.BUSY_MAX_RETRIES * self.BUSY_RETRY_DELAY:.0f}s of waiting."
                )

            return response

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()
