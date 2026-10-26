"""Tests for manage_linked_data."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.file_ops import ALLOWED_LINKED_ACTIONS, manage_linked_data
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.file_ops.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_actions():
    assert ALLOWED_LINKED_ACTIONS == {"LIST", "MAKE_LOCAL", "OVERRIDE", "RELOAD"}


def test_list(mock_conn):
    manage_linked_data("LIST")
    assert _sent(mock_conn) == ("manage_linked_data", {"action": "LIST"})


def test_make_local(mock_conn):
    manage_linked_data("MAKE_LOCAL", data_name="Oak", data_type="MATERIAL")
    assert _sent(mock_conn)[1] == {"action": "MAKE_LOCAL", "data_name": "Oak",
                                   "data_type": "MATERIAL"}


def test_override_with_library(mock_conn):
    manage_linked_data("OVERRIDE", data_name="Chair", library="chairs.blend")
    assert _sent(mock_conn)[1] == {"action": "OVERRIDE", "data_name": "Chair",
                                   "data_type": "OBJECT", "library": "chairs.blend"}


def test_reload(mock_conn):
    manage_linked_data("RELOAD", library="chairs.blend")
    assert _sent(mock_conn)[1] == {"action": "RELOAD", "library": "chairs.blend"}


@pytest.mark.parametrize("kwargs", [
    {"action": "DELETE"},
    {"action": "MAKE_LOCAL"},
    {"action": "OVERRIDE", "data_name": "Oak", "data_type": "MATERIAL"},
    {"action": "MAKE_LOCAL", "data_name": "x", "data_type": "SCRIPT"},
    {"action": "RELOAD"},
    {"action": "RELOAD", "library": "x\x00"},
    {"action": "MAKE_LOCAL", "data_name": "x\x00"},
])
def test_bad_input(mock_conn, kwargs):
    with pytest.raises(ValidationError):
        manage_linked_data(**kwargs)
    mock_conn.send_command.assert_not_called()
