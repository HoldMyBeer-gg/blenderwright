"""Tests for the 3D Print Toolbox handler.

The toolbox is a bundled Blender extension, not part of bpy, so every path
here has to cope with it being absent or disabled. It is worth wrapping
rather than reimplementing because it catches three defects that a mesh can
carry while still reporting as manifold, watertight and non-degenerate:

  Bad Contiguous Edges - a shell whose normals are consistent with each other
      but collectively point inward. recalc_face_normals leaves it alone and
      the slicer rejects it as reversed faces.
  Intersect Faces      - the surface passing through itself.
  Thin Faces           - walls below the nozzle width, which slice away.

Each check operator replaces the stored report with only its own rows, and
Shells is only produced by check_all, so a subset of checks has to be merged
across calls. That is what most of these tests pin.
"""

import os
import sys
import math
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_print3d_handler():
    mock_dispatcher = MagicMock()
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher

    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "addon", "handlers", "print3d.py"
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.print3d", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.print3d"] = mod
    spec.loader.exec_module(mod)
    # The handler bound the mock bpy that tests/test_addon/conftest.py put in
    # sys.modules, and that object is shared by every addon test. Give this
    # module a private one so wiring a fake scene here cannot leak sideways.
    mod.bpy = MagicMock()
    return mod


@pytest.fixture
def print3d():
    mod = _load_print3d_handler()
    yield mod


def _make_report(rows):
    """Mimic props.get_report(): (label, count_str, indices, ...) tuples."""
    return tuple(
        (label, str(count), list(indices), "FACE", "faces", "FACESEL")
        for label, count, indices in rows
    )


def _wire_blender(print3d, report_rows, obj_name="Cube", toolbox=True):
    """Point the handler's bpy at a fake scene with a fake toolbox."""
    bpy = print3d.bpy
    obj = MagicMock()
    obj.name = obj_name
    obj.type = "MESH"
    bpy.data.objects = {obj_name: obj}

    scene = MagicMock()
    if toolbox:
        props = MagicMock()
        props.get_report.return_value = _make_report(report_rows)
        scene.print3d_toolbox = props
    else:
        del scene.print3d_toolbox
        props = None
    bpy.context.scene = scene
    bpy.context.view_layer.objects.active = None

    mesh_ops = MagicMock()
    for name in ("check_all", "check_solid", "check_intersect", "check_degenerate",
                 "check_thick", "check_sharp", "check_overhang", "check_nonplanar"):
        setattr(mesh_ops, f"print3d_{name}", MagicMock())
    bpy.ops.mesh = mesh_ops
    return obj, props, mesh_ops


ALL_ROWS = [
    ("Non-manifold Edges", 0, []),
    ("Bad Contiguous Edges", 3, [1, 2, 7]),
    ("Intersect Faces", 179, list(range(179))),
    ("Shells", 4, []),
    ("Zero Faces", 0, []),
    ("Zero Edges", 0, []),
    ("Non-flat Faces", 12, [5, 6]),
    ("Thin Faces", 22, [9]),
    ("Sharp Edges", 51, [3]),
    ("Overhang Faces", 308, [4]),
]


class TestAvailability:
    def test_missing_toolbox_raises_an_actionable_error(self, print3d):
        _wire_blender(print3d, ALL_ROWS, toolbox=False)
        with pytest.raises(RuntimeError) as exc:
            print3d.handle_check_3d_printability({"object_name": "Cube"})
        message = str(exc.value)
        assert "3D Print Toolbox" in message
        assert "enable" in message.lower()

    def test_available_reports_true(self, print3d):
        _wire_blender(print3d, ALL_ROWS)
        assert print3d.toolbox_available() is True

    def test_unavailable_reports_false(self, print3d):
        _wire_blender(print3d, ALL_ROWS, toolbox=False)
        assert print3d.toolbox_available() is False


