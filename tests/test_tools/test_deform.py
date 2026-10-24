"""Tests for vertex group and shape key tools."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.deform import (
    add_shape_key,
    assign_vertex_group,
    keyframe_shape_key,
    list_shape_keys,
    list_vertex_groups,
    move_shape_key_vertices,
    remove_shape_key,
    remove_vertex_group,
    set_shape_key,
    vertex_group_operation,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.deform.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestAssignVertexGroup:
    def test_defaults_to_whole_mesh_replace(self, mock_conn):
        assign_vertex_group("Body", "Arm")
        assert _sent(mock_conn) == ("assign_vertex_group", {
            "object_name": "Body", "group_name": "Arm", "weight": 1.0,
            "mode": "REPLACE", "selection": "ALL"})

    def test_indices(self, mock_conn):
        assign_vertex_group("Body", "Arm", vertex_indices=[0, 3, 3, 7], weight=0.5, mode="ADD")
        assert _sent(mock_conn)[1]["vertex_indices"] == [0, 3, 7]
        assert _sent(mock_conn)[1]["weight"] == 0.5

    @pytest.mark.parametrize("kwargs", [
        {"weight": 1.5}, {"weight": -0.1}, {"mode": "MULTIPLY"}, {"selection": "SOME"},
        {"vertex_indices": [-1]}, {"vertex_indices": [1.5]}, {"vertex_indices": "0,1"},
        {"vertex_indices": []},
    ])
    def test_rejects_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            assign_vertex_group("Body", "Arm", **kwargs)
        mock_conn.send_command.assert_not_called()

    @pytest.mark.parametrize("names", [("Bo/dy", "Arm"), ("Body", ""), ("Body", "Arm;rm")])
    def test_rejects_bad_names(self, mock_conn, names):
        with pytest.raises(ValidationError):
            assign_vertex_group(*names)


class TestVertexGroupOperation:
    def test_smooth(self, mock_conn):
        vertex_group_operation("Body", "Arm", "SMOOTH", factor=0.4, repeat=3)
        assert _sent(mock_conn) == ("vertex_group_operation", {
            "object_name": "Body", "group_name": "Arm", "operation": "SMOOTH",
            "factor": 0.4, "repeat": 3})

    def test_operations_only_send_their_own_options(self, mock_conn):
        vertex_group_operation("Body", "Arm", "CLEAN", threshold=0.05, factor=0.9)
        assert _sent(mock_conn)[1] == {"object_name": "Body", "group_name": "Arm",
                                       "operation": "CLEAN", "threshold": 0.05}

    def test_limit_total_and_levels_and_quantize(self, mock_conn):
        vertex_group_operation("Body", "Arm", "LIMIT_TOTAL", max_groups=4)
        assert _sent(mock_conn)[1]["max_groups"] == 4
        vertex_group_operation("Body", "Arm", "LEVELS", offset=0.1, gain=1.5)
        assert (_sent(mock_conn)[1]["offset"], _sent(mock_conn)[1]["gain"]) == (0.1, 1.5)
        vertex_group_operation("Body", "Arm", "QUANTIZE", steps=4)
        assert _sent(mock_conn)[1]["steps"] == 4

    @pytest.mark.parametrize("kwargs", [
        {"operation": "BLUR"}, {"operation": "SMOOTH", "repeat": 0},
        {"operation": "SMOOTH", "factor": 2}, {"operation": "LIMIT_TOTAL", "max_groups": 0},
        {"operation": "QUANTIZE", "steps": 0}, {"operation": "LEVELS", "gain": 20},
    ])
    def test_rejects_bad_options(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            vertex_group_operation("Body", "Arm", **kwargs)


class TestShapeKeys:
    def test_add(self, mock_conn):
        add_shape_key("Face", "Smile")
        assert _sent(mock_conn) == ("add_shape_key", {
            "object_name": "Face", "key_name": "Smile", "from_mix": False})

    def test_set_sends_only_given(self, mock_conn):
        set_shape_key("Face", "Smile", value=0.7, vertex_group="Mouth")
        assert _sent(mock_conn)[1] == {"object_name": "Face", "key_name": "Smile",
                                       "value": 0.7, "vertex_group": "Mouth"}

    def test_set_can_clear_the_vertex_group(self, mock_conn):
        set_shape_key("Face", "Smile", vertex_group="")
        assert _sent(mock_conn)[1]["vertex_group"] == ""

    @pytest.mark.parametrize("kwargs", [
        {"value": 11}, {"slider_min": -11}, {"slider_max": 11},
        {"slider_min": 1, "slider_max": 0}, {"vertex_group": "a/b"},
    ])
    def test_set_rejects_bad_values(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_shape_key("Face", "Smile", **kwargs)

    def test_move_vertices_by_group(self, mock_conn):
        move_shape_key_vertices("Face", "Cheeks", [0, 0.1, 0], vertex_group="Cheeks")
        assert _sent(mock_conn) == ("move_shape_key_vertices", {
            "object_name": "Face", "key_name": "Cheeks", "offset": [0.0, 0.1, 0.0],
            "vertex_group": "Cheeks"})

    def test_move_vertices_by_index(self, mock_conn):
        move_shape_key_vertices("Face", "Up", [0, 0, 1], vertex_indices=[4, 5])
        assert _sent(mock_conn)[1]["vertex_indices"] == [4, 5]

    @pytest.mark.parametrize("kwargs", [
        {"offset": [0, 1]}, {"offset": [0, float("nan"), 0]}, {"offset": [0, 0, 1e6]},
        {"offset": [0, 0, 1], "vertex_indices": [1], "vertex_group": "G"},
    ])
    def test_move_rejects_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            move_shape_key_vertices("Face", "Up", **kwargs)

    def test_keyframe(self, mock_conn):
        keyframe_shape_key("Face", "Smile", frame=12, value=1.0)
        assert _sent(mock_conn) == ("keyframe_shape_key", {
            "object_name": "Face", "key_name": "Smile", "frame": 12, "value": 1.0})

    def test_lists_and_removes(self, mock_conn):
        list_shape_keys("Face")
        assert _sent(mock_conn) == ("list_shape_keys", {"object_name": "Face"})
        remove_shape_key("Face", "Smile")
        assert _sent(mock_conn) == ("remove_shape_key", {"object_name": "Face",
                                                         "key_name": "Smile"})
        list_vertex_groups("Face")
        assert _sent(mock_conn) == ("list_vertex_groups", {"object_name": "Face"})
        remove_vertex_group("Face", "Mouth")
        assert _sent(mock_conn) == ("remove_vertex_group", {"object_name": "Face",
                                                            "group_name": "Mouth"})

    def test_blender_error_raised(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "nope"}
        with pytest.raises(RuntimeError, match="nope"):
            list_shape_keys("Face")
