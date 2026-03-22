"""Shared test fixtures."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_connection():
    """Mock BlenderConnection that returns configurable responses."""
    with patch("blend_ai.server._connection") as mock_conn:
        conn = MagicMock()
        conn.send_command = MagicMock(return_value={"status": "ok", "result": {}})
        mock_conn.return_value = conn
        # Also patch get_connection to return our mock
        with patch("blend_ai.server.get_connection", return_value=conn):
            yield conn


@pytest.fixture
def mock_socket():
    """Mock socket for connection tests."""
    with patch("socket.socket") as mock_sock_class:
        mock_sock = MagicMock()
        mock_sock_class.return_value = mock_sock
        yield mock_sock
