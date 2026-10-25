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