class TestCheckAll:
    def test_every_row_becomes_a_count(self, print3d):
        _wire_blender(print3d, ALL_ROWS)
        out = print3d.handle_check_3d_printability({"object_name": "Cube"})
        assert out["non_manifold_edge_count"] == 0
        assert out["bad_contiguous_edge_count"] == 3
        assert out["intersect_face_count"] == 179
        assert out["shell_count"] == 4
        assert out["thin_face_count"] == 22
        assert out["overhang_face_count"] == 308

    def test_uses_check_all_when_no_subset_requested(self, print3d):
        _obj, _props, ops = _wire_blender(print3d, ALL_ROWS)
        print3d.handle_check_3d_printability({"object_name": "Cube"})
        assert ops.print3d_check_all.called
        assert not ops.print3d_check_solid.called

    def test_indices_are_capped(self, print3d):
        _wire_blender(print3d, ALL_ROWS)
        out = print3d.handle_check_3d_printability({"object_name": "Cube"})
        assert len(out["intersect_face_indices"]) == print3d.MAX_SAMPLE_INDICES
        assert out["intersect_face_count"] == 179

    def test_issues_found_is_true_when_anything_is_wrong(self, print3d):
        _wire_blender(print3d, ALL_ROWS)
        out = print3d.handle_check_3d_printability({"object_name": "Cube"})
        assert out["issues_found"] is True

    def test_clean_mesh_reports_no_issues(self, print3d):
        clean = [(label, 0, []) for label, _c, _i in ALL_ROWS]
        clean = [("Shells", 1, []) if r[0] == "Shells" else r for r in clean]
        _wire_blender(print3d, clean)
        out = print3d.handle_check_3d_printability({"object_name": "Cube"})
        assert out["issues_found"] is False
        assert out["print_blocking"] == []

    def test_a_single_shell_is_not_an_issue(self, print3d):
        """One shell is a solid. Zero or many is worth saying, one is normal."""
        rows = [(label, 0, []) for label, _c, _i in ALL_ROWS]
        rows = [("Shells", 1, []) if r[0] == "Shells" else r for r in rows]
        _wire_blender(print3d, rows)
        out = print3d.handle_check_3d_printability({"object_name": "Cube"})
        assert out["shell_count"] == 1
        assert "shells" not in " ".join(out["print_blocking"]).lower()

    def test_print_blocking_names_only_the_fatal_defects(self, print3d):
        """Overhangs and sharp edges are advisory; reversed faces are not."""
        _wire_blender(print3d, ALL_ROWS)
        out = print3d.handle_check_3d_printability({"object_name": "Cube"})
        blocking = " ".join(out["print_blocking"]).lower()
        assert "contiguous" in blocking or "reversed" in blocking
        assert "overhang" not in blocking
        assert "sharp" not in blocking


class TestCheckSubset:
    def test_subset_calls_only_the_named_operators(self, print3d):
        _obj, props, ops = _wire_blender(print3d, [("Intersect Faces", 5, [1])])
        print3d.handle_check_3d_printability(
            {"object_name": "Cube", "checks": ["INTERSECT"]})
        assert ops.print3d_check_intersect.called
        assert not ops.print3d_check_all.called
        assert not ops.print3d_check_solid.called

    def test_subset_merges_reports_across_calls(self, print3d):
        """Each operator replaces the report, so results must be accumulated."""
        _obj, props, _ops = _wire_blender(print3d, [])
        props.get_report.side_effect = [
            _make_report([("Non-manifold Edges", 2, [1, 2]),
                          ("Bad Contiguous Edges", 0, [])]),
            _make_report([("Thin Faces", 7, [3])]),
        ]
        out = print3d.handle_check_3d_printability(
            {"object_name": "Cube", "checks": ["SOLID", "THICKNESS"]})
        assert out["non_manifold_edge_count"] == 2
        assert out["thin_face_count"] == 7

    def test_unrequested_checks_are_absent_not_zero(self, print3d):
        """Reporting 0 for a check that never ran would be a lie."""
        _wire_blender(print3d, [("Intersect Faces", 5, [1])])
        out = print3d.handle_check_3d_printability(
            {"object_name": "Cube", "checks": ["INTERSECT"]})
        assert out["intersect_face_count"] == 5
        assert "thin_face_count" not in out
        assert out["checks_run"] == ["INTERSECT"]

    def test_unknown_check_is_rejected(self, print3d):
        _wire_blender(print3d, ALL_ROWS)
        with pytest.raises(ValueError):
            print3d.handle_check_3d_printability(
                {"object_name": "Cube", "checks": ["WARP_CORE"]})


class TestThresholds:
    def test_thresholds_are_applied_to_the_toolbox(self, print3d):
        _obj, props, _ops = _wire_blender(print3d, ALL_ROWS)
        print3d.handle_check_3d_printability({
            "object_name": "Cube",
            "overhang_angle": math.radians(50),
            "min_thickness": 0.8,
            "sharp_angle": math.radians(70),
        })
        assert props.angle_overhang == pytest.approx(math.radians(50))
        assert props.thickness_min == pytest.approx(0.8)
        assert props.angle_sharp == pytest.approx(math.radians(70))

    def test_omitted_thresholds_are_left_alone(self, print3d):
        _obj, props, _ops = _wire_blender(print3d, ALL_ROWS)
        props.angle_overhang = 1.234
        print3d.handle_check_3d_printability({"object_name": "Cube"})
        assert props.angle_overhang == 1.234


class TestObjectResolution:
    def test_missing_object_raises(self, print3d):
        _wire_blender(print3d, ALL_ROWS)
        with pytest.raises(ValueError):
            print3d.handle_check_3d_printability({"object_name": "Nope"})

    def test_non_mesh_object_raises(self, print3d):
        obj, _props, _ops = _wire_blender(print3d, ALL_ROWS)
        obj.type = "CAMERA"
        with pytest.raises(ValueError):
            print3d.handle_check_3d_printability({"object_name": "Cube"})

    def test_object_is_made_active(self, print3d):
        """The operators act on the active object, not on a name."""
        obj, _props, _ops = _wire_blender(print3d, ALL_ROWS)
        print3d.handle_check_3d_printability({"object_name": "Cube"})
        assert print3d.bpy.context.view_layer.objects.active is obj


class TestRegistration:
    def test_registers_the_command(self, print3d):
        dispatcher = MagicMock()
        print3d.dispatcher = dispatcher
        print3d.register()
        registered = {c.args[0] for c in dispatcher.register_handler.call_args_list}
        assert "check_3d_printability" in registered
