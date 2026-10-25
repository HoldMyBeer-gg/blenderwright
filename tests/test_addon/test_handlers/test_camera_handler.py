"""Tests for fast viewport capture handler: validates render.opengl usage."""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
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


class TestCaptureViewportCleanup:
    """A failed capture must not leave the scene's render settings or temp files behind."""

    def _scene(self, video_output_scene):
        import bpy

        render = bpy.context.scene.render
        render.resolution_x = 1920
        render.resolution_y = 1080
        render.resolution_percentage = 50
        render.filepath = "/renders/shot_"
        return render

    def test_failed_render_restores_settings(self, camera_handler, video_output_scene, tmp_path):
        import bpy

        render = self._scene(video_output_scene)
        bpy.ops.render.render.side_effect = RuntimeError("render cancelled")
        try:
            with pytest.raises(RuntimeError):
                camera_handler.handle_capture_viewport(
                    {"filepath": str(tmp_path / "shot.png"), "width": 64, "height": 64}
                )
        finally:
            bpy.ops.render.render.side_effect = None

        assert (render.resolution_x, render.resolution_y) == (1920, 1080)
        assert render.resolution_percentage == 50
        assert render.filepath == "/renders/shot_"
        assert video_output_scene.media_type == "VIDEO"
        assert video_output_scene.file_format == "FFMPEG"

    def test_failed_render_removes_temp_dir(self, camera_handler, video_output_scene, tmp_path,
                                            monkeypatch):
        import bpy

        self._scene(video_output_scene)
        temp_dir = tmp_path / "capture"
        temp_dir.mkdir()
        monkeypatch.setattr(camera_handler.tempfile, "mkdtemp", lambda: str(temp_dir))
        bpy.ops.render.render.side_effect = RuntimeError("render cancelled")
        try:
            with pytest.raises(RuntimeError):
                camera_handler.handle_capture_viewport({"width": 64, "height": 64})
        finally:
            bpy.ops.render.render.side_effect = None

        assert not temp_dir.exists()

    def test_temp_dir_removed_even_with_leftover_files(self, camera_handler, video_output_scene,
                                                       tmp_path, monkeypatch):
        """Cleanup removes the whole folder, not just the one PNG it expects."""
        import bpy

        self._scene(video_output_scene)
        temp_dir = tmp_path / "capture"
        temp_dir.mkdir()
        monkeypatch.setattr(camera_handler.tempfile, "mkdtemp", lambda: str(temp_dir))

        def render(**kwargs):
            (temp_dir / "viewport_capture.png").write_bytes(b"png")
            (temp_dir / "viewport_capture.png.tmp").write_bytes(b"partial")

        bpy.ops.render.render.side_effect = render
        try:
            result = camera_handler.handle_capture_viewport({"width": 64, "height": 64})
        finally:
            bpy.ops.render.render.side_effect = None

        assert result["format"] == "png"
        assert not temp_dir.exists()
