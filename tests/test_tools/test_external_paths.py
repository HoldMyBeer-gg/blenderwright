"""Tests for manage_external_paths and validate_directory."""

import os
from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.file_ops import ALLOWED_PATH_ACTIONS, manage_external_paths
from blenderwright.validators import ValidationError, validate_directory


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"files": []}}
    with patch("blenderwright.tools.file_ops.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestValidateDirectory:
    def test_existing_directory(self, tmp_path):
        assert validate_directory(str(tmp_path)) == str(tmp_path.resolve())

    def test_relative_refused(self):
        with pytest.raises(ValidationError, match="absolute"):
            validate_directory("textures")

    def test_file_refused(self, tmp_path):
        f = tmp_path / "a.png"
        f.write_bytes(b"x")
        with pytest.raises(ValidationError, match="not a directory"):
            validate_directory(str(f))

    def test_missing_refused(self, tmp_path):
        with pytest.raises(ValidationError):
            validate_directory(str(tmp_path / "nope"))

    def test_filesystem_root_refused(self):
        with pytest.raises(ValidationError, match="root"):
            validate_directory(os.path.abspath(os.sep))

    @pytest.mark.parametrize("bad", ["", None, 5, "/tmp/\x00x"])
    def test_junk(self, bad):
        with pytest.raises(ValidationError):
            validate_directory(bad)


def test_actions():
    assert ALLOWED_PATH_ACTIONS == {"LIST", "MAKE_RELATIVE", "MAKE_ABSOLUTE", "FIND_MISSING"}


@pytest.mark.parametrize("action", ["LIST", "MAKE_RELATIVE", "MAKE_ABSOLUTE"])
def test_simple_actions(mock_conn, action):
    manage_external_paths(action)
    assert _sent(mock_conn) == ("manage_external_paths", {"action": action})


def test_find_missing_sends_resolved_directory(mock_conn, tmp_path):
    manage_external_paths("FIND_MISSING", directory=str(tmp_path))
    assert _sent(mock_conn)[1] == {"action": "FIND_MISSING",
                                   "directory": str(tmp_path.resolve())}


def test_find_missing_needs_directory(mock_conn):
    with pytest.raises(ValidationError, match="directory"):
        manage_external_paths("FIND_MISSING")


def test_unknown_action(mock_conn):
    with pytest.raises(ValidationError):
        manage_external_paths("DELETE")
    mock_conn.send_command.assert_not_called()
