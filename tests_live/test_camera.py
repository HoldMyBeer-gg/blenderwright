"""Cameras and viewport capture in a real Blender. Replaces the fake-bpy
camera handler tests. Capture draws with OpenGL, so those run with a GPU."""

import base64
import os

import pytest

from blenderwright.server import mcp

T = {x.name: x.fn for x in mcp._tool_manager.list_tools()}
NO_GPU = bool(os.environ.get("BLENDERWRIGHT_NO_GPU"))


class TestSceneCamera:
    def test_first_camera_becomes_the_scene_camera(self, scene):
        T["delete_object"]("Camera")
        result = T["create_camera"](name="Shot", location=[0, -5, 2])
        assert result["active"] is True

    def test_existing_scene_camera_is_not_stolen(self, scene):
        assert T["create_camera"](name="Second")["active"] is False


@pytest.mark.skipif(NO_GPU, reason="no GPU here: viewport capture draws with OpenGL")
class TestCapture:
    def test_png_with_the_size_asked_for(self, scene):
        result = T["capture_viewport"](width=64, height=48)
        assert (result["width"], result["height"]) == (64, 48)
        assert base64.b64decode(result["base64"])[:8] == b"\x89PNG\r\n\x1a\n"

    def test_render_resolution_is_restored(self, scene):
        T["set_render_resolution"](320, 240)
        T["capture_viewport"](width=64, height=48)
        assert T["set_render_resolution"](320, 240)["resolution_x"] == 320

    def test_after_a_video_output(self, scene):
        T["set_render_resolution"](32, 32)
        T["set_render_engine"]("CYCLES")
        T["set_render_samples"](1)
        T["render_video"](filepath=str(scene / "clip.mp4"))
        T["capture_viewport"](width=32, height=32)
        assert T["set_output_format"]("PNG")["format"] == "PNG"
