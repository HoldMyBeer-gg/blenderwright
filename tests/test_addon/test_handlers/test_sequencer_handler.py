"""Unit tests for the sequencer handler: sequence discovery, sound offset, video output."""

import importlib.util
import os
import sys
from unittest.mock import MagicMock

import pytest


def _load_handler():
    """Load addon.handlers.sequencer without addon/handlers/__init__.py."""
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "sequencer.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.sequencer", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.sequencer"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def handler():
    return _load_handler()


@pytest.fixture
def scene():
    """A mock scene with an empty sequence editor at 12 fps."""
    import bpy

    scene = MagicMock()
    scene.render.fps = 12
    scene.render.fps_base = 1.0
    scene.frame_start = 1
    scene.frame_end = 60
    bpy.context.scene = scene
    return scene


def _touch(folder, *names):
    for name in names:
        (folder / name).write_bytes(b"x")


class TestSequenceFiles:
    def test_collects_the_numbered_siblings_in_order(self, handler, tmp_path):
        _touch(tmp_path, "f_0010.png", "f_0001.png", "f_0003.png")
        directory, files = handler._sequence_files(str(tmp_path / "f_0001.png"))
        assert directory == str(tmp_path)
        assert files == ["f_0001.png", "f_0003.png", "f_0010.png"]

    def test_orders_by_number_not_by_text(self, handler, tmp_path):
        _touch(tmp_path, "f_2.png", "f_10.png", "f_1.png")
        _, files = handler._sequence_files(str(tmp_path / "f_1.png"))
        assert files == ["f_1.png", "f_2.png", "f_10.png"]

    def test_ignores_other_prefixes_extensions_and_files(self, handler, tmp_path):
        _touch(tmp_path, "f_0001.png", "f_0002.png", "g_0001.png", "f_0003.jpg", "notes.txt")
        _, files = handler._sequence_files(str(tmp_path / "f_0001.png"))
        assert files == ["f_0001.png", "f_0002.png"]

    def test_starts_at_the_frame_it_was_given(self, handler, tmp_path):
        _touch(tmp_path, "f_0001.png", "f_0002.png", "f_0003.png")
        _, files = handler._sequence_files(str(tmp_path / "f_0002.png"))
        assert files == ["f_0002.png", "f_0003.png"]

    def test_an_unnumbered_image_stands_alone(self, handler, tmp_path):
        _touch(tmp_path, "poster.png", "poster2.png")
        _, files = handler._sequence_files(str(tmp_path / "poster.png"))
        assert files == ["poster.png"]

    def test_too_many_images_is_refused(self, handler, tmp_path):
        handler.MAX_SEQUENCE_IMAGES = 2
        _touch(tmp_path, "f_1.png", "f_2.png", "f_3.png")
        with pytest.raises(ValueError, match="limit"):
            handler._sequence_files(str(tmp_path / "f_1.png"))


