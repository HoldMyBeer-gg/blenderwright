"""Materials and shader nodes in a real Blender. Replaces the fake-bpy
materials handler tests."""

import pytest

from blenderwright.tools import materials as m
from blenderwright.tools.objects import create_object, get_object_info, join_objects
from blenderwright.tools.modeling import boolean_operation


@pytest.fixture
def mat(scene):
    m.create_material("Paint")
    m.add_shader_node("Paint", "ShaderNodeTexNoise")
    m.add_shader_node("Paint", "ShaderNodeMath")
    m.add_shader_node("Paint", "ShaderNodeValToRGB")
    return "Paint"


class TestShaderNodeInput:
    def test_by_name(self, mat):
        assert m.set_shader_node_input(mat, "Noise Texture", "Scale", 12.0)["value"] == 12.0

    def test_by_index_reaches_the_second_value(self, mat):
        assert m.set_shader_node_input(mat, "Math", 1, 3.0)["value"] == 3.0

    def test_vector(self, mat):
        result = m.set_shader_node_input(mat, "Noise Texture", "Vector", [1.0, 2.0, 3.0])
        assert result["value"] == [1.0, 2.0, 3.0]

    @pytest.mark.parametrize("node, socket, match", [
        ("Noise Texture", "Nope", "Nope"),
        ("Math", 9, "9"),
        ("Ghost", "Scale", "Ghost"),
    ])
    def test_errors_name_the_problem(self, mat, node, socket, match):
        with pytest.raises(RuntimeError, match=match):
            m.set_shader_node_input(mat, node, socket, 1.0)

    def test_unknown_material(self, scene):
        with pytest.raises(RuntimeError, match="Nowhere"):
            m.set_shader_node_input("Nowhere", "Math", 0, 1.0)


class TestShaderNodeProperty:
    def test_enum_and_bool(self, mat):
        m.set_shader_node_property(mat, "Math", "operation", "MULTIPLY")
        assert m.set_shader_node_property(mat, "Math", "use_clamp", True)["value"] is True

    def test_property_the_node_lacks(self, mat):
        with pytest.raises(RuntimeError):
            m.set_shader_node_property(mat, "Noise Texture", "operation", "ADD")


class TestColorRamp:
    def test_starts_with_two_stops(self, mat):
        assert len(m.get_color_ramp(mat, "Color Ramp")["elements"]) == 2

    @pytest.mark.parametrize("position", [0.5, 0.0, 0.999])
    def test_reported_index_points_at_the_new_stop(self, mat, position):
        """Stops re-sort on add (a tie at 0.0 lands after the old stop)."""
        index = m.add_color_ramp_element(mat, "Color Ramp", position, [0, 1, 0, 1])["index"]
        stop = m.get_color_ramp(mat, "Color Ramp")["elements"][index]
        assert stop["position"] == pytest.approx(position)
        assert stop["color"] == pytest.approx([0, 1, 0, 1])

    def test_set_position_leaves_colour(self, mat):
        before = m.get_color_ramp(mat, "Color Ramp")["elements"][1]["color"]
        m.set_color_ramp_element(mat, "Color Ramp", 1, position=0.8)
        after = m.get_color_ramp(mat, "Color Ramp")["elements"][1]
        assert after["position"] == pytest.approx(0.8) and after["color"] == before

    def test_remove_and_never_the_last(self, mat):
        m.remove_color_ramp_element(mat, "Color Ramp", 0)
        with pytest.raises(RuntimeError):
            m.remove_color_ramp_element(mat, "Color Ramp", 0)

    def test_out_of_range(self, mat):
        with pytest.raises(RuntimeError):
            m.set_color_ramp_element(mat, "Color Ramp", 5, position=0.1)

    def test_interpolation_and_colour_mode(self, mat):
        result = m.set_color_ramp_interpolation(mat, "Color Ramp", "CONSTANT", color_mode="HSV")
        assert result["interpolation"] == "CONSTANT" and result["color_mode"] == "HSV"

    def test_not_a_ramp(self, mat):
        with pytest.raises(RuntimeError, match="ramp"):
            m.get_color_ramp(mat, "Math")


def _slots(name):
    return [s["name"] for s in get_object_info(name)["materials"]]


class TestAssignMaterialSlots:
    def test_no_slots_gets_one(self, mat):
        create_object("UV_SPHERE", name="Ball")
        result = m.assign_material("Ball", mat)
        assert _slots("Ball") == [mat] and result["action"] == "assigned"

    def test_single_material_is_replaced(self, mat):
        result = m.assign_material("Cube", mat)  # the factory cube has "Material"
        assert _slots("Cube") == [mat]
        assert result["action"] == "replaced" and result["replaced"] == "Material"

    def test_multi_material_object_keeps_its_materials(self, mat):
        create_object("UV_SPHERE", name="Glass", location=[3, 0, 0])
        m.create_material("GlassMat")
        m.assign_material("Glass", "GlassMat")
        join_objects(["Cube", "Glass"])
        result = m.assign_material("Cube", mat)
        assert _slots("Cube") == ["Material", "GlassMat", mat]
        assert result["action"] == "added_slot" and result["slot"] == 2

    def test_already_assigned(self, mat):
        m.assign_material("Cube", mat)
        assert m.assign_material("Cube", mat)["action"] == "already_assigned"

    def test_boolean_leftover_empty_slot_is_filled(self, mat):
        create_object("UV_SPHERE", name="Wall")
        boolean_operation("Wall", "Cube", operation="DIFFERENCE")
        assert _slots("Wall")[0] is None  # the empty slot a boolean leaves
        result = m.assign_material("Wall", mat)
        assert _slots("Wall")[0] == mat and result["slot"] == 0
