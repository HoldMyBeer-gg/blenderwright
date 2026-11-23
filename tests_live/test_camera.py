"""Cameras and viewport capture in a real Blender. Replaces the fake-bpy
camera handler tests. Capture draws with OpenGL, so those run with a GPU."""

import base64
import json
import os
import subprocess

import pytest

from blenderwright.server import mcp

T = {x.name: x.fn for x in mcp._tool_manager.list_tools()}
NO_GPU = bool(os.environ.get("BLENDERWRIGHT_NO_GPU"))
PNG = b"\x89PNG\r\n\x1a\n"


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

    def test_exr_depth_and_channels_are_left_as_they_were(self, scene):
        _open_with_output(scene, "IMAGE", "OPEN_EXR",
                          "s.image_settings.color_mode = 'RGBA'; "
                          "s.image_settings.color_depth = '32'; ")
        T["capture_viewport"](width=32, height=32)
        assert _saved_output(scene) == ["IMAGE", "OPEN_EXR", str(scene / "renders" / "shot"),
                                        "RGBA", "32"]


OUTPUT = ("r = bpy.context.scene.render; "
          "print('OUTPUT=' + json.dumps([r.image_settings.media_type, "
          "r.image_settings.file_format, r.filepath, r.image_settings.color_mode, "
          "r.image_settings.color_depth]))")


def _blender(blend, expr):
    """Run a line of Python on a .blend in a throwaway headless Blender."""
    done = subprocess.run(
        [os.environ["BLENDER"], "-b", str(blend), "--python-exit-code", "1",
         "--python-expr", "import bpy, json; " + expr],
        capture_output=True, text=True, check=True)
    return done.stdout


def _open_with_output(folder, media_type, file_format, extra=""):
    """Open the scene with this output format; return the folder renders would land in."""
    out = folder / "renders"
    out.mkdir()
    _blender(folder / "scene.blend",
             "s = bpy.context.scene.render; "
             f"s.image_settings.media_type = {media_type!r}; "
             f"s.image_settings.file_format = {file_format!r}; "
             f"s.filepath = {str(out / 'shot')!r}; {extra}"
             "bpy.ops.wm.save_mainfile()")
    T["open_file"](str(folder / "scene.blend"))
    return out


def _saved_output(folder):
    """Save the open scene and read its output settings back from the file."""
    T["save_file"](str(folder / "after.blend"))
    printed = _blender(folder / "after.blend", OUTPUT)
    return json.loads(printed.split("OUTPUT=")[1].splitlines()[0])


@pytest.mark.skipif(NO_GPU, reason="no GPU here: the viewport screenshot draws with OpenGL")
class TestFastScreenshot:
    def test_png_when_the_output_is_a_video(self, viewport):
        _open_with_output(viewport, "VIDEO", "FFMPEG")
        result = T["get_viewport_screenshot"](max_size=64)
        assert base64.b64decode(result["base64"])[:8] == PNG

    def test_video_output_is_left_as_it_was(self, viewport):
        out = _open_with_output(viewport, "VIDEO", "FFMPEG")
        T["get_viewport_screenshot"](max_size=64)
        assert _saved_output(viewport)[:2] == ["VIDEO", "FFMPEG"]
        assert _saved_output(viewport)[2] == str(out / "shot")

    def test_png_when_the_output_is_a_jpeg(self, viewport):
        _open_with_output(viewport, "IMAGE", "JPEG")
        result = T["get_viewport_screenshot"](max_size=64)
        assert base64.b64decode(result["base64"])[:8] == PNG
        assert _saved_output(viewport)[:2] == ["IMAGE", "JPEG"]

    def test_nothing_is_written_to_the_output_path(self, viewport):
        out = _open_with_output(viewport, "IMAGE", "PNG")
        T["get_viewport_screenshot"](max_size=64)
        assert list(out.iterdir()) == []

    def test_exr_depth_and_channels_are_left_as_they_were(self, viewport):
        _open_with_output(viewport, "IMAGE", "OPEN_EXR",
                          "s.image_settings.color_mode = 'RGBA'; "
                          "s.image_settings.color_depth = '32'; ")
        T["get_viewport_screenshot"](max_size=64)
        assert _saved_output(viewport)[3:] == ["RGBA", "32"]
        assert _saved_output(viewport)[:2] == ["IMAGE", "OPEN_EXR"]
