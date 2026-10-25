"""UV tools in a real Blender. Replaces the fake-bpy UV handler tests."""

import pytest

from blenderwright.server import mcp
from blenderwright.tools.objects import create_object

T = {x.name: x.fn for x in mcp._tool_manager.list_tools()}


class TestTexelDensity:
    def test_set_then_measure(self, scene):
        create_object("CUBE", name="Box")
        T["smart_uv_project"]("Box")
        T["set_texel_density"]("Box", density=512, texture_size=1024)
        measured = T["get_texel_density"]("Box", texture_size=1024)
        assert measured["density"] == pytest.approx(512, rel=0.05)

    def test_world_scale_counts(self, scene):
        create_object("CUBE", name="Small")
        create_object("CUBE", name="Large", location=[5, 0, 0], scale=[2, 2, 2])
        for name in ("Small", "Large"):
            T["smart_uv_project"](name)
        small = T["get_texel_density"]("Small")["density"]
        large = T["get_texel_density"]("Large")["density"]
        assert large == pytest.approx(small / 2, rel=0.1)


class TestIslandOperations:
    @pytest.mark.parametrize("operation", ["AVERAGE_SCALE", "MINIMIZE_STRETCH", "ALIGN_ROTATION",
                                           "RANDOMIZE", "SEAMS_FROM_ISLANDS", "ARRANGE",
                                           "WELD"])
    def test_each_operation_runs(self, scene, operation):
        create_object("UV_SPHERE", name="Ball")
        T["smart_uv_project"]("Ball")
        assert T["uv_island_operation"]("Ball", operation)["operation"] == operation

    def test_from_edit_mode(self, scene):
        create_object("CUBE", name="Box")
        T["select_by_axis"]("Box", axis="Z", sign="POS")
        T["uv_island_operation"]("Box", "ARRANGE", selection="CURRENT")
        T["smart_uv_project"]("Box")


class TestUVMaps:
    def test_add_set_rename_remove(self, scene):
        maps = T["manage_uv_map"]("Cube", "ADD", uv_map="Lightmap", copy_active=False)["uv_maps"]
        assert [m["name"] for m in maps] == ["UVMap", "Lightmap"]
        assert next(m for m in maps if m["name"] == "Lightmap")["active"] is True
        maps = T["manage_uv_map"]("Cube", "SET_RENDER", uv_map="Lightmap")["uv_maps"]
        assert next(m for m in maps if m["name"] == "Lightmap")["render"] is True
        T["manage_uv_map"]("Cube", "RENAME", uv_map="UVMap", new_name="Base")
        maps = T["manage_uv_map"]("Cube", "REMOVE", uv_map="Base")["uv_maps"]
        assert [m["name"] for m in maps] == ["Lightmap"]

    def test_limits_and_errors(self, scene):
        with pytest.raises(RuntimeError, match="already"):
            T["manage_uv_map"]("Cube", "ADD", uv_map="UVMap")
        for i in range(7):
            T["manage_uv_map"]("Cube", "ADD", uv_map=f"m{i}", copy_active=False)
        with pytest.raises(RuntimeError, match="8"):
            T["manage_uv_map"]("Cube", "ADD", uv_map="Ninth")
        with pytest.raises(RuntimeError, match="UVMap"):
            T["manage_uv_map"]("Cube", "REMOVE", uv_map="Ghost")
