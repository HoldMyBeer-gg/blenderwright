"""Handler tests for symmetrize, bisect and the built-in loop tools."""

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
                        "addon", "handlers", "mesh_editing.py")
    spec = importlib.util.spec_from_file_location("addon.handlers.mesh_editing", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.mesh_editing"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def h(monkeypatch):
    import bpy

    mod = _load_handler()
    obj = SimpleNamespace(name="Pipe", type="MESH", mode="OBJECT",
                          data=SimpleNamespace(vertices=[0] * 8))
    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(get={"Pipe": obj}.get))
    entered = []
    monkeypatch.setattr(mod, "_ensure_object_mode", lambda: None)
    monkeypatch.setattr(mod, "_enter_edit", lambda o, sel="ALL": entered.append(sel))
    mesh_ops = MagicMock()
    for op in ("symmetrize", "bisect", "circularize", "space_edge_loops_evenly", "flatten"):
        getattr(mesh_ops, op).return_value = {"FINISHED"}
    monkeypatch.setattr(bpy.ops, "mesh", mesh_ops)
    monkeypatch.setattr(bpy.ops.object, "mode_set", MagicMock())
    mod._entered = entered
    return mod


def test_symmetrize(h):
    import bpy

    h.handle_symmetrize_mesh({"object_name": "Pipe", "direction": "POSITIVE_Y",
                              "threshold": 0.001, "selection": "ALL"})
    bpy.ops.mesh.symmetrize.assert_called_once_with(direction="POSITIVE_Y", threshold=0.001)
    assert h._entered == ["ALL"]


def test_bisect(h):
    import bpy

    h.handle_bisect_mesh({"object_name": "Pipe", "plane_point": [0, 0, 5],
                          "plane_normal": [0, 0, 1], "clear_outer": True, "fill": True})
    bpy.ops.mesh.bisect.assert_called_once_with(
        plane_co=(0, 0, 5), plane_no=(0, 0, 1), clear_inner=False, clear_outer=True,
        use_fill=True)


@pytest.mark.parametrize("params, op, kwargs", [
    ({"operation": "CIRCLE", "factor": 0.8}, "circularize", {"factor": 0.8}),
    ({"operation": "CIRCLE", "factor": 1.0, "radius": 0.5}, "circularize",
     {"factor": 1.0, "use_custom_radius": True, "custom_radius": 0.5}),
    ({"operation": "SPACE", "factor": 1.0}, "space_edge_loops_evenly", {"factor": 1.0}),
    ({"operation": "FLATTEN", "factor": 1.0}, "flatten", {"factor": 1.0}),
])
def test_loop_tools(h, params, op, kwargs):
    import bpy

    h.handle_loop_tools({"object_name": "Pipe", "selection": "CURRENT", **params})
    getattr(bpy.ops.mesh, op).assert_called_once_with(**kwargs)
    assert h._entered == ["CURRENT"]


def test_unknown_loop_operation_refused(h):
    with pytest.raises(ValueError):
        h.handle_loop_tools({"object_name": "Pipe", "operation": "__class__"})


def test_unknown_symmetrize_direction_refused(h):
    with pytest.raises(ValueError):
        h.handle_symmetrize_mesh({"object_name": "Pipe", "direction": "UP"})


def test_cancelled_operator_raises(h):
    import bpy

    bpy.ops.mesh.circularize.return_value = {"CANCELLED"}
    with pytest.raises(RuntimeError):
        h.handle_loop_tools({"object_name": "Pipe", "operation": "CIRCLE", "factor": 1.0})
