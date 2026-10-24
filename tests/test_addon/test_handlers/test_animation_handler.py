"""Tests for animation handler: F-curves live in action channelbags since 5.0."""

import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load_handler():
    """Load addon.handlers.animation without addon/handlers/__init__.py."""
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "animation.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.animation", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.animation"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def handler():
    return _load_handler()


def _keyframe(frame, value):
    return SimpleNamespace(co=(frame, value), interpolation="BEZIER")


def _animated_object(fcurves):
    """Mock an object whose action slot holds the given F-curves."""
    import bpy
    from bpy_extras import anim_utils

    action = SimpleNamespace()  # 5.x actions have no .fcurves
    obj = MagicMock()
    obj.name = "Cube"
    obj.animation_data.action = action
    bpy.data.objects.get = MagicMock(return_value=obj)
    anim_utils.action_get_channelbag_for_slot.return_value = SimpleNamespace(fcurves=fcurves)
    return obj


def _fcurve(data_path, index, keyframes):
    return SimpleNamespace(data_path=data_path, array_index=index, keyframe_points=keyframes)


class TestListKeyframes:
    def test_reads_fcurves_from_the_channelbag(self, handler):
        _animated_object([_fcurve("location", 0, [_keyframe(10, 2.0), _keyframe(1, 0.0)])])

        keyframes = handler.handle_list_keyframes({"object_name": "Cube"})

        assert [k["frame"] for k in keyframes] == [1, 10]
        assert keyframes[0]["data_path"] == "location"

    def test_slot_without_channelbag_has_no_keyframes(self, handler):
        from bpy_extras import anim_utils

        _animated_object([])
        anim_utils.action_get_channelbag_for_slot.return_value = None

        assert handler.handle_list_keyframes({"object_name": "Cube"}) == []


class TestSetInterpolation:
    def test_updates_only_the_matching_channel(self, handler):
        x = [_keyframe(1, 0.0), _keyframe(10, 1.0)]
        y = [_keyframe(1, 0.0)]
        _animated_object([_fcurve("location", 0, x), _fcurve("location", 1, y)])

        result = handler.handle_set_interpolation({
            "object_name": "Cube", "data_path": "location[0]", "interpolation": "LINEAR",
        })

        assert result["keyframes_updated"] == 2
        assert [k.interpolation for k in x] == ["LINEAR", "LINEAR"]
        assert y[0].interpolation == "BEZIER"

    def test_no_matching_keyframes_raises(self, handler):
        _animated_object([_fcurve("rotation_euler", 0, [_keyframe(1, 0.0)])])

        with pytest.raises(ValueError):
            handler.handle_set_interpolation({
                "object_name": "Cube", "data_path": "location", "interpolation": "LINEAR",
            })
