"""Sculpting in a real Blender. Replaces the fake-bpy sculpting handler tests."""

import pytest

from blenderwright import server
from blenderwright.server import mcp
from blenderwright.tools.mesh_quality import analyze_mesh_quality
from blenderwright.tools.objects import create_object

T = {x.name: x.fn for x in mcp._tool_manager.list_tools()}


@pytest.fixture
def sculpting(scene):
    create_object("UV_SPHERE", name="Head")
    T["enter_sculpt_mode"]("Head")
    return "Head"


class TestBrushes:
    @pytest.mark.parametrize("brush", ["DRAW", "CLAY_STRIPS", "GRAB", "SMOOTH", "MASK"])
    def test_essentials_brushes_activate(self, sculpting, brush):
        T["set_sculpt_brush"](brush)

    def test_brush_settings(self, sculpting):
        T["set_sculpt_brush"]("DRAW")
        T["set_brush_property"]("size", 80)
        assert T["set_brush_property"]("strength", 0.4)["value"] == pytest.approx(0.4)
        T["set_brush_property"]("stroke_method", "DOTS")

    @pytest.mark.parametrize("prop, value", [("stroke_method", "SIDEWAYS"),
                                             ("__class__", 1), ("name", "x")])
    def test_the_addon_refuses_bad_settings(self, sculpting, prop, value):
        T["set_sculpt_brush"]("DRAW")
        reply = server.get_connection().send_command("set_brush_property",
                                                     {"property": prop, "value": value})
        assert reply["status"] == "error"


class TestRemeshVoxelBudget:
    """0.001 on a 2 m object is a 2000^3 grid; Blender would stop responding."""

    def test_absurd_grid_refused_with_a_workable_size(self, scene):
        create_object("CUBE", name="Thing")
        with pytest.raises(RuntimeError, match="0.0"):
            T["remesh"]("Thing", voxel_size=0.001)

    def test_budget_scales_with_the_object(self, scene):
        create_object("CUBE", name="Big", scale=[100, 100, 100])
        with pytest.raises(RuntimeError, match="(?i)voxel"):
            T["remesh"]("Big", voxel_size=0.05)

    def test_sane_size_remeshes(self, scene):
        create_object("CUBE", name="Thing")
        T["remesh"]("Thing", voxel_size=0.2)
        assert analyze_mesh_quality("Thing")["vertex_count"] > 8

    def test_other_modes_ignore_voxel_size_and_say_so(self, scene):
        create_object("CUBE", name="Thing")
        assert T["remesh"]("Thing", voxel_size=0.001, mode="SHARP").get("voxel_size") is None


class TestMasksAndFaceSets:
    def test_mask_all_part_invert_clear(self, sculpting):
        assert T["set_sculpt_mask"](sculpting)["masked"] == \
            analyze_mesh_quality(sculpting)["vertex_count"]
        T["set_sculpt_mask"](sculpting, clear=True)
        assert T["set_sculpt_mask"](sculpting, vertex_indices=[0, 1, 2])["masked"] == 3
        inverted = T["set_sculpt_mask"](sculpting, invert=True)["masked"]
        assert inverted == analyze_mesh_quality(sculpting)["vertex_count"] - 3

    def test_mask_from_a_weighted_group(self, scene):
        create_object("CUBE", name="Box")
        T["assign_vertex_group"]("Box", "Half", vertex_indices=[0, 1], weight=0.5)
        assert T["set_sculpt_mask"]("Box", vertex_group="Half")["masked"] == 2

    def test_bad_vertex_and_missing_group(self, sculpting):
        with pytest.raises(RuntimeError, match="out of range"):
            T["set_sculpt_mask"](sculpting, vertex_indices=[99999])
        with pytest.raises(RuntimeError, match="Nose"):
            T["set_sculpt_mask"](sculpting, vertex_group="Nose")

    def test_sculpt_mode_is_kept(self, sculpting):
        T["set_sculpt_mask"](sculpting)
        T["set_face_sets"](sculpting, "LOOSE_PARTS")
        T["exit_sculpt_mode"]()  # still in sculpt mode until here, or this would fail

    def test_face_sets(self, scene):
        create_object("CUBE", name="A")
        create_object("CUBE", name="B", location=[3, 0, 0])
        T["join_objects"](["A", "B"])
        assert T["set_face_sets"]("A", "LOOSE_PARTS")["face_sets"] == 2
        assert T["set_face_sets"]("A", "ASSIGN", face_indices=[0], face_set=9)["face_sets"] == 3
        with pytest.raises(RuntimeError, match="out of range"):
            T["set_face_sets"]("A", "ASSIGN", face_indices=[99], face_set=1)
        assert T["set_face_sets"]("A", "CLEAR")["face_sets"] == 0
