"""Client token file handling. The handshake is tested in tests/test_handshake.py."""

import pytest

from blenderwright.connection import BlenderAuthError, BlenderConnection


def test_missing_token_file_fails_loud(mock_socket, token_file):
    token_file.unlink()
    with pytest.raises(BlenderAuthError, match="Start Server"):
        BlenderConnection().send_command("get_scene_info")
