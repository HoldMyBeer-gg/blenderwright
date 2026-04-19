"""Tests for addon.handlers.objects — polygon prism and threaded shaft geometry math.

Validates the non-trivial logic in handle_create_polygon_prism and
handle_create_threaded_shaft: Screw-modifier parameter derivation, V-profile
vertex positions, auto thread-depth computation, and iteration count.
"""

import math
import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_objects_handler():
    """Load addon.handlers.objects without triggering addon/__init__.py."""
    mock_dispatcher = MagicMock()
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "objects.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.objects", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.objects"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def objects_handler():
    return _load_objects_handler()


# ---------------------------------------------------------------------------
# handle_create_polygon_prism
# ---------------------------------------------------------------------------


class TestCreatePolygonPrism:
    def test_passes_vertices_to_cylinder_add(self, objects_handler):
        """Hex prism calls primitive_cylinder_add(vertices=6)."""
        import bpy
        bpy.reset_mock()

        mock_obj = MagicMock()
        mock_obj.name = "Cylinder"
        mock_obj.type = "MESH"
        mock_obj.location = [0, 0, 0]
        bpy.context.active_object = mock_obj

        result = objects_handler.handle_create_polygon_prism({
            "sides": 6,
            "radius": 1.5,
            "depth": 0.8,
            "name": "Hex",
            "location": (0, 0, 0),
            "rotation": (0, 0, 0),
            "scale": (1, 1, 1),
        })

        call_kwargs = bpy.ops.mesh.primitive_cylinder_add.call_args.kwargs
        assert call_kwargs["vertices"] == 6
        assert call_kwargs["radius"] == 1.5
        assert call_kwargs["depth"] == 0.8
        assert result["sides"] == 6

    def test_applies_custom_name(self, objects_handler):
        import bpy
        bpy.reset_mock()

        mock_obj = MagicMock()
        mock_obj.name = "Hex"
        mock_obj.type = "MESH"
        mock_obj.location = [0, 0, 0]
        bpy.context.active_object = mock_obj

        objects_handler.handle_create_polygon_prism({
            "sides": 6, "radius": 1.0, "depth": 2.0, "name": "MyHex",
            "location": (0, 0, 0), "rotation": (0, 0, 0), "scale": (1, 1, 1),
        })
        assert mock_obj.name == "MyHex"

    def test_empty_name_skips_rename(self, objects_handler):
        import bpy
        bpy.reset_mock()

        mock_obj = MagicMock()
        mock_obj.name = "Cylinder"
        mock_obj.type = "MESH"
        mock_obj.location = [0, 0, 0]
        bpy.context.active_object = mock_obj
        original_name = mock_obj.name

        objects_handler.handle_create_polygon_prism({
            "sides": 6, "radius": 1.0, "depth": 2.0, "name": "",
            "location": (0, 0, 0), "rotation": (0, 0, 0), "scale": (1, 1, 1),
        })
        # name attribute should not have been reassigned
        assert mock_obj.name == original_name


# ---------------------------------------------------------------------------
# handle_create_threaded_shaft
# ---------------------------------------------------------------------------


def _setup_threaded_shaft_mocks(objects_handler):
    """Wire mocks for the solid-core + helical-ridge construction pipeline.

    Models: one primitive_cylinder_add call (core) + two primitive_cube_add
    calls (top and bottom trim cutters). Each add call sets a distinct mock
    as active_object. Multiple modifier.new calls on the core stack
    (1 boolean union for ridge, then 1 difference per trim cutter).
    """
    import bpy
    bpy.reset_mock()

    captured = {"trim_cube_locations": []}

    mock_core = MagicMock()
    mock_core.name = "Cylinder"
    mock_core.data = MagicMock()
    mock_core.data.name = "Cylinder_mesh"

    mock_core_bool = MagicMock()
    mock_core_bool.name = "Threads"
    mock_trim_mods = [MagicMock(), MagicMock()]
    mock_trim_mods[0].name = "top_trim"
    mock_trim_mods[1].name = "bot_trim"
    # modifier.new gets called 3 times on the core: UNION, then two DIFFERENCE.
    mock_core.modifiers.new.side_effect = [
        mock_core_bool, mock_trim_mods[0], mock_trim_mods[1],
    ]

    mock_trim_cubes = [MagicMock(), MagicMock()]
    mock_trim_cubes[0].name = "top_cube"
    mock_trim_cubes[1].name = "bot_cube"

    def _cyl_add_side_effect(*args, **kwargs):
        captured["core_add_kwargs"] = kwargs
        bpy.context.active_object = mock_core

    def _cube_add_side_effect(*args, **kwargs):
        captured["trim_cube_locations"].append(kwargs.get("location"))
        idx = len(captured["trim_cube_locations"]) - 1
        if idx < len(mock_trim_cubes):
            bpy.context.active_object = mock_trim_cubes[idx]

    bpy.ops.mesh.primitive_cylinder_add.side_effect = _cyl_add_side_effect
    bpy.ops.mesh.primitive_cube_add.side_effect = _cube_add_side_effect
    bpy.context.active_object = mock_core  # seed before first op

    # from_pydata captures the ridge triangular profile.
    def _from_pydata(verts, edges, faces):
        captured["ridge_verts"] = list(verts)
        captured["ridge_edges"] = list(edges)
        captured["ridge_faces"] = list(faces)

    mock_ridge_mesh = MagicMock()
    mock_ridge_mesh.from_pydata.side_effect = _from_pydata
    bpy.data.meshes.new.return_value = mock_ridge_mesh

    mock_ridge = MagicMock()
    mock_ridge.name = "ridge"
    mock_ridge_screw = MagicMock()
    mock_ridge_screw.name = "Screw"
    mock_ridge.modifiers.new.return_value = mock_ridge_screw
    bpy.data.objects.new.return_value = mock_ridge

    return {
        "captured": captured,
        "core": mock_core,
        "ridge": mock_ridge,
        "ridge_screw": mock_ridge_screw,
        "core_bool": mock_core_bool,
        "trim_mods": mock_trim_mods,
        "trim_cubes": mock_trim_cubes,
    }


