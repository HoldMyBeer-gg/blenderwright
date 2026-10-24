"""Shared test fixtures."""

import pytest
from unittest.mock import MagicMock, patch

TEST_TOKEN = "a" * 64


@pytest.fixture(scope="session")
def _session_token_file(tmp_path_factory):
    return tmp_path_factory.mktemp("auth") / "token"


@pytest.fixture(autouse=True)
def _isolated_token(_session_token_file, monkeypatch):
    """Point both ends at a throwaway token file, never the user's real one."""
    _session_token_file.write_text(TEST_TOKEN)
    monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(_session_token_file))


@pytest.fixture
def token_file(tmp_path, monkeypatch):
    """A token file of the test's own, for tests that change or delete it."""
    path = tmp_path / "token"
    path.write_text(TEST_TOKEN)
    monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(path))
    return path


@pytest.fixture
def mock_connection():
    """Mock BlenderConnection that returns configurable responses."""
    with patch("blenderwright.server._connection") as mock_conn:
        conn = MagicMock()
        conn.send_command = MagicMock(return_value={"status": "ok", "result": {}})
        mock_conn.return_value = conn
        # Also patch get_connection to return our mock
        with patch("blenderwright.server.get_connection", return_value=conn):
            yield conn


@pytest.fixture
def mock_socket():
    """Mock socket for connection tests."""
    with patch("socket.socket") as mock_sock_class:
        mock_sock = MagicMock()
        mock_sock_class.return_value = mock_sock
        yield mock_sock
