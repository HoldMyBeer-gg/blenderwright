"""edit_mesh_operation in a real Blender: counts and sizes change as each
operation should. Counts come from analyze_mesh_quality."""

import pytest

from blenderwright.tools.mesh_editing import edit_mesh_operation
from blenderwright.tools.mesh_quality import analyze_mesh_quality
from blenderwright.tools.objects import create_object, get_object_info
from blenderwright.tools.selection import select_by_axis


def _counts(name):
    report = analyze_mesh_quality(name)
    return report["vertex_count"], report["face_count"]


def test_smooth_pulls_corners_in(scene):
    create_object("CUBE", name="Box")
    edit_mesh_operation("Box", "SMOOTH_VERTICES", factor=0.5, repeat=2)
    assert get_object_info("Box")["dimensions"][0] < 1.95
    assert _counts("Box") == (8, 6)


def test_poke_adds_a_point_per_face(scene):
    create_object("CUBE", name="Box")
    edit_mesh_operation("Box", "POKE")
    assert _counts("Box") == (14, 24)


def test_edge_split_unwelds_every_face(scene):
    create_object("CUBE", name="Box")
    edit_mesh_operation("Box", "EDGE_SPLIT")
    assert _counts("Box")[0] == 24


def test_wireframe_turns_edges_into_struts(scene):
    create_object("CUBE", name="Box")
    edit_mesh_operation("Box", "WIREFRAME", thickness=0.05)
    assert _counts("Box")[1] == 48  # 12 edges, each a four-sided strut


def test_solidify_gives_a_plane_thickness(scene):
    create_object("PLANE", name="Sheet")
    edit_mesh_operation("Sheet", "SOLIDIFY", thickness=0.25)
    assert get_object_info("Sheet")["dimensions"][2] == pytest.approx(0.25, abs=0.01)


def test_current_selection_only(scene):
    create_object("CUBE", name="Box")
    select_by_axis("Box", axis="Z", sign="POS")
    edit_mesh_operation("Box", "POKE", selection="CURRENT")
    assert _counts("Box") == (9, 9)  # only the top face was poked
