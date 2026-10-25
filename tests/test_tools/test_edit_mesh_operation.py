"""Tool-side tests for edit_mesh_operation. Behaviour: tests_live/test_edit_mesh.py."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.mesh_editing import ALLOWED_EDIT_OPERATIONS, edit_mesh_operation
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.mesh_editing.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_operations():
    assert ALLOWED_EDIT_OPERATIONS == {"SMOOTH_VERTICES", "POKE", "EDGE_SPLIT", "WIREFRAME",
                                       "SOLIDIFY"}


@pytest.mark.parametrize("operation, kwargs, sent", [
    ("SMOOTH_VERTICES", {"factor": 0.3, "repeat": 4}, {"factor": 0.3, "repeat": 4}),
    ("POKE", {"offset": 0.2}, {"offset": 0.2}),
    ("EDGE_SPLIT", {}, {}),
    ("WIREFRAME", {"thickness": 0.05}, {"thickness": 0.05}),
    ("SOLIDIFY", {"thickness": 0.1}, {"thickness": 0.1}),
])
def test_sends_only_what_the_operation_uses(mock_conn, operation, kwargs, sent):
    edit_mesh_operation("Cube", operation, **kwargs)
    assert _sent(mock_conn) == ("edit_mesh_operation", {
        "object_name": "Cube", "operation": operation, "selection": "ALL", **sent})


@pytest.mark.parametrize("kwargs", [
    {"operation": "EXPLODE"},
    {"operation": "SMOOTH_VERTICES", "factor": 2},
    {"operation": "SMOOTH_VERTICES", "repeat": 0},
    {"operation": "SMOOTH_VERTICES", "repeat": 1000},
    {"operation": "WIREFRAME", "thickness": 0},
    {"operation": "SOLIDIFY", "thickness": 1e6},
    {"operation": "POKE", "offset": float("nan")},
    {"operation": "POKE", "selection": "SOME"},
])
def test_bad_input(mock_conn, kwargs):
    with pytest.raises(ValidationError):
        edit_mesh_operation("Cube", **kwargs)
    mock_conn.send_command.assert_not_called()