class TestAddImageSequenceStrip:
    def test_creates_one_strip_and_appends_the_rest(self, handler, scene, tmp_path):
        _touch(tmp_path, "f_0001.png", "f_0003.png", "f_0005.png")
        strip = scene.sequence_editor.strips.new_image.return_value
        strip.name = "Launch"

        result = handler.handle_add_image_sequence_strip({
            "first_frame": str(tmp_path / "f_0001.png"),
            "name": "Launch", "channel": 1, "frame_start": 1,
        })

        scene.sequence_editor.strips.new_image.assert_called_once_with(
            "Launch", str(tmp_path / "f_0001.png"), 1, 1
        )
        assert [c.args[0] for c in strip.elements.append.call_args_list] == [
            "f_0003.png", "f_0005.png",
        ]
        assert result["images"] == 3

    def test_missing_first_frame_raises(self, handler, scene, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            handler.handle_add_image_sequence_strip({
                "first_frame": str(tmp_path / "f_0001.png"),
            })


class TestAddSoundStrip:
    def test_offset_slides_and_trims_by_the_same_frames(self, handler, scene, tmp_path):
        _touch(tmp_path, "roar.mp3")
        strip = scene.sequence_editor.strips.new_sound.return_value

        handler.handle_add_sound_strip({
            "filepath": str(tmp_path / "roar.mp3"),
            "channel": 2, "frame_start": 1, "start_offset": 3.5, "volume": 1.3,
        })

        # 3.5 seconds at 12 fps is 42 frames
        assert strip.left_handle_offset == 42.0
        assert strip.content_start == 1 - 42.0
        assert strip.volume == 1.3

    def test_no_offset_leaves_the_strip_where_blender_put_it(self, handler, scene, tmp_path):
        _touch(tmp_path, "roar.mp3")
        strip = scene.sequence_editor.strips.new_sound.return_value
        strip.left_handle_offset = 0

        handler.handle_add_sound_strip({"filepath": str(tmp_path / "roar.mp3")})

        assert strip.left_handle_offset == 0

    def test_name_defaults_to_the_file_stem(self, handler, scene, tmp_path):
        _touch(tmp_path, "roar.mp3")
        handler.handle_add_sound_strip({"filepath": str(tmp_path / "roar.mp3")})
        assert scene.sequence_editor.strips.new_sound.call_args[0][0] == "roar"

    def test_missing_file_raises(self, handler, scene, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            handler.handle_add_sound_strip({"filepath": str(tmp_path / "roar.mp3")})


class TestRemoveAndList:
    def test_remove_unknown_strip_raises(self, handler, scene):
        scene.sequence_editor.strips.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            handler.handle_remove_strip({"strip_name": "Ghost"})

    def test_remove_calls_blender(self, handler, scene):
        strip = scene.sequence_editor.strips.get.return_value
        strip.name = "Launch"
        result = handler.handle_remove_strip({"strip_name": "Launch"})
        scene.sequence_editor.strips.remove.assert_called_once_with(strip)
        assert result == {"removed": "Launch"}

    def test_list_without_an_editor_is_empty(self, handler, scene):
        scene.sequence_editor = None
        assert handler.handle_list_strips({}) == []

    def test_list_reports_inclusive_last_frame(self, handler, scene):
        strip = MagicMock()
        strip.name = "Launch"
        strip.type = "IMAGE"
        strip.channel = 1
        strip.left_handle = 1
        strip.right_handle = 61
        scene.sequence_editor.strips = [strip]
        assert handler.handle_list_strips({}) == [{
            "name": "Launch", "type": "IMAGE", "channel": 1, "frame_start": 1, "frame_end": 60,
        }]


class TestOlderBlender:
    def test_an_editor_without_strips_is_refused_clearly(self, handler, scene):
        """Before 5.1 the collection and the timing names were different."""
        scene.sequence_editor = MagicMock(spec=["sequences"])
        with pytest.raises(ValueError, match="5.1 or later"):
            handler.handle_add_sound_strip({"filepath": __file__})


class TestRenderVideo:
    def _prime(self, scene):
        render = scene.render
        render.filepath = "/original/path_"
        render.image_settings.media_type = "IMAGE"
        render.image_settings.file_format = "PNG"
        render.ffmpeg.format = "MKV"
        render.ffmpeg.codec = "AV1"
        render.ffmpeg.constant_rate_factor = "MEDIUM"
        render.ffmpeg.audio_codec = "NONE"
        return render

    def test_renders_with_video_settings_then_restores(self, handler, scene):
        import bpy

        render = self._prime(scene)
        seen = {}

        def capture(**kwargs):
            seen["media_type"] = render.image_settings.media_type
            seen["file_format"] = render.image_settings.file_format
            seen["format"] = render.ffmpeg.format
            seen["codec"] = render.ffmpeg.codec
            seen["audio"] = render.ffmpeg.audio_codec
            seen["quality"] = render.ffmpeg.constant_rate_factor
            seen["filepath"] = render.filepath
            seen["kwargs"] = kwargs

        bpy.ops.render.render = MagicMock(side_effect=capture)

        result = handler.handle_render_video({
            "filepath": "/out/launch.mp4", "container": "MPEG4",
            "quality": "HIGH", "audio_codec": "AAC",
        })

        assert seen == {
            "media_type": "VIDEO", "file_format": "FFMPEG", "format": "MPEG4",
            "codec": "H264", "audio": "AAC", "quality": "HIGH",
            "filepath": "/out/launch.mp4", "kwargs": {"animation": True},
        }
        assert render.filepath == "/original/path_"
        assert render.image_settings.media_type == "IMAGE"
        assert render.image_settings.file_format == "PNG"
        assert render.ffmpeg.format == "MKV"
        assert render.ffmpeg.codec == "AV1"
        assert render.ffmpeg.audio_codec == "NONE"
        assert result["fps"] == 12
        assert result["rendered"] is True

    def test_settings_are_restored_when_the_render_fails(self, handler, scene):
        import bpy

        render = self._prime(scene)
        bpy.ops.render.render = MagicMock(side_effect=RuntimeError("encoder exploded"))

        with pytest.raises(RuntimeError):
            handler.handle_render_video({"filepath": "/out/launch.mp4"})

        assert render.filepath == "/original/path_"
        assert render.image_settings.file_format == "PNG"
        assert render.image_settings.media_type == "IMAGE"

    def test_webm_uses_the_webm_codec(self, handler, scene):
        import bpy

        render = self._prime(scene)
        seen = {}
        bpy.ops.render.render = MagicMock(
            side_effect=lambda **kw: seen.setdefault("codec", render.ffmpeg.codec)
        )
        handler.handle_render_video({
            "filepath": "/out/launch.webm", "container": "WEBM", "audio_codec": "OPUS",
        })
        assert seen["codec"] == "WEBM"

    def test_unknown_container_raises_before_touching_settings(self, handler, scene):
        render = self._prime(scene)
        with pytest.raises(ValueError, match="container"):
            handler.handle_render_video({"filepath": "/out/x.avi", "container": "AVI"})
        assert render.image_settings.file_format == "PNG"
