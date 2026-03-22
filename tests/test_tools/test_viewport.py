"""Unit tests for viewport tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"success": True}}
    with patch("blend_ai.tools.viewport.get_connection", return_value=mock):
        yield mock


class TestSetViewportShading:
    def test_set_wireframe(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_shading

        set_viewport_shading("WIREFRAME")
        mock_conn.send_command.assert_called_once_with("set_viewport_shading", {
            "mode": "WIREFRAME",
        })

    def test_set_solid(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_shading

        set_viewport_shading("SOLID")
        mock_conn.send_command.assert_called_once()

    def test_set_material(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_shading

        set_viewport_shading("MATERIAL")
        mock_conn.send_command.assert_called_once()

    def test_set_rendered(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_shading

        set_viewport_shading("RENDERED")
        mock_conn.send_command.assert_called_once()

    def test_invalid_mode(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_shading

        with pytest.raises(ValidationError):
            set_viewport_shading("TEXTURED")

    def test_case_sensitive(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_shading

        with pytest.raises(ValidationError):
            set_viewport_shading("wireframe")


class TestSetViewportOverlay:
    def test_enable_wireframes(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_overlay

        set_viewport_overlay("show_wireframes", True)
        mock_conn.send_command.assert_called_once_with("set_viewport_overlay", {
            "overlay": "show_wireframes",
            "enabled": True,
        })

    def test_disable_floor(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_overlay

        set_viewport_overlay("show_floor", False)
        mock_conn.send_command.assert_called_once_with("set_viewport_overlay", {
            "overlay": "show_floor",
            "enabled": False,
        })

    def test_show_stats(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_overlay

        set_viewport_overlay("show_stats", True)
        mock_conn.send_command.assert_called_once()

    def test_all_valid_overlays(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_overlay, ALLOWED_OVERLAYS

        for overlay in ALLOWED_OVERLAYS:
            mock_conn.send_command.reset_mock()
            set_viewport_overlay(overlay, True)
            mock_conn.send_command.assert_called_once()

    def test_invalid_overlay(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_overlay

        with pytest.raises(ValidationError):
            set_viewport_overlay("show_normals", True)

    def test_invalid_overlay_name(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_overlay

        with pytest.raises(ValidationError):
            set_viewport_overlay("wireframes", True)


class TestFocusOnObject:
    def test_focus_on_object(self, mock_conn):
        from blend_ai.tools.viewport import focus_on_object

        focus_on_object("Cube")
        mock_conn.send_command.assert_called_once_with("focus_on_object", {
            "object_name": "Cube",
        })

    def test_focus_with_dot_in_name(self, mock_conn):
        from blend_ai.tools.viewport import focus_on_object

        focus_on_object("Cube.001")
        mock_conn.send_command.assert_called_once_with("focus_on_object", {
            "object_name": "Cube.001",
        })

    def test_focus_invalid_name(self, mock_conn):
        from blend_ai.tools.viewport import focus_on_object

        with pytest.raises(ValidationError):
            focus_on_object("")

    def test_focus_special_chars_in_name(self, mock_conn):
        from blend_ai.tools.viewport import focus_on_object

        with pytest.raises(ValidationError):
            focus_on_object("Cube<script>")


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.viewport import set_viewport_shading

        mock_conn.send_command.return_value = {"status": "error", "result": "No 3D viewport"}
        with pytest.raises(RuntimeError, match="Blender error"):
            set_viewport_shading("SOLID")
