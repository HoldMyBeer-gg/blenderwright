"""Tests for BlenderServer — SO_KEEPALIVE and stale client cleanup."""

import os
import sys
import socket
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_server_module():
    """Load addon/server.py directly without triggering addon/__init__.py imports."""
    # Set up mock modules before loading
    mock_dispatcher = MagicMock()
    mock_thread_safety = MagicMock()
    mock_render_guard_module = MagicMock()
    mock_render_guard = MagicMock()
    mock_render_guard.is_rendering = False
    mock_render_guard_module.render_guard = mock_render_guard

    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = mock_dispatcher
    sys.modules["addon.thread_safety"] = mock_thread_safety
    sys.modules["addon.render_guard"] = mock_render_guard_module

    server_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "addon", "server.py",
    )
    spec = importlib.util.spec_from_file_location("addon.server", server_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.server"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def server_module():
    """Provide the loaded server module."""
    return _load_server_module()


class TestSOKeepalive:
    """Tests that accepted client sockets have SO_KEEPALIVE set."""

    def test_accepted_client_has_keepalive(self, server_module):
        """After accept(), client socket has SO_KEEPALIVE set to 1."""
        BlenderServer = server_module.BlenderServer
        server = BlenderServer()

        mock_client = MagicMock(spec=socket.socket)
        mock_server_socket = MagicMock()
        mock_server_socket.accept.side_effect = [
            (mock_client, ("127.0.0.1", 12345)),
            OSError("stop loop"),
        ]

        server._server_socket = mock_server_socket
        server._running = True

        # Run accept loop — it will accept one client then hit OSError to exit
        server._accept_loop()

        # Verify SO_KEEPALIVE was set on the accepted client
        mock_client.setsockopt.assert_any_call(
            socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1
        )


class TestClientCleanup:
    """Tests that stale/disconnected clients are removed from _clients list."""

    def test_client_removed_on_disconnect(self, server_module):
        """When _recv_message returns None, client is removed from _clients."""
        BlenderServer = server_module.BlenderServer
        server = BlenderServer()

        mock_client = MagicMock(spec=socket.socket)
        server._running = True

        # Pre-add client to the list
        with server._lock:
            server._clients.append(mock_client)

        # Simulate disconnect: _recv_message returns None
        server._recv_message = MagicMock(return_value=None)

        server._handle_client(mock_client)

        assert mock_client not in server._clients

    def test_client_socket_closed_on_disconnect(self, server_module):
        """When client disconnects, its socket is closed."""
        BlenderServer = server_module.BlenderServer
        server = BlenderServer()

        mock_client = MagicMock(spec=socket.socket)
        server._running = True

        with server._lock:
            server._clients.append(mock_client)

        server._recv_message = MagicMock(return_value=None)

        server._handle_client(mock_client)

        mock_client.close.assert_called()
