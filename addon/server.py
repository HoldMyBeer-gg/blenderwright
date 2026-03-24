"""TCP socket server that runs inside Blender.

Listens for commands from the MCP server over a TCP socket.
Commands are executed on Blender's main thread via thread_safety module.
"""

import json
import socket
import struct
import threading
from typing import Any

from . import dispatcher
from . import thread_safety
from .render_guard import render_guard


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

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start the socket server in a background thread."""
        if self._running:
            return

        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self._host, self._port))
        self._server_socket.listen(1)
        self._server_socket.settimeout(1.0)  # Allow periodic shutdown checks
        self._running = True

        thread_safety.register_timer()

        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the socket server."""
        self._running = False

        with self._lock:
            for client in self._clients:
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

    def _accept_loop(self) -> None:
        """Accept incoming connections."""
        while self._running and self._server_socket:
            try:
                client, addr = self._server_socket.accept()
                client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                client.settimeout(30.0)
                with self._lock:
                    self._clients.append(client)
                handler_thread = threading.Thread(
                    target=self._handle_client, args=(client,), daemon=True
                )
                handler_thread.start()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    break

    def _handle_client(self, client: socket.socket) -> None:
        """Handle a single client connection."""
        try:
            while self._running:
                try:
                    data = self._recv_message(client)
                    if data is None:
                        break

                    message = json.loads(data.decode("utf-8"))
                    command = message.get("command", "")
                    params = message.get("params", {})

                    # Check if Blender is rendering — main thread is blocked
                    if render_guard.is_rendering:
                        response = {
                            "status": "busy",
                            "result": "Blender is currently rendering. "
                                      "Command will not be processed until "
                                      "the render completes.",
                        }
                    else:
                        # Execute on main thread via thread_safety
                        response = thread_safety.execute_on_main_thread(
                            dispatcher.dispatch, command, params
                        )

                    response_data = json.dumps(response).encode("utf-8")
                    self._send_message(client, response_data)

                except json.JSONDecodeError:
                    error_response = json.dumps({
                        "status": "error",
                        "result": "Invalid JSON in request",
                    }).encode("utf-8")
                    self._send_message(client, error_response)
                except socket.timeout:
                    continue
                except OSError:
                    break
        finally:
            with self._lock:
                if client in self._clients:
                    self._clients.remove(client)
            try:
                client.close()
            except OSError:
                pass

    def _send_message(self, sock: socket.socket, data: bytes) -> None:
        """Send a length-prefixed message."""
        header = struct.pack(">I", len(data))
        sock.sendall(header + data)

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
