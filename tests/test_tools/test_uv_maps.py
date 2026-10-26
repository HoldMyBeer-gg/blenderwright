"""Tests for manage_uv_map."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.uv import ALLOWED_UV_MAP_ACTIONS, manage_uv_map
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"uv_maps": []}}
    with patch("blenderwright.tools.uv.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_actions():
    assert ALLOWED_UV_MAP_ACTIONS == {"LIST", "ADD", "REMOVE", "SET_ACTIVE", "SET_RENDER",
                                      "RENAME"}


def test_list(mock_conn):
    manage_uv_map("Cube", "LIST")
    assert _sent(mock_conn) == ("manage_uv_map", {"object_name": "Cube", "action": "LIST"})


def test_add_copies_active_by_default(mock_conn):
    manage_uv_map("Cube", "ADD", uv_map="Lightmap")
    assert _sent(mock_conn)[1] == {"object_name": "Cube", "action": "ADD",
                                   "uv_map": "Lightmap", "copy_active": True}


def test_add_blank(mock_conn):
    manage_uv_map("Cube", "ADD", uv_map="Lightmap", copy_active=False)
    assert _sent(mock_conn)[1]["copy_active"] is False


def test_rename(mock_conn):
    manage_uv_map("Cube", "RENAME", uv_map="UVMap", new_name="Base")
    assert _sent(mock_conn)[1] == {"object_name": "Cube", "action": "RENAME",
                                   "uv_map": "UVMap", "new_name": "Base"}


def test_rename_needs_new_name(mock_conn):
    with pytest.raises(ValidationError, match="new_name"):
        manage_uv_map("Cube", "RENAME", uv_map="UVMap")


@pytest.mark.parametrize("kwargs", [
    {"action": "COPY"},
    {"action": "ADD", "uv_map": "x\x00"},
    {"action": "ADD", "uv_map": ""},
    {"action": "ADD", "copy_active": "yes"},
    {"action": "RENAME", "new_name": "a" * 300},
])
def test_bad_input(mock_conn, kwargs):
    with pytest.raises(ValidationError):
        manage_uv_map("Cube", **kwargs)
    mock_conn.send_command.assert_not_called()
