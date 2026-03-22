"""Unit tests for animation tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"success": True}}
    with patch("blend_ai.tools.animation.get_connection", return_value=mock):
        yield mock


class TestInsertKeyframe:
    def test_insert_keyframe_basic(self, mock_conn):
        from blend_ai.tools.animation import insert_keyframe

        result = insert_keyframe("Cube", "location", 1)
        mock_conn.send_command.assert_called_once_with("insert_keyframe", {
            "object_name": "Cube",
            "data_path": "location",
            "frame": 1,
            "value": None,
        })
        assert result == {"success": True}

    def test_insert_keyframe_with_value(self, mock_conn):
        from blend_ai.tools.animation import insert_keyframe

        insert_keyframe("Cube", "location[0]", 10, value=5.0)
        mock_conn.send_command.assert_called_once_with("insert_keyframe", {
            "object_name": "Cube",
            "data_path": "location[0]",
            "frame": 10,
            "value": 5.0,
        })

    def test_insert_keyframe_invalid_data_path(self, mock_conn):
        from blend_ai.tools.animation import insert_keyframe

        with pytest.raises(ValidationError, match="data_path must be one of"):
            insert_keyframe("Cube", "color", 1)

    def test_insert_keyframe_empty_data_path(self, mock_conn):
        from blend_ai.tools.animation import insert_keyframe

        with pytest.raises(ValidationError, match="data_path must be a non-empty string"):
            insert_keyframe("Cube", "", 1)

    def test_insert_keyframe_negative_frame(self, mock_conn):
        from blend_ai.tools.animation import insert_keyframe

        with pytest.raises(ValidationError):
            insert_keyframe("Cube", "location", -1)

    def test_insert_keyframe_frame_too_large(self, mock_conn):
        from blend_ai.tools.animation import insert_keyframe

        with pytest.raises(ValidationError):
            insert_keyframe("Cube", "location", 1048575)

    def test_insert_keyframe_all_valid_data_paths(self, mock_conn):
        from blend_ai.tools.animation import insert_keyframe, ALLOWED_DATA_PATHS

        for dp in ALLOWED_DATA_PATHS:
            mock_conn.send_command.reset_mock()
            insert_keyframe("Cube", dp, 0)
            mock_conn.send_command.assert_called_once()


class TestDeleteKeyframe:
    def test_delete_keyframe(self, mock_conn):
        from blend_ai.tools.animation import delete_keyframe

        delete_keyframe("Cube", "rotation_euler", 24)
        mock_conn.send_command.assert_called_once_with("delete_keyframe", {
            "object_name": "Cube",
            "data_path": "rotation_euler",
            "frame": 24,
        })

    def test_delete_keyframe_invalid_data_path(self, mock_conn):
        from blend_ai.tools.animation import delete_keyframe

        with pytest.raises(ValidationError):
            delete_keyframe("Cube", "visibility", 1)

    def test_delete_keyframe_invalid_name(self, mock_conn):
        from blend_ai.tools.animation import delete_keyframe

        with pytest.raises(ValidationError):
            delete_keyframe("", "location", 1)


class TestSetFrame:
    def test_set_frame(self, mock_conn):
        from blend_ai.tools.animation import set_frame

        set_frame(100)
        mock_conn.send_command.assert_called_once_with("set_frame", {"frame": 100})

    def test_set_frame_zero(self, mock_conn):
        from blend_ai.tools.animation import set_frame

        set_frame(0)
        mock_conn.send_command.assert_called_once_with("set_frame", {"frame": 0})

    def test_set_frame_negative(self, mock_conn):
        from blend_ai.tools.animation import set_frame

        with pytest.raises(ValidationError):
            set_frame(-1)


class TestSetFrameRange:
    def test_set_frame_range(self, mock_conn):
        from blend_ai.tools.animation import set_frame_range

        set_frame_range(1, 250)
        mock_conn.send_command.assert_called_once_with("set_frame_range", {
            "start": 1,
            "end": 250,
        })

    def test_set_frame_range_end_must_exceed_start(self, mock_conn):
        from blend_ai.tools.animation import set_frame_range

        with pytest.raises(ValidationError, match="end.*must be greater than start"):
            set_frame_range(100, 50)

    def test_set_frame_range_equal_values(self, mock_conn):
        from blend_ai.tools.animation import set_frame_range

        with pytest.raises(ValidationError, match="end.*must be greater than start"):
            set_frame_range(100, 100)


class TestSetInterpolation:
    def test_set_interpolation_bezier(self, mock_conn):
        from blend_ai.tools.animation import set_interpolation

        set_interpolation("Cube", "location", "BEZIER")
        mock_conn.send_command.assert_called_once_with("set_interpolation", {
            "object_name": "Cube",
            "data_path": "location",
            "interpolation": "BEZIER",
        })

    def test_set_interpolation_linear(self, mock_conn):
        from blend_ai.tools.animation import set_interpolation

        set_interpolation("Cube", "scale", "LINEAR")
        mock_conn.send_command.assert_called_once()

    def test_set_interpolation_invalid_type(self, mock_conn):
        from blend_ai.tools.animation import set_interpolation

        with pytest.raises(ValidationError):
            set_interpolation("Cube", "location", "SMOOTH")

    def test_set_interpolation_invalid_data_path(self, mock_conn):
        from blend_ai.tools.animation import set_interpolation

        with pytest.raises(ValidationError):
            set_interpolation("Cube", "custom_prop", "LINEAR")


class TestCreateAnimationPath:
    def test_create_animation_path(self, mock_conn):
        from blend_ai.tools.animation import create_animation_path

        create_animation_path("Cube", "BezierCircle")
        mock_conn.send_command.assert_called_once_with("create_animation_path", {
            "object_name": "Cube",
            "path_object": "BezierCircle",
        })

    def test_create_animation_path_invalid_names(self, mock_conn):
        from blend_ai.tools.animation import create_animation_path

        with pytest.raises(ValidationError):
            create_animation_path("", "BezierCircle")
        with pytest.raises(ValidationError):
            create_animation_path("Cube", "")


class TestListKeyframes:
    def test_list_keyframes(self, mock_conn):
        from blend_ai.tools.animation import list_keyframes

        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": [{"data_path": "location", "frame": 1, "value": [0, 0, 0]}],
        }
        result = list_keyframes("Cube")
        mock_conn.send_command.assert_called_once_with("list_keyframes", {"object_name": "Cube"})
        assert len(result) == 1

    def test_list_keyframes_invalid_name(self, mock_conn):
        from blend_ai.tools.animation import list_keyframes

        with pytest.raises(ValidationError):
            list_keyframes("")


class TestClearAnimation:
    def test_clear_animation(self, mock_conn):
        from blend_ai.tools.animation import clear_animation

        clear_animation("Cube")
        mock_conn.send_command.assert_called_once_with("clear_animation", {"object_name": "Cube"})

    def test_clear_animation_invalid_name(self, mock_conn):
        from blend_ai.tools.animation import clear_animation

        with pytest.raises(ValidationError):
            clear_animation("")


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.animation import insert_keyframe

        mock_conn.send_command.return_value = {"status": "error", "result": "Object not found"}
        with pytest.raises(RuntimeError, match="Blender error"):
            insert_keyframe("Cube", "location", 1)
