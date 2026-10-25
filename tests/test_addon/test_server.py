"""Tests for BlenderServer: SO_KEEPALIVE and stale client cleanup."""

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

    auth_path = os.path.join(os.path.dirname(__file__), "..", "..", "addon", "auth.py")
    auth_spec = importlib.util.spec_from_file_location("addon.auth", auth_path)
    auth_mod = importlib.util.module_from_spec(auth_spec)
    auth_spec.loader.exec_module(auth_mod)
    sys.modules["addon.auth"] = auth_mod
    sys.modules["addon"].auth = auth_mod

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
        # _accept_loop spawns a real handler thread for this client. Without a
        # realistic disconnect, recv() returns a MagicMock, which is truthy, so the
        # `if not chunk` guard never fires, but len() == 0, so _recv_exactly
        # loops forever. The thread then spins for the rest of the session,
        # growing the heap until pytest's teardown gc collect crawls.
        mock_client.recv.return_value = b""
        mock_server_socket = MagicMock()
        mock_server_socket.accept.side_effect = [
            (mock_client, ("127.0.0.1", 12345)),
            OSError("stop loop"),
        ]

        server._server_socket = mock_server_socket
        server._running = True

        # Run accept loop: it will accept one client then hit OSError to exit
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


class TestNonFiniteJSON:
    """Python's json parser accepts NaN and Infinity by default.

    Assigning those into Blender properties writes garbage that persists
    into the saved .blend, so they are refused at the protocol boundary
    rather than in each individual handler.
    """

    def test_reject_non_finite_raises(self, server_module):
        with pytest.raises(ValueError):
            server_module._reject_non_finite("Infinity")

    def test_parser_rejects_infinity(self, server_module):
        import json

        with pytest.raises(ValueError):
            json.loads(
                '{"v": Infinity}',
                parse_constant=server_module._reject_non_finite,
            )

    def test_parser_rejects_nan(self, server_module):
        import json

        with pytest.raises(ValueError):
            json.loads(
                '{"v": NaN}', parse_constant=server_module._reject_non_finite
            )

    def test_parser_accepts_ordinary_numbers(self, server_module):
        import json

        parsed = json.loads(
            '{"v": 1.5, "w": -2}',
            parse_constant=server_module._reject_non_finite,
        )
        assert parsed == {"v": 1.5, "w": -2}


class TestAuthToken:
    """Handshake behaviour is tested over real sockets in tests/test_handshake.py."""

    def test_start_writes_a_fresh_token_and_stop_clears_it(self, server_module, monkeypatch):
        written, cleared = [], []
        monkeypatch.setattr(server_module.auth, "write_token",
                            lambda token, port: written.append(token))
        monkeypatch.setattr(server_module.auth, "clear_token", lambda port: cleared.append(port))
        monkeypatch.setattr(server_module.socket, "socket", MagicMock())
        monkeypatch.setattr(server_module.threading, "Thread", MagicMock())

        server = server_module.BlenderServer()
        server.start()
        first = server._token
        server.stop()
        server.start()
        server.stop()

        assert written[0] == first and len(written) == 2 and written[0] != written[1]
        assert len(cleared) == 2


class TestTakenPortKeepsTheToken:
    """A second Blender that cannot get the port must not replace the token
    the first one is serving with, or the MCP can no longer authenticate."""

    def test_no_token_written_when_the_port_is_taken(self, server_module, monkeypatch):
        written = []
        monkeypatch.setattr(server_module.auth, "write_token",
                            lambda token, port: written.append(token))
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        try:
            server = server_module.BlenderServer(port=holder.getsockname()[1])
            with pytest.raises(OSError):
                server.start()
            assert written == []
            assert not server.is_running
        finally:
            holder.close()


class TestPortIsExclusive:
    """Windows SO_REUSEADDR lets a second process bind the same port and take
    connections meant for Blender. Windows needs SO_EXCLUSIVEADDRUSE instead;
    on POSIX, SO_REUSEADDR only allows a quick restart, never sharing."""

    def _options(self, server_module, monkeypatch, platform):
        monkeypatch.setattr(server_module.sys, "platform", platform)
        monkeypatch.setattr(server_module.socket, "SO_EXCLUSIVEADDRUSE", -5, raising=False)
        sock = MagicMock()
        server_module._claim_port(sock)
        return [c.args[1] for c in sock.setsockopt.call_args_list]

    def test_windows_claims_the_port_exclusively(self, server_module, monkeypatch):
        options = self._options(server_module, monkeypatch, "win32")
        assert options == [-5]
        assert server_module.socket.SO_REUSEADDR not in options

    @pytest.mark.parametrize("platform", ["darwin", "linux"])
    def test_posix_keeps_reuseaddr_for_quick_restarts(self, server_module, monkeypatch,
                                                     platform):
        assert self._options(server_module, monkeypatch, platform) == [
            server_module.socket.SO_REUSEADDR]

