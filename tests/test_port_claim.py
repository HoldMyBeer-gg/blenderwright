"""The add-on's listening port cannot be taken by a second process.

Lives outside tests/test_addon so the cross-platform CI matrix (which
includes Windows) runs it against real sockets.
"""

import importlib.util
import os
import socket
import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def server_module(monkeypatch):
    for name in ("addon", "addon.dispatcher", "addon.thread_safety", "addon.render_guard",
                 "addon.auth"):
        monkeypatch.setitem(sys.modules, name, MagicMock())
    path = os.path.join(os.path.dirname(__file__), "..", "addon", "server.py")
    spec = importlib.util.spec_from_file_location("addon_server_port_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_second_socket_cannot_take_a_claimed_port(server_module):
    first = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_module._claim_port(first)
    first.bind(("127.0.0.1", 0))
    first.listen(1)
    port = first.getsockname()[1]
    intruder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    intruder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        with pytest.raises(OSError):
            intruder.bind(("127.0.0.1", port))
    finally:
        intruder.close()
        first.close()
