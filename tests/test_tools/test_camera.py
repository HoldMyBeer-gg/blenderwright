"""Unit tests for camera tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"name": "Camera"}}
    with patch("blend_ai.tools.camera.get_connection", return_value=mock):
        yield mock


class TestCreateCamera:
    def test_create_camera_defaults(self, mock_conn):
        from blend_ai.tools.camera import create_camera

        result = create_camera()
        mock_conn.send_command.assert_called_once_with("create_camera", {
            "name": "Camera",
            "location": [0, 0, 0],
            "rotation": [0, 0, 0],
            "lens": 50.0,
        })
        assert result == {"name": "Camera"}

    def test_create_camera_custom(self, mock_conn):
        from blend_ai.tools.camera import create_camera

        create_camera(name="MyCam", location=[1, 2, 3], rotation=[0.1, 0.2, 0.3], lens=85.0)
        mock_conn.send_command.assert_called_once_with("create_camera", {
            "name": "MyCam",
            "location": [1, 2, 3],
            "rotation": [0.1, 0.2, 0.3],
            "lens": 85.0,
        })

    def test_create_camera_lens_out_of_range(self, mock_conn):
        from blend_ai.tools.camera import create_camera

        with pytest.raises(ValidationError):
            create_camera(lens=0.5)
        with pytest.raises(ValidationError):
            create_camera(lens=501.0)

    def test_create_camera_invalid_location(self, mock_conn):
        from blend_ai.tools.camera import create_camera

        with pytest.raises(ValidationError):
            create_camera(location=[1, 2])

    def test_create_camera_invalid_name(self, mock_conn):
        from blend_ai.tools.camera import create_camera

        with pytest.raises(ValidationError):
            create_camera(name="")


class TestSetCameraProperty:
    def test_set_lens(self, mock_conn):
        from blend_ai.tools.camera import set_camera_property

        set_camera_property("Camera", "lens", 35.0)
        mock_conn.send_command.assert_called_once_with("set_camera_property", {
            "name": "Camera",
            "property": "lens",
            "value": 35.0,
        })

    def test_set_type_valid(self, mock_conn):
        from blend_ai.tools.camera import set_camera_property

        set_camera_property("Camera", "type", "ORTHO")
        mock_conn.send_command.assert_called_once()

    def test_set_invalid_property(self, mock_conn):
        from blend_ai.tools.camera import set_camera_property

        with pytest.raises(ValidationError):
            set_camera_property("Camera", "invalid_prop", 1.0)

    def test_set_lens_out_of_range(self, mock_conn):
        from blend_ai.tools.camera import set_camera_property

        with pytest.raises(ValidationError):
            set_camera_property("Camera", "lens", 0.0)

    def test_set_dof_use_dof_not_bool(self, mock_conn):
        from blend_ai.tools.camera import set_camera_property

        with pytest.raises(ValidationError):
            set_camera_property("Camera", "dof.use_dof", "yes")

    def test_set_shift_x_in_range(self, mock_conn):
        from blend_ai.tools.camera import set_camera_property

        set_camera_property("Camera", "shift_x", 5.0)
        mock_conn.send_command.assert_called_once()

    def test_set_shift_x_out_of_range(self, mock_conn):
        from blend_ai.tools.camera import set_camera_property

        with pytest.raises(ValidationError):
            set_camera_property("Camera", "shift_x", 11.0)

    def test_set_sensor_fit_invalid(self, mock_conn):
        from blend_ai.tools.camera import set_camera_property

        with pytest.raises(ValidationError):
            set_camera_property("Camera", "sensor_fit", "DIAGONAL")

    def test_set_camera_type_invalid(self, mock_conn):
        from blend_ai.tools.camera import set_camera_property

        with pytest.raises(ValidationError):
            set_camera_property("Camera", "type", "FISHEYE")


class TestSetActiveCamera:
    def test_set_active_camera(self, mock_conn):
        from blend_ai.tools.camera import set_active_camera

        set_active_camera("Camera.001")
        mock_conn.send_command.assert_called_once_with("set_active_camera", {"name": "Camera.001"})

    def test_set_active_camera_empty_name(self, mock_conn):
        from blend_ai.tools.camera import set_active_camera

        with pytest.raises(ValidationError):
            set_active_camera("")


class TestPointCameraAt:
    def test_point_at_target(self, mock_conn):
        from blend_ai.tools.camera import point_camera_at

        point_camera_at("Camera", target="Cube")
        mock_conn.send_command.assert_called_once_with("point_camera_at", {
            "camera_name": "Camera",
            "target": "Cube",
        })

    def test_point_at_location(self, mock_conn):
        from blend_ai.tools.camera import point_camera_at

        point_camera_at("Camera", location=[1, 2, 3])
        mock_conn.send_command.assert_called_once_with("point_camera_at", {
            "camera_name": "Camera",
            "location": [1, 2, 3],
        })

    def test_point_at_neither(self, mock_conn):
        from blend_ai.tools.camera import point_camera_at

        with pytest.raises(ValidationError, match="Must provide either"):
            point_camera_at("Camera")

    def test_point_at_both(self, mock_conn):
        from blend_ai.tools.camera import point_camera_at

        with pytest.raises(ValidationError, match="Cannot provide both"):
            point_camera_at("Camera", target="Cube", location=[1, 2, 3])


class TestCaptureViewport:
    def test_capture_defaults(self, mock_conn):
        from blend_ai.tools.camera import capture_viewport

        capture_viewport()
        mock_conn.send_command.assert_called_once_with("capture_viewport", {
            "filepath": "",
            "width": 1920,
            "height": 1080,
        })

    def test_capture_with_filepath(self, mock_conn):
        from blend_ai.tools.camera import capture_viewport

        capture_viewport(filepath="/tmp/test.png")
        call_args = mock_conn.send_command.call_args
        assert call_args[0][0] == "capture_viewport"
        assert call_args[0][1]["width"] == 1920

    def test_capture_width_too_large(self, mock_conn):
        from blend_ai.tools.camera import capture_viewport

        with pytest.raises(ValidationError):
            capture_viewport(width=9000)

    def test_capture_invalid_extension(self, mock_conn):
        from blend_ai.tools.camera import capture_viewport

        with pytest.raises(ValidationError):
            capture_viewport(filepath="/tmp/test.py")


class TestSetCameraFromView:
    def test_set_camera_from_view(self, mock_conn):
        from blend_ai.tools.camera import set_camera_from_view

        result = set_camera_from_view()
        mock_conn.send_command.assert_called_once_with("set_camera_from_view", None)
        assert result == {"name": "Camera"}


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.camera import create_camera

        mock_conn.send_command.return_value = {"status": "error", "result": "Camera not found"}
        with pytest.raises(RuntimeError, match="Blender error"):
            create_camera()
