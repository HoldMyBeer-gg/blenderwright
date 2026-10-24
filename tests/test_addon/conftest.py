"""Mock bpy module for addon tests."""

import sys
from unittest.mock import MagicMock

import pytest

# Create mock bpy module before any addon imports
mock_bpy = MagicMock()
mock_bpy.app.timers.is_registered = MagicMock(return_value=False)
mock_bpy.app.timers.register = MagicMock()
mock_bpy.app.timers.unregister = MagicMock()
sys.modules["bpy"] = mock_bpy


class _Vector(tuple):
    """Enough of mathutils.Vector for handlers that build and transform one."""

    def __new__(cls, seq=(0.0, 0.0, 0.0)):
        return super().__new__(cls, tuple(float(v) for v in seq))

    x = property(lambda self: self[0])
    y = property(lambda self: self[1])
    z = property(lambda self: self[2])


if "mathutils" not in sys.modules:
    mock_mathutils = MagicMock()
    mock_mathutils.Vector = _Vector
    sys.modules["mathutils"] = mock_mathutils


if "bpy_extras" not in sys.modules:
    mock_bpy_extras = MagicMock()
    sys.modules["bpy_extras"] = mock_bpy_extras
    sys.modules["bpy_extras.anim_utils"] = mock_bpy_extras.anim_utils


class _ImageFormatSettings:
    """Blender 5.x image settings: file_format must fit the current media_type."""

    def __init__(self, media_type, file_format):
        self.media_type = media_type
        self._file_format = file_format

    @property
    def file_format(self):
        return self._file_format

    @file_format.setter
    def file_format(self, value):
        if (value == "FFMPEG") != (self.media_type == "VIDEO"):
            raise TypeError(f"enum \"{value}\" not found in media type {self.media_type}")
        self._file_format = value


@pytest.fixture
def video_output_scene():
    """A scene left on video output, as after render_video."""
    settings = _ImageFormatSettings("VIDEO", "FFMPEG")
    mock_bpy.context.scene.render.image_settings = settings
    mock_bpy.context.scene.render.filepath = "/tmp/out/"
    return settings
