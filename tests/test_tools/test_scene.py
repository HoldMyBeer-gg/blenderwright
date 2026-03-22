"""Unit tests for scene tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.scene import (
    get_scene_info,
    set_scene_property,
    list_scenes,
    create_scene,
    delete_scene,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.scene.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# get_scene_info
# ---------------------------------------------------------------------------


class TestGetSceneInfo:
    def test_sends_correct_command(self, mock_conn):
        result = get_scene_info()
        mock_conn.send_command.assert_called_once_with("get_scene_info")
        assert result == {"some": "data"}

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "no scene"}
        with pytest.raises(RuntimeError, match="Blender error: no scene"):
            get_scene_info()


# ---------------------------------------------------------------------------
# set_scene_property
# ---------------------------------------------------------------------------


class TestSetSceneProperty:
    def test_valid_frame_start(self, mock_conn):
        set_scene_property("frame_start", 10)
        mock_conn.send_command.assert_called_once_with(
            "set_scene_property", {"property": "frame_start", "value": 10}
        )

    def test_valid_fps(self, mock_conn):
        set_scene_property("fps", 30)
        mock_conn.send_command.assert_called_once_with(
            "set_scene_property", {"property": "fps", "value": 30}
        )

    def test_valid_unit_system(self, mock_conn):
        set_scene_property("unit_system", "METRIC")
        mock_conn.send_command.assert_called_once_with(
            "set_scene_property", {"property": "unit_system", "value": "METRIC"}
        )

    def test_valid_render_engine(self, mock_conn):
        set_scene_property("render_engine", "CYCLES")
        mock_conn.send_command.assert_called_once_with(
            "set_scene_property", {"property": "render_engine", "value": "CYCLES"}
        )

    def test_invalid_property_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_scene_property("invalid_prop", 10)

    def test_invalid_fps_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_scene_property("fps", 500)

    def test_invalid_fps_too_low_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_scene_property("fps", 0)

    def test_invalid_frame_value_negative_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_scene_property("frame_start", -1)

    def test_invalid_unit_system_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_scene_property("unit_system", "CUSTOM")

    def test_invalid_render_engine_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_scene_property("render_engine", "UNREAL")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_scene_property("fps", 24)


# ---------------------------------------------------------------------------
# list_scenes
# ---------------------------------------------------------------------------


class TestListScenes:
    def test_sends_correct_command(self, mock_conn):
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": [{"name": "Scene", "objects": 5}],
        }
        result = list_scenes()
        mock_conn.send_command.assert_called_once_with("list_scenes")
        assert result == [{"name": "Scene", "objects": 5}]

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "err"}
        with pytest.raises(RuntimeError):
            list_scenes()


# ---------------------------------------------------------------------------
# create_scene
# ---------------------------------------------------------------------------


class TestCreateScene:
    def test_valid_name(self, mock_conn):
        create_scene("NewScene")
        mock_conn.send_command.assert_called_once_with(
            "create_scene", {"name": "NewScene"}
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_scene("")

    def test_invalid_chars_in_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_scene("scene<>bad")

    def test_name_too_long_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_scene("a" * 64)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "exists"}
        with pytest.raises(RuntimeError):
            create_scene("Scene")


# ---------------------------------------------------------------------------
# delete_scene
# ---------------------------------------------------------------------------


class TestDeleteScene:
    def test_valid_name(self, mock_conn):
        delete_scene("OldScene")
        mock_conn.send_command.assert_called_once_with(
            "delete_scene", {"name": "OldScene"}
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            delete_scene("")

    def test_invalid_chars_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            delete_scene("bad;name")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {
            "status": "error",
            "result": "cannot delete last scene",
        }
        with pytest.raises(RuntimeError, match="cannot delete last scene"):
            delete_scene("Scene")
