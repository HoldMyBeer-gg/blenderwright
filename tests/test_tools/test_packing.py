"""Tests for pack_resources and unpack_resources."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.file_ops import pack_resources, unpack_resources
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"packed": []}}
    with patch("blenderwright.tools.file_ops.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestPackResources:
    def test_packs_everything(self, mock_conn):
        pack_resources()
        assert _sent(mock_conn) == ("pack_resources", {})

    def test_autopack(self, mock_conn):
        pack_resources(autopack=True)
        assert _sent(mock_conn) == ("pack_resources", {"autopack": True})

    def test_autopack_must_be_bool(self, mock_conn):
        with pytest.raises(ValidationError):
            pack_resources(autopack="on")

    def test_blender_error_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "nope"}
        with pytest.raises(RuntimeError, match="nope"):
            pack_resources()


class TestUnpackResources:
    def test_keeps_existing_files_by_default(self, mock_conn):
        unpack_resources()
        assert _sent(mock_conn) == ("unpack_resources", {"overwrite": False})

    def test_overwrite(self, mock_conn):
        unpack_resources(overwrite=True)
        assert _sent(mock_conn) == ("unpack_resources", {"overwrite": True})

    def test_overwrite_must_be_bool(self, mock_conn):
        with pytest.raises(ValidationError):
            unpack_resources(overwrite="yes")

    def test_no_way_to_pick_a_destination(self):
        import inspect

        assert set(inspect.signature(unpack_resources).parameters) == {"overwrite"}
