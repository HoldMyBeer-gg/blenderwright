"""Challenge-response handshake between the MCP server and the Blender add-on.

Real sockets, real BlenderServer, real BlenderConnection, in plain Python, so
the cross-platform CI (Windows included) runs it. Blender itself is replaced
by a dispatcher that answers directly.

What must hold:
- the token never crosses the socket;
- the client sends nothing useful to a process that cannot prove it knows
  the token (a squatter on the port);
- after the handshake every command and reply is signed, so commands cannot
  be injected, altered or replayed;
- version mismatches fail with a message that says what to update.
"""

import importlib.util
import json
import os
import socket
import struct
import sys
import threading
from unittest.mock import MagicMock

import pytest

from blenderwright import connection as client
from blenderwright.connection import BlenderAuthError, BlenderConnection, BlenderConnectionError

TOKEN = "f" * 64


def _load_addon(monkeypatch):
    """addon/auth.py and addon/server.py, with Blender-only modules stubbed."""
    root = os.path.join(os.path.dirname(__file__), "..", "addon")
    for name in ("addon", "addon.dispatcher", "addon.thread_safety", "addon.render_guard"):
        monkeypatch.setitem(sys.modules, name, MagicMock())
    sys.modules["addon.render_guard"].render_guard.is_rendering = False
    mods = {}
    for name in ("auth", "server"):
        spec = importlib.util.spec_from_file_location(f"addon.{name}",
                                                      os.path.join(root, f"{name}.py"))
        mod = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, f"addon.{name}", mod)
        spec.loader.exec_module(mod)
        mods[name] = mod
        # "from . import auth" reads the package attribute first
        setattr(sys.modules["addon"], name, mod)
    return mods["auth"], mods["server"]


@pytest.fixture
def blender(monkeypatch, tmp_path):
    """A running add-on server on a free port, answering commands directly."""
    token_file = tmp_path / "token"
    monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(token_file))
    auth, server_mod = _load_addon(monkeypatch)
    calls = []

    def dispatch(command, params):
        calls.append((command, params))
        return {"status": "ok", "result": {"echo": command, "params": params}}

    server_mod.dispatcher.dispatch = dispatch
    server_mod.thread_safety.execute_on_main_thread = lambda fn, *a: fn(*a)
    server_mod.thread_safety.MainThreadBusyError = type("Busy", (Exception,), {})
    srv = server_mod.BlenderServer(port=0)
    srv.start()
    yield SimpleNamespace(server=srv, port=srv.port, calls=calls, token_file=token_file,
                          auth=auth, server_mod=server_mod)
    srv.stop()


class SimpleNamespace:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _conn(port):
    return BlenderConnection(port=port, timeout=5.0)


def _frame(obj):
    data = json.dumps(obj).encode()
    return struct.pack(">I", len(data)) + data


def _read(sock):
    head = b""
    while len(head) < 4:
        head += sock.recv(4 - len(head))
    n = struct.unpack(">I", head)[0]
    body = b""
    while len(body) < n:
        body += sock.recv(n - len(body))
    return json.loads(body)


class TestHappyPath:
    def test_command_round_trip(self, blender):
        with _conn(blender.port) as conn:
            result = conn.send_command("get_scene_info", {"x": 1})
        assert result == {"status": "ok", "result": {"echo": "get_scene_info", "params": {"x": 1}}}
        assert blender.calls == [("get_scene_info", {"x": 1})]

    def test_many_commands_on_one_connection(self, blender):
        with _conn(blender.port) as conn:
            for i in range(5):
                assert conn.send_command("ping", {"i": i})["result"]["params"] == {"i": i}

    def test_reconnects_after_blender_restarts_with_a_new_token(self, blender):
        conn = _conn(blender.port)
        conn.send_command("ping")
        blender.server.stop()
        blender.server.start()  # writes a fresh token
        assert conn.send_command("ping")["status"] == "ok"
        conn.disconnect()

    def test_hello_reports_the_addon_version(self, blender):
        with _conn(blender.port) as conn:
            conn.send_command("ping")
            assert conn.addon_version


class TestTokenNeverCrossesTheSocket:
    def test_server_never_receives_the_token(self, blender):
        token = blender.token_file.read_text()
        seen = []
        original = blender.server._recv_message

        def spy(sock):
            data = original(sock)
            if data is not None:
                seen.append(data)
            return data

        blender.server._recv_message = spy
        with _conn(blender.port) as conn:
            conn.send_command("ping")
        assert seen and not any(token.encode() in d for d in seen)


class TestImpostor:
    """Something squatting on the port without the token."""

    def _impostor(self, reply):
        lsock = socket.socket()
        lsock.bind(("127.0.0.1", 0))
        lsock.listen(1)
        received = []

        def run():
            c, _ = lsock.accept()
            c.settimeout(2)
            try:
                received.append(_read(c))
                c.sendall(_frame(reply))
                while True:
                    data = c.recv(65536)
                    if not data:
                        break
                    received.append(data)
            except OSError:
                pass
            finally:
                c.close()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        return lsock, received, t

    def test_client_refuses_an_impostor_and_sends_it_nothing(self, tmp_path, monkeypatch):
        token_file = tmp_path / "token"
        token_file.write_text(TOKEN)
        monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(token_file))
        lsock, received, t = self._impostor({"status": "hello", "protocol": client.PROTOCOL_VERSION,
                                             "nonce": "a" * 64, "proof": "0" * 64,
                                             "addon_version": "9.9.9"})
        port = lsock.getsockname()[1]
        with pytest.raises(BlenderAuthError, match="prove"):
            _conn(port).send_command("delete_object", {"object_name": "Cube"})
        t.join(3)
        lsock.close()
        wire = b"".join(r if isinstance(r, bytes) else json.dumps(r).encode() for r in received)
        assert TOKEN.encode() not in wire
        assert b"delete_object" not in wire
        assert b"auth" not in wire


