"""Handler tests for focus_on_object.

object.select_all fails its poll outside object mode, so focusing from
sculpt mode raised. 5.2.3 live.
"""

import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load_handler():
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "addon", "handlers", "viewport.py")
    spec = importlib.util.spec_from_file_location("addon.handlers.viewport", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.viewport"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def scene(monkeypatch):
    import bpy

    mod = _load_handler()
    head = SimpleNamespace(name="Head", mode="OBJECT", select_set=MagicMock())
    other = SimpleNamespace(name="Other", mode="OBJECT", select_set=MagicMock())
    layer = SimpleNamespace(objects=SimpleNamespace(active=other))
    monkeypatch.setattr(bpy.data, "objects", {"Head": head, "Other": other})
    monkeypatch.setattr(bpy.context, "view_layer", layer, raising=False)
    monkeypatch.setattr(bpy.context, "selected_objects", [other], raising=False)

    def select_all(action):
        if bpy.context.object.mode != "OBJECT":
            raise RuntimeError("Operator bpy.ops.object.select_all.poll() failed")

    monkeypatch.setattr(bpy.ops.object, "select_all", select_all)
    modes = []

    def mode_set(mode):
        modes.append(mode)
        bpy.context.object.mode = mode

    monkeypatch.setattr(bpy.ops.object, "mode_set", mode_set)
    frames = MagicMock()
    monkeypatch.setattr(bpy.ops.view3d, "view_selected", frames)
    region_3d = SimpleNamespace(view_location=None, view_distance=None)
    monkeypatch.setattr(mod, "_get_3d_viewport_area",
                        lambda: (SimpleNamespace(regions=[object()]),
                                 SimpleNamespace(region_3d=region_3d)))
    monkeypatch.setattr(mod, "_world_bounds",
                        lambda obj: ((3.0, 2.0, -1.0), (5.0, 4.0, 1.0)), raising=False)
    head.region_3d = region_3d
    return mod, head, other, layer, modes, frames


class TestFocusOnObject:
    def test_while_sculpting_it_frames_without_leaving_the_mode(self, scene, monkeypatch):
        import bpy

        mod, head, other, layer, modes, frames = scene
        head.mode = "SCULPT"
        layer.objects.active = head
        monkeypatch.setattr(bpy.context, "object", head, raising=False)
        mod.handle_focus_on_object({"object_name": "Head"})
        assert modes == [] and head.mode == "SCULPT"
        # view_selected in sculpt mode frames the last stroke, not the object
        frames.assert_not_called()
        assert tuple(head.region_3d.view_location) == (4.0, 3.0, 0.0)
        assert head.region_3d.view_distance > 2.0

    def test_from_object_mode_it_selects_only_the_target(self, scene, monkeypatch):
        import bpy

        mod, head, other, layer, modes, frames = scene
        monkeypatch.setattr(bpy.context, "object", other, raising=False)
        mod.handle_focus_on_object({"object_name": "Head"})
        other.select_set.assert_called_with(False)
        head.select_set.assert_called_with(True)
        assert layer.objects.active is head
        frames.assert_called_once()

    def test_sculpting_another_object_leaves_that_mode_first(self, scene, monkeypatch):
        import bpy

        mod, head, other, layer, modes, frames = scene
        other.mode = "SCULPT"
        monkeypatch.setattr(bpy.context, "object", other, raising=False)
        mod.handle_focus_on_object({"object_name": "Head"})
        assert modes == ["OBJECT"] and layer.objects.active is head
