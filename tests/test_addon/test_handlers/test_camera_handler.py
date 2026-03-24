"""Tests for fast viewport capture handler — validates render.opengl usage."""

import os
import sys
import base64
import importlib.util
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock
import pytest


def _load_camera_handler():
    """Load addon.handlers.camera directly without triggering addon/handlers/__init__.py."""
    mock_dispatcher = MagicMock()

    # Create an addon mock with dispatcher set so `from .. import dispatcher` resolves
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "camera.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.camera", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.camera"] = mod
    spec.loader.exec_module(mod)
    return mod, mock_dispatcher


@pytest.fixture(scope="module")
def camera_handler():
    """Provide loaded camera handler module."""
    mod, _dispatcher = _load_camera_handler()
    return mod


@pytest.fixture(scope="module")
def camera_handler_with_dispatcher():
    """Provide loaded camera handler module and mock dispatcher.
    
    Note: Returns the same module as camera_handler since they share sys.modules.
    """
    # The dispatcher mock is already in sys.modules from camera_handler fixture
    mod = sys.modules.get("addon.handlers.camera")
    disp = sys.modules.get("addon.dispatcher")
    if mod is None:
        mod, disp = _load_camera_handler()
    return mod, disp


def _setup_mock_bpy_for_fast_capture():
    """Configure mock bpy for fast viewport capture tests."""
    import bpy

    # Reset mocks
    bpy.reset_mock()

    # Set up scene render properties
    bpy.context.scene.render.resolution_x = 1920
    bpy.context.scene.render.resolution_y = 1080
    bpy.context.scene.render.resolution_percentage = 100

    # Set up a mock 3D viewport area
    mock_area = MagicMock()
    mock_area.type = "VIEW_3D"

    mock_screen = MagicMock()
    mock_screen.areas = [mock_area]

    mock_window = MagicMock()
    mock_window.screen = mock_screen

    bpy.context.window_manager.windows = [mock_window]

    # Set up temp_override as a context manager
    mock_override = MagicMock()
    mock_override.__enter__ = MagicMock(return_value=None)
    mock_override.__exit__ = MagicMock(return_value=False)
    bpy.context.temp_override.return_value = mock_override

    # Set up render.opengl mock
    bpy.ops.render.opengl = MagicMock()

    # Set up Render Result image mock that writes a valid PNG
    mock_image = MagicMock()

    def fake_save_render(filepath):
        """Write minimal PNG bytes for testing."""
        # Minimal valid PNG: 8-byte signature + IHDR + IDAT + IEND
        png_bytes = (
            b'\x89PNG\r\n\x1a\n'  # PNG signature
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde'
            b'\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05'
            b'\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        with open(filepath, "wb") as f:
            f.write(png_bytes)

    mock_image.save_render = MagicMock(side_effect=fake_save_render)
    bpy.data.images.get.return_value = mock_image

    return bpy


class TestFastViewportCapture:
    """Tests for handle_fast_viewport_capture handler."""

    def test_calls_render_opengl(self, camera_handler):
        """Fast capture uses bpy.ops.render.opengl, not bpy.ops.render.render."""
        bpy = _setup_mock_bpy_for_fast_capture()

        camera_handler.handle_fast_viewport_capture({})

        bpy.ops.render.opengl.assert_called_once_with(write_still=True)

    def test_result_contains_required_keys(self, camera_handler):
        """Result dict has base64, format, width, height, and mode keys."""
        _setup_mock_bpy_for_fast_capture()

        result = camera_handler.handle_fast_viewport_capture({})

        assert "base64" in result
        assert "format" in result
        assert "width" in result
        assert "height" in result
        assert "mode" in result

    def test_result_mode_is_fast(self, camera_handler):
        """Result mode is 'fast'."""
        _setup_mock_bpy_for_fast_capture()

        result = camera_handler.handle_fast_viewport_capture({})

        assert result["mode"] == "fast"

    def test_result_format_is_png(self, camera_handler):
        """Result format is 'png'."""
        _setup_mock_bpy_for_fast_capture()

        result = camera_handler.handle_fast_viewport_capture({})

        assert result["format"] == "png"

    def test_result_base64_is_valid(self, camera_handler):
        """Result base64 can be decoded."""
        _setup_mock_bpy_for_fast_capture()

        result = camera_handler.handle_fast_viewport_capture({})

        decoded = base64.b64decode(result["base64"])
        assert len(decoded) > 0

    def test_restores_resolution_on_success(self, camera_handler):
        """Resolution settings are restored after successful capture."""
        import bpy
        _setup_mock_bpy_for_fast_capture()

        # Set original values
        bpy.context.scene.render.resolution_x = 1920
        bpy.context.scene.render.resolution_y = 1080
        bpy.context.scene.render.resolution_percentage = 100

        camera_handler.handle_fast_viewport_capture({"width": 800, "height": 600})

        # Verify originals restored
        assert bpy.context.scene.render.resolution_x == 1920
        assert bpy.context.scene.render.resolution_y == 1080
        assert bpy.context.scene.render.resolution_percentage == 100

    def test_restores_resolution_on_exception(self, camera_handler):
        """Resolution settings are restored even if capture fails."""
        import bpy
        _setup_mock_bpy_for_fast_capture()

        bpy.context.scene.render.resolution_x = 1920
        bpy.context.scene.render.resolution_y = 1080
        bpy.context.scene.render.resolution_percentage = 100

        # Make opengl raise an error
        bpy.ops.render.opengl.side_effect = RuntimeError("GPU error")

        with pytest.raises(RuntimeError):
            camera_handler.handle_fast_viewport_capture({"width": 800, "height": 600})

        # Verify originals restored despite error
        assert bpy.context.scene.render.resolution_x == 1920
        assert bpy.context.scene.render.resolution_y == 1080
        assert bpy.context.scene.render.resolution_percentage == 100

    def test_uses_temp_override_with_view3d(self, camera_handler):
        """Uses bpy.context.temp_override with a VIEW_3D area."""
        bpy = _setup_mock_bpy_for_fast_capture()

        camera_handler.handle_fast_viewport_capture({})

        bpy.context.temp_override.assert_called()
        # Verify the override was called with window and area kwargs
        call_kwargs = bpy.context.temp_override.call_args
        assert "window" in call_kwargs.kwargs or len(call_kwargs.args) > 0

    def test_default_resolution(self, camera_handler):
        """Default resolution is 1920x1080 when not specified."""
        _setup_mock_bpy_for_fast_capture()

        result = camera_handler.handle_fast_viewport_capture({})

        assert result["width"] == 1920
        assert result["height"] == 1080

    def test_custom_resolution(self, camera_handler):
        """Custom width/height from params are used."""
        _setup_mock_bpy_for_fast_capture()

        result = camera_handler.handle_fast_viewport_capture(
            {"width": 800, "height": 600}
        )

        assert result["width"] == 800
        assert result["height"] == 600

    def test_registered_in_dispatcher(self, camera_handler_with_dispatcher):
        """fast_viewport_capture command is registered in dispatcher."""
        mod, mock_dispatcher = camera_handler_with_dispatcher
        mock_dispatcher.reset_mock()
        mod.register()
        registered_commands = [
            call.args[0] for call in mock_dispatcher.register_handler.call_args_list
        ]
        assert "fast_viewport_capture" in registered_commands

    def test_raises_when_no_view3d(self, camera_handler):
        """Raises RuntimeError when no 3D viewport is found."""
        import bpy
        _setup_mock_bpy_for_fast_capture()

        # Replace areas with no VIEW_3D
        mock_area = MagicMock()
        mock_area.type = "PROPERTIES"
        mock_window = MagicMock()
        mock_window.screen.areas = [mock_area]
        bpy.context.window_manager.windows = [mock_window]

        with pytest.raises(RuntimeError, match="No 3D viewport"):
            camera_handler.handle_fast_viewport_capture({})

    def test_raises_when_no_render_result(self, camera_handler):
        """Raises RuntimeError when Render Result image is not available."""
        import bpy
        _setup_mock_bpy_for_fast_capture()

        bpy.data.images.get.return_value = None

        with pytest.raises(RuntimeError, match="No render result"):
            camera_handler.handle_fast_viewport_capture({})
