"""Handler tests for UV island operations and texel density."""

import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load_handler():
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "addon", "handlers", "uv.py")
    spec = importlib.util.spec_from_file_location("addon.handlers.uv", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.uv"] = mod
    spec.loader.exec_module(mod)
    return mod


def _quad_mesh(size=2.0, uv_size=0.5, scale=1.0):
    """One square face, size x size in local units, UVs a uv_size square."""
    s = size / 2
    verts = [SimpleNamespace(co=(x, y, 0.0)) for x, y in ((-s, -s), (s, -s), (s, s), (-s, s))]
    uv = [SimpleNamespace(uv=[u, v]) for u, v in ((0, 0), (uv_size, 0), (uv_size, uv_size),
                                                   (0, uv_size))]
    poly = SimpleNamespace(vertices=[0, 1, 2, 3], loop_indices=[0, 1, 2, 3])
    mesh = SimpleNamespace(vertices=verts, polygons=[poly],
                           uv_layers=SimpleNamespace(active=SimpleNamespace(data=uv)),
                           update=MagicMock())
    return SimpleNamespace(name="Tile", type="MESH", mode="OBJECT", data=mesh,
                           matrix_world=SimpleNamespace(scale=scale))


@pytest.fixture
def h(monkeypatch):
    import bpy

    mod = _load_handler()
    obj = _quad_mesh()
    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(get={"Tile": obj}.get))
    monkeypatch.setattr(mod, "_world_coords", lambda o: [
        tuple(c * o.matrix_world.scale for c in v.co) for v in o.data.vertices])
    mod._obj = obj
    return mod


class TestTexelDensity:
    def test_measures_pixels_per_metre(self, h):
        # A 2 m square covered by half the UV width: 0.5 * 1024 px over 2 m = 256 px/m
        result = h.handle_get_texel_density({"object_name": "Tile", "texture_size": 1024})
        assert result["density"] == pytest.approx(256.0)
        assert result["surface_area"] == pytest.approx(4.0)
        assert result["uv_coverage"] == pytest.approx(0.25)

    def test_world_scale_counts(self, h):
        h._obj.matrix_world.scale = 2.0
        result = h.handle_get_texel_density({"object_name": "Tile", "texture_size": 1024})
        assert result["density"] == pytest.approx(128.0)

    def test_set_scales_uvs_to_the_target(self, h):
        result = h.handle_set_texel_density({"object_name": "Tile", "density": 512.0,
                                             "texture_size": 1024})
        assert result["before"] == pytest.approx(256.0)
        assert result["after"] == pytest.approx(512.0)
        again = h.handle_get_texel_density({"object_name": "Tile", "texture_size": 1024})
        assert again["density"] == pytest.approx(512.0)

    def test_no_uvs_is_explained(self, h):
        h._obj.data.uv_layers.active = None
        with pytest.raises(ValueError, match="UV"):
            h.handle_get_texel_density({"object_name": "Tile", "texture_size": 1024})


class TestIslandOperation:
    @pytest.mark.parametrize("params, op, kwargs", [
        ({"operation": "AVERAGE_SCALE"}, "average_islands_scale", {}),
        ({"operation": "MINIMIZE_STRETCH", "iterations": 30}, "minimize_stretch",
         {"iterations": 30}),
        ({"operation": "ALIGN_ROTATION"}, "align_rotation", {"method": "AUTO"}),
        ({"operation": "RANDOMIZE", "rotation": 0.5, "scale_variation": 0.2, "offset": 0.1,
          "seed": 4}, "randomize_uv_transform",
         {"rot": 0.5, "scale": (0.2, 0.2), "scale_even": True, "loc": (0.1, 0.1),
          "random_seed": 4}),
        ({"operation": "SEAMS_FROM_ISLANDS"}, "seams_from_islands", {}),
        ({"operation": "ARRANGE", "margin": 0.02}, "arrange_islands", {"margin": 0.02}),
        ({"operation": "WELD", "threshold": 0.001}, "remove_doubles", {"threshold": 0.001}),
    ])
    def test_runs_the_operator_with_uv_sync_on(self, h, monkeypatch, params, op, kwargs):
        import bpy

        seen = {}
        ts = SimpleNamespace(use_uv_select_sync=False)
        monkeypatch.setattr(bpy.context, "scene", SimpleNamespace(tool_settings=ts))
        monkeypatch.setattr(h, "_enter_uv_edit", lambda obj, selection: None)
        monkeypatch.setattr(bpy.ops.object, "mode_set", MagicMock())
        uv_ops = MagicMock()
        getattr(uv_ops, op).side_effect = lambda **kw: seen.update(
            kw=kw, sync=ts.use_uv_select_sync) or {"FINISHED"}
        monkeypatch.setattr(bpy.ops, "uv", uv_ops)

        h.handle_uv_island_operation({"object_name": "Tile", "selection": "ALL", **params})
        assert seen["kw"] == kwargs
        assert seen["sync"] is True
        assert ts.use_uv_select_sync is False  # restored

    def test_unknown_operation_refused(self, h):
        with pytest.raises(ValueError):
            h.handle_uv_island_operation({"object_name": "Tile", "operation": "__class__"})


def test_world_matrix_is_refreshed_before_measuring(monkeypatch):
    """Blender only recomputes matrix_world on a scene update; a scale set in the
    previous call is invisible until then."""
    import bpy

    mod = _load_handler()
    obj = _quad_mesh()
    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(get={"Tile": obj}.get))
    pending = {"scale": 2.0}

    class Matrix:
        def __matmul__(self, co):
            return tuple(c * obj.matrix_world.applied for c in co)

    obj.matrix_world = Matrix()
    obj.matrix_world.applied = 1.0
    monkeypatch.setattr(bpy.context, "view_layer", SimpleNamespace(
        update=lambda: setattr(obj.matrix_world, "applied", pending["scale"])))
    result = mod.handle_get_texel_density({"object_name": "Tile", "texture_size": 1024})
    assert result["density"] == pytest.approx(128.0)