class TestCreateThreadedShaft:
    def test_ridge_profile_is_edges_only_triangle(self, objects_handler):
        """Ridge is a closed triangle loop of EDGES only (no face). A filled
        face makes Screw stamp the triangle at every rotation step, creating
        interior divider faces that break manifoldness. Edges-only produces
        just the 3 outer walls of a triangular tube, which fill_holes caps."""
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "Shaft", "location": (0, 0, 0),
        })
        captured = h["captured"]
        assert len(captured["ridge_verts"]) == 3
        assert captured["ridge_faces"] == []
        # Edges form a closed triangle (order-independent).
        assert len(captured["ridge_edges"]) == 3
        edge_set = {frozenset(e) for e in captured["ridge_edges"]}
        assert edge_set == {frozenset({0, 1}), frozenset({1, 2}), frozenset({2, 0})}

    def test_ridge_peak_at_major_radius(self, objects_handler):
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "Shaft", "location": (0, 0, 0),
        })
        verts = h["captured"]["ridge_verts"]
        # Middle vert of the triangle is the thread peak at major radius.
        assert verts[1][0] == pytest.approx(1.5)
        # Peak sits at pitch/2 axially.
        assert verts[1][2] == pytest.approx(0.25)

    def test_ridge_base_corners_at_minor_radius(self, objects_handler):
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "Shaft", "location": (0, 0, 0),
        })
        verts = h["captured"]["ridge_verts"]
        minor_r = 1.5 - 0.27
        assert verts[0][0] == pytest.approx(minor_r)
        assert verts[2][0] == pytest.approx(minor_r)

    def test_core_cylinder_has_minor_radius(self, objects_handler):
        """Core cylinder is the shaft body at minor_r — the V ridge adds the
        thread peaks up to major_r via the boolean union."""
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "Shaft", "location": (0, 0, 0),
        })
        kwargs = h["captured"]["core_add_kwargs"]
        assert kwargs["radius"] == pytest.approx(1.5 - 0.27)

    def test_core_cylinder_spans_exact_length(self, objects_handler):
        """Core is built at exactly the requested length, centered so its base
        sits at location.z. Thread ridges overhang by half_base on each end —
        cosmetic, and avoids the boolean trim failures that collapsed the mesh
        or erased thread peaks."""
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "Shaft", "location": (0, 0, 0),
        })
        kwargs = h["captured"]["core_add_kwargs"]
        assert kwargs["depth"] == pytest.approx(10.0)
        assert kwargs["location"][2] == pytest.approx(5.0)

    def test_no_trim_cubes_created(self, objects_handler):
        """The trim-boolean step was removed. No primitive_cube_add calls
        should happen during threaded shaft construction."""
        import bpy
        _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "Shaft", "location": (0, 0, 0),
        })
        assert bpy.ops.mesh.primitive_cube_add.call_count == 0

    def test_only_ridge_is_removed(self, objects_handler):
        """Only the ridge helper is removed — no trim cubes any more."""
        import bpy
        _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "Shaft", "location": (0, 0, 0),
        })
        assert bpy.data.objects.remove.call_count == 1

    def test_core_cylinder_vertices_match_segments(self, objects_handler):
        """Rotational resolution of the core must equal that of the ridge so
        their boolean-union seam aligns cleanly."""
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 48,
            "name": "Shaft", "location": (0, 0, 0),
        })
        assert h["captured"]["core_add_kwargs"]["vertices"] == 48

    def test_auto_thread_depth_when_zero(self, objects_handler):
        """thread_depth=0 triggers auto-compute: pitch * 0.54."""
        _setup_threaded_shaft_mocks(objects_handler)
        result = objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.0, "segments": 32,
            "name": "Shaft", "location": (0, 0, 0),
        })
        assert result["thread_depth"] == pytest.approx(0.5 * 0.54)

    def test_screw_modifier_params(self, objects_handler):
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 48,
            "name": "Shaft", "location": (0, 0, 0),
        })
        screw = h["ridge_screw"]
        assert screw.axis == "Z"
        assert screw.angle == pytest.approx(2 * math.pi)
        assert screw.screw_offset == pytest.approx(0.5)
        assert screw.steps == 48
        assert screw.render_steps == 48

    def test_screw_modifier_merges_iteration_seams(self, objects_handler):
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "Shaft", "location": (0, 0, 0),
        })
        assert h["ridge_screw"].use_merge_vertices is True
        assert h["ridge_screw"].merge_threshold > 0

    def test_iterations_default_runout_is_zero(self, objects_handler):
        """Default thread_runout (-1 sentinel) resolves to 0 — threads run
        full length for FDM printability. A smooth runout creates a weak
        neck at minor_r that snaps under torque."""
        h = _setup_threaded_shaft_mocks(objects_handler)
        # length=10, pitch=0.5, thread_depth=0.27, runout=0 (auto).
        # allowed = (10 - 0 - 0.25 - 0.156) / 0.5 = 19.188. iterations = 19.
        result = objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "thread_runout": -1.0,
            "name": "Shaft", "location": (0, 0, 0),
        })
        assert h["ridge_screw"].iterations == 19
        assert result["iterations"] == 19

    def test_iterations_with_no_runout(self, objects_handler):
        """thread_runout=0 allows threads to reach as far up as the last
        full iteration fits."""
        h = _setup_threaded_shaft_mocks(objects_handler)
        # length=10, pitch=0.5, thread_depth=0.27, runout=0.
        # allowed = (10 - 0 - 0.25 - 0.156) / 0.5 = 19.188. iterations = 19.
        result = objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "thread_runout": 0.0,
            "name": "Shaft", "location": (0, 0, 0),
        })
        assert h["ridge_screw"].iterations == 19
        assert result["iterations"] == 19

    def test_iterations_explicit_runout(self, objects_handler):
        """Explicit larger runout forces fewer iterations."""
        h = _setup_threaded_shaft_mocks(objects_handler)
        # length=10, pitch=0.5, thread_depth=0.27, runout=2.0.
        # allowed = (10 - 2 - 0.25 - 0.156) / 0.5 = 15.188. iterations = 15.
        result = objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "thread_runout": 2.0,
            "name": "Shaft", "location": (0, 0, 0),
        })
        assert h["ridge_screw"].iterations == 15
        assert result["iterations"] == 15

    def test_iterations_never_below_one(self, objects_handler):
        """Even when runout math would give 0 or negative iterations, always
        produce at least 1 thread so the output isn't a plain cylinder."""
        h = _setup_threaded_shaft_mocks(objects_handler)
        # runout nearly consumes the length; math would give iterations ~= 0.
        result = objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 1.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "thread_runout": 0.9,
            "name": "Shaft", "location": (0, 0, 0),
        })
        assert h["ridge_screw"].iterations >= 1
        assert result["iterations"] >= 1

    def test_boolean_union_uses_exact_solver(self, objects_handler):
        """Fast solver struggles on coplanar cases; EXACT is required for the
        core/ridge union to stay manifold at thread roots."""
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "Shaft", "location": (0, 0, 0),
        })
        bool_mod = h["core_bool"]
        assert bool_mod.operation == "UNION"
        assert bool_mod.object is h["ridge"]
        assert bool_mod.solver == "EXACT"

    def test_ridge_consumed_after_union(self, objects_handler):
        """The ridge helper object must be deleted — otherwise the scene
        keeps a duplicate mesh sitting inside the shaft."""
        import bpy
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "Shaft", "location": (0, 0, 0),
        })
        # Ridge is the first object removed (before the trim cubes).
        first_remove_call = bpy.data.objects.remove.call_args_list[0]
        assert first_remove_call.args[0] is h["ridge"]
        assert first_remove_call.kwargs == {"do_unlink": True}

    def test_core_renamed_to_user_name(self, objects_handler):
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "MyShaft", "location": (0, 0, 0),
        })
        assert h["core"].name == "MyShaft"

    def test_default_name_when_empty(self, objects_handler):
        h = _setup_threaded_shaft_mocks(objects_handler)
        objects_handler.handle_create_threaded_shaft({
            "diameter": 3.0, "length": 10.0, "pitch": 0.5,
            "thread_depth": 0.27, "segments": 32,
            "name": "", "location": (0, 0, 0),
        })
        assert h["core"].name == "ThreadedShaft"
