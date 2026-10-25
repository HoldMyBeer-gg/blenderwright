"""Animation in a real Blender, judged by where things are on a given frame.
Replaces the fake-bpy animation handler tests."""

import pytest

from blenderwright import server
from blenderwright.server import mcp
from blenderwright.tools.objects import create_object, get_object_info

T = {x.name: x.fn for x in mcp._tool_manager.list_tools()}


def _at(frame, name="Box", what="location"):
    T["set_frame"](frame)
    return get_object_info(name)[what]


@pytest.fixture
def box(scene):
    create_object("CUBE", name="Box")
    T["insert_keyframe"]("Box", "location", 1, [0, 0, 0])
    T["insert_keyframe"]("Box", "location", 21, [10, 0, 0])
    return "Box"


class TestKeyframes:
    def test_keys_animate_and_list(self, box):
        assert _at(21)[0] == pytest.approx(10)
        assert 0 < _at(11)[0] < 10
        x_keys = [(k["frame"], k["value"]) for k in T["list_keyframes"](box)
                  if k["data_path"] == "location" and k["array_index"] == 0]
        assert x_keys == [(1.0, 0.0), (21.0, pytest.approx(10.0))]

    def test_linear_interpolation_is_halfway(self, box):
        T["set_interpolation"](box, "location", "LINEAR")
        assert _at(11)[0] == pytest.approx(5.0)

    def test_constant_interpolation_holds(self, box):
        T["set_interpolation"](box, "location", "CONSTANT")
        assert _at(20)[0] == pytest.approx(0.0)

    def test_no_keys_on_that_path(self, box):
        with pytest.raises(RuntimeError):
            T["set_interpolation"](box, "scale", "LINEAR")


class TestDrivers:
    def test_expression_driver(self, scene):
        create_object("CUBE", name="Box")
        T["add_driver"]("Box", "location", expression="frame / 10", index=2)
        assert _at(20)[2] == pytest.approx(2.0)

    def test_variable_from_another_object(self, scene):
        create_object("CUBE", name="Box")
        create_object("CUBE", name="Leader", location=[3, 0, 0])
        T["add_driver"]("Box", "location", expression="x * 2", index=0, variables=[
            {"name": "x", "type": "SINGLE_PROP", "object": "Leader", "data_path": "location.x"}])
        assert _at(1)[0] == pytest.approx(6.0)

    def test_unknown_variable_object(self, scene):
        create_object("CUBE", name="Box")
        with pytest.raises(RuntimeError, match="Ghost"):
            T["add_driver"]("Box", "location", expression="x", index=0, variables=[
                {"name": "x", "type": "SINGLE_PROP", "object": "Ghost",
                 "data_path": "location.x"}])

    def test_list_and_remove(self, scene):
        create_object("CUBE", name="Box")
        T["add_driver"]("Box", "location", expression="frame", index=2)
        assert T["list_drivers"]("Box")["drivers"]
        T["remove_driver"]("Box", "location", index=2)
        assert T["list_drivers"]("Box")["drivers"] == []

    def test_light_energy_hops_to_the_light_data(self, scene):
        T["add_driver"]("Light", "data.energy", expression="frame * 10")
        T["set_frame"](30)
        assert T["list_drivers"]("Light")["drivers"]

    @pytest.mark.parametrize("expression", ["__import__('os')", "open('/etc/passwd')",
                                            "(lambda: 1)()", "x.__class__"])
    def test_unsafe_expression_refused_by_the_addon(self, scene, expression):
        reply = server.get_connection().send_command("add_driver", {
            "object_name": "Cube", "data_path": "location", "index": 2,
            "expression": expression, "driver_type": "SCRIPTED", "variables": []})
        assert reply["status"] == "error"


class TestKeyframeProperty:
    def test_material_colour_keyed_on_its_node_tree(self, scene):
        path = 'active_material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value'
        result = T["keyframe_property"](path, 24, value=[1, 0, 0, 1], object_name="Cube")
        assert result["owner"] == "Shader Nodetree"

    def test_world_target(self, scene):
        """Its reply once held a raw Blender value and dropped the connection."""
        path = 'node_tree.nodes["Background"].inputs["Strength"].default_value'
        assert T["keyframe_property"](path, 1, value=0.2, target="WORLD")["value"] == \
            pytest.approx(0.2)

    def test_unknown_path_is_explained(self, scene):
        with pytest.raises(RuntimeError, match="no property"):
            T["keyframe_property"]("colour", 1, value=1, object_name="Cube")


class TestActionsAndNla:
    def test_new_assign_push_down_and_nla(self, box):
        actions = T["manage_action"](box, "LIST")
        first = actions["action"]
        T["manage_action"](box, "NEW", action_name="Jump")
        with pytest.raises(RuntimeError, match="Jump"):
            T["manage_action"](box, "NEW", action_name="Jump")
        T["manage_action"](box, "ASSIGN", action_name=first)
        assert T["manage_action"](box, "PUSH_DOWN")["action"] is None
        strip = T["list_nla"](box)["tracks"][0]["strips"][0]
        assert strip["action"] == first

    def test_strip_on_a_named_track_drives_the_object(self, box):
        first = T["manage_action"](box, "LIST")["action"]
        T["manage_action"](box, "UNASSIGN")
        T["add_nla_strip"](box, first, frame_start=101, track_name="Base")
        listing = T["list_nla"](box)
        assert listing["tracks"][0]["name"] == "Base"
        assert _at(121)[0] == pytest.approx(10)

    def test_missing_action(self, box):
        with pytest.raises(RuntimeError, match="Nope"):
            T["manage_action"](box, "ASSIGN", action_name="Nope")

    def test_unknown_blend_refused_by_the_addon(self, box):
        reply = server.get_connection().send_command("add_nla_strip", {
            "object_name": box, "action_name": "x", "blend_type": "__class__"})
        assert reply["status"] == "error"


class TestFcurveModifiers:
    def test_noise_reaches_every_component_and_moves_the_object(self, box):
        T["set_interpolation"](box, "location", "LINEAR")
        T["add_fcurve_modifier"](box, "location", "NOISE", settings={"strength": 5.0})
        assert _at(11)[1] != pytest.approx(0.0)  # Y wobbles now too

    @pytest.mark.parametrize("key", ["__class__", "bl_rna", "data_path"])
    def test_settings_are_rna_only_in_the_addon(self, box, key):
        reply = server.get_connection().send_command("add_fcurve_modifier", {
            "object_name": box, "data_path": "location", "modifier": "NOISE", "index": -1,
            "settings": {key: 1}})
        assert reply["status"] == "error"

    def test_no_animation(self, scene):
        create_object("CUBE", name="Still")
        with pytest.raises(RuntimeError):
            T["add_fcurve_modifier"]("Still", "location", "NOISE")