class TestTamperingAndReplay:
    def _handshake(self, blender):
        """Complete a real handshake by hand and return (sock, key, server_nonce)."""
        token = blender.token_file.read_text()
        sock = socket.create_connection(("127.0.0.1", blender.port), timeout=3)
        nc = os.urandom(32).hex()
        sock.sendall(_frame({"hello": {"protocol": client.PROTOCOL_VERSION, "nonce": nc}}))
        hello = _read(sock)
        ns = hello["nonce"]
        sock.sendall(_frame({"auth": client.proof(token, "client", ns, nc)}))
        assert _read(sock)["status"] == "ready"
        return sock, client.session_key(token, nc, ns)

    def _signed(self, key, seq, body):
        return {**body, "seq": seq, "mac": client.message_mac(key, "request", seq, body)}

    def test_altered_command_is_refused(self, blender):
        sock, key = self._handshake(blender)
        msg = self._signed(key, 1, {"command": "ping", "params": {}})
        msg["command"] = "delete_object"
        sock.sendall(_frame(msg))
        assert _read(sock)["code"] == "unauthorized"
        assert blender.calls == []

    def test_replayed_command_is_refused(self, blender):
        sock, key = self._handshake(blender)
        msg = self._signed(key, 1, {"command": "ping", "params": {}})
        sock.sendall(_frame(msg))
        assert _read(sock)["status"] == "ok"
        sock.sendall(_frame(msg))
        assert _read(sock)["code"] == "unauthorized"
        assert len(blender.calls) == 1

    def test_wrong_client_proof_is_refused(self, blender):
        sock = socket.create_connection(("127.0.0.1", blender.port), timeout=3)
        sock.sendall(_frame({"hello": {"protocol": client.PROTOCOL_VERSION, "nonce": "b" * 64}}))
        _read(sock)
        sock.sendall(_frame({"auth": "0" * 64}))
        assert _read(sock)["code"] == "unauthorized"
        assert blender.server.rejected_connections == 1


class TestVersions:
    def test_old_token_style_client_is_told_to_update(self, blender):
        sock = socket.create_connection(("127.0.0.1", blender.port), timeout=3)
        sock.sendall(_frame({"command": "ping", "token": "x"}))
        reply = _read(sock)
        assert reply["code"] == "unauthorized" and "update" in reply["result"].lower()

    def test_protocol_mismatch_is_explained(self, blender):
        sock = socket.create_connection(("127.0.0.1", blender.port), timeout=3)
        sock.sendall(_frame({"hello": {"protocol": 99, "nonce": "c" * 64}}))
        reply = _read(sock)
        assert reply["code"] == "protocol" and str(client.PROTOCOL_VERSION) in reply["result"]

    def test_client_explains_an_old_addon(self, tmp_path, monkeypatch):
        """An add-on from before the handshake answers hello with 'unauthorized'."""
        token_file = tmp_path / "token"
        token_file.write_text(TOKEN)
        monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(token_file))
        lsock = socket.socket()
        lsock.bind(("127.0.0.1", 0))
        lsock.listen(1)

        def old_addon():
            c, _ = lsock.accept()
            _read(c)
            c.sendall(_frame({"status": "error", "code": "unauthorized",
                              "result": "Unauthorized: missing or wrong token"}))
            c.close()

        threading.Thread(target=old_addon, daemon=True).start()
        with pytest.raises(BlenderConnectionError, match="add-on"):
            _conn(lsock.getsockname()[1]).send_command("ping")
        lsock.close()


class TestSharedCrypto:
    """The add-on and the MCP server compute the same proofs and MACs."""

    def test_both_sides_agree(self, monkeypatch):
        auth, _ = _load_addon(monkeypatch)
        nc, ns = "1" * 64, "2" * 64
        assert auth.proof(TOKEN, "server", nc, ns) == client.proof(TOKEN, "server", nc, ns)
        key = auth.session_key(TOKEN, nc, ns)
        assert key == client.session_key(TOKEN, nc, ns)
        body = {"command": "ping", "params": {"a": [1, 2.5, "x"], "b": True}}
        assert auth.message_mac(key, "request", 3, body) == client.message_mac(
            key, "request", 3, body)

    def test_proofs_differ_by_role_and_order(self):
        nc, ns = "1" * 64, "2" * 64
        assert client.proof(TOKEN, "server", nc, ns) != client.proof(TOKEN, "client", nc, ns)
        assert client.proof(TOKEN, "server", nc, ns) != client.proof(TOKEN, "server", ns, nc)


def test_busy_reply_keeps_the_signed_connection_working(blender, monkeypatch):
    """A busy Blender answers 'busy'; the client waits and the same connection goes on."""
    busy = blender.server_mod.thread_safety.MainThreadBusyError
    answers = iter([busy(), None])

    def flaky(fn, *args):
        outcome = next(answers, None)
        if isinstance(outcome, Exception):
            raise outcome
        return fn(*args)

    blender.server_mod.thread_safety.execute_on_main_thread = flaky
    monkeypatch.setattr(BlenderConnection, "BUSY_RETRY_DELAY", 0.0)
    with _conn(blender.port) as conn:
        assert conn.send_command("ping")["status"] == "ok"
        assert conn.send_command("ping")["status"] == "ok"
    assert len(blender.calls) == 2
