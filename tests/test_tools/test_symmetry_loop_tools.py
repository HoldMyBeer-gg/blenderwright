"""Tests for symmetrize_mesh, bisect_mesh and loop_tools."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.mesh_editing import bisect_mesh, loop_tools, symmetrize_mesh
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.mesh_editing.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestSymmetrize:
    def test_defaults(self, mock_conn):
        symmetrize_mesh("Head")
        assert _sent(mock_conn) == ("symmetrize_mesh", {
            "object_name": "Head", "direction": "NEGATIVE_X", "threshold": 0.0001,
            "selection": "ALL"})

    @pytest.mark.parametrize("kwargs", [{"direction": "LEFT"}, {"threshold": -1},
                                        {"threshold": 2}, {"selection": "SOME"}])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            symmetrize_mesh("Head", **kwargs)


class TestBisect:
    def test_cut_and_clear(self, mock_conn):
        bisect_mesh("Log", plane_point=[0, 0, 5], plane_normal=[0, 0, 1], clear_outer=True,
                    fill=True)
        assert _sent(mock_conn) == ("bisect_mesh", {
            "object_name": "Log", "plane_point": [0.0, 0.0, 5.0],
            "plane_normal": [0.0, 0.0, 1.0], "clear_inner": False, "clear_outer": True,
            "fill": True, "selection": "ALL"})

    @pytest.mark.parametrize("kwargs", [
        {"plane_normal": [0, 0, 0]}, {"plane_normal": [0, 1]},
        {"plane_point": [0, float("nan"), 0]},
        {"clear_inner": True, "clear_outer": True},
    ])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            bisect_mesh("Log", **kwargs)


class TestLoopTools:
    def test_circle_defaults_to_current_selection(self, mock_conn):
        loop_tools("Pipe", "CIRCLE")
        assert _sent(mock_conn) == ("loop_tools", {
            "object_name": "Pipe", "operation": "CIRCLE", "factor": 1.0,
            "selection": "CURRENT"})

    def test_circle_radius(self, mock_conn):
        loop_tools("Pipe", "CIRCLE", radius=0.5)
        assert _sent(mock_conn)[1]["radius"] == 0.5

    def test_space_and_flatten(self, mock_conn):
        loop_tools("Pipe", "SPACE", factor=0.5)
        assert _sent(mock_conn)[1] == {"object_name": "Pipe", "operation": "SPACE",
                                       "factor": 0.5, "selection": "CURRENT"}
        loop_tools("Pipe", "FLATTEN", selection="ALL")
        assert _sent(mock_conn)[1]["selection"] == "ALL"

    @pytest.mark.parametrize("kwargs", [
        {"operation": "SQUARE"}, {"operation": "CIRCLE", "factor": 2},
        {"operation": "CIRCLE", "radius": 0}, {"operation": "SPACE", "radius": 1},
    ])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            loop_tools("Pipe", **kwargs)
