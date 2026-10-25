"""Geometry nodes in a real Blender. Replaces the fake-bpy handler tests for
build_geometry_nodes, modifier inputs and the Essentials modifiers."""

import pytest

from blenderwright.tools.geometry_nodes import (add_essentials_modifier, build_geometry_nodes,
                                                get_geometry_node_tree,
                                                list_geometry_node_inputs,
                                                set_geometry_node_input)
from blenderwright.tools.objects import create_object, get_object_info


def _node(tree, name):
    return next(n for n in tree["nodes"] if n["name"] == name)


@pytest.fixture
def box(scene):
    create_object("CUBE", name="Box")
    return "Box"


class TestBuild:
    def test_a_new_build_replaces_the_graph(self, box):
        build_geometry_nodes(box, {"nodes": [{"name": "first", "type": "ShaderNodeMath"}]},
                             modifier_name="GN")
        build_geometry_nodes(box, {"nodes": [{"name": "second", "type": "ShaderNodeMath"}]},
                             modifier_name="GN")
        names = {n["name"] for n in get_geometry_node_tree(box, "GN")["nodes"]}
        assert "second" in names and "first" not in names
        assert [m["name"] for m in get_object_info(box)["modifiers"]] == ["GN"]

    def test_a_failed_build_keeps_the_working_graph(self, box):
        build_geometry_nodes(box, {"nodes": [{"name": "keep", "type": "ShaderNodeMath"}]},
                             modifier_name="GN")
        with pytest.raises(RuntimeError, match="Nope"):
            build_geometry_nodes(box, {
                "nodes": [{"name": "broken", "type": "ShaderNodeMath", "inputs": {"Nope": 1}}]},
                modifier_name="GN")
        assert "keep" in {n["name"] for n in get_geometry_node_tree(box, "GN")["nodes"]}

    def test_settings_apply_and_read_back(self, box):
        build_geometry_nodes(box, {"nodes": [
            {"name": "wave", "type": "ShaderNodeMath", "settings": {"operation": "SINE"}}]})
        tree = get_geometry_node_tree(box, "GeometryNodes")
        assert _node(tree, "wave")["settings"]["operation"] == "SINE"

    @pytest.mark.parametrize("key", ["name", "location", "bl_idname", "missing"])
    def test_unsafe_or_unknown_settings_refused(self, box, key):
        with pytest.raises(RuntimeError, match="setting"):
            build_geometry_nodes(box, {"nodes": [
                {"name": "m", "type": "ShaderNodeMath", "settings": {key: 1}}]})

    def test_unknown_node_type_suggests_the_real_one(self, box):
        with pytest.raises(RuntimeError, match="GeometryNodeMeshCube"):
            build_geometry_nodes(box, {"nodes": [{"name": "c", "type": "GeometryNodeCube"}]})

    def test_links_by_name_identifier_and_index(self, box):
        build_geometry_nodes(box, {
            "nodes": [{"name": "a", "type": "ShaderNodeMath"},
                      {"name": "b", "type": "ShaderNodeMath"}],
            "links": [["a", "Value", "b", "Value_001"], ["a", 0, "b", 0]]})
        links = get_geometry_node_tree(box, "GeometryNodes")["links"]
        assert ["a", "Value", "b", "Value_001"] in links and ["a", "Value", "b", "Value"] in links

    def test_group_inputs_link_and_show_on_the_modifier(self, box):
        build_geometry_nodes(box, {
            "inputs": [{"name": "Size", "type": "FLOAT", "default": 4.0, "min": 0.1}],
            "nodes": [{"name": "grid", "type": "GeometryNodeMeshGrid"}],
            "links": [["Group Input", "Size", "grid", "Size X"],
                      ["grid", "Mesh", "Group Output", "Geometry"]]})
        assert get_object_info(box)["dimensions"][0] == pytest.approx(4.0, abs=0.01)
        assert {"name": "Size", "in_out": "INPUT", "type": "FLOAT"} in \
            get_geometry_node_tree(box, "GeometryNodes")["interface"]

    def test_object_socket_takes_a_name(self, box):
        build_geometry_nodes(box, {"nodes": [
            {"name": "info", "type": "GeometryNodeObjectInfo", "inputs": {"Object": "Camera"}}]})
        assert _node(get_geometry_node_tree(box, "GeometryNodes"), "info")["inputs"][
            "Object"] == "Camera"

    def test_missing_object_for_a_socket(self, box):
        with pytest.raises(RuntimeError, match="Ghost"):
            build_geometry_nodes(box, {"nodes": [
                {"name": "info", "type": "GeometryNodeObjectInfo", "inputs": {"Object": "Ghost"}}]})


class TestModifierInputs:
    def test_set_and_list_round_trip(self, box):
        build_geometry_nodes(box, {"inputs": [{"name": "Size", "type": "FLOAT"}]})
        set_geometry_node_input(box, "GeometryNodes", "Size", 2.5)
        inputs = {i["name"]: i for i in list_geometry_node_inputs(box, "GeometryNodes")}
        assert inputs["Size"]["value"] == pytest.approx(2.5)

    def test_geometry_input_takes_no_value(self, box):
        build_geometry_nodes(box, {})
        with pytest.raises(RuntimeError, match="Geometry"):
            set_geometry_node_input(box, "GeometryNodes", "Geometry", 1)


class TestEssentials:
    def test_scatter_with_numbers_menus_and_objects(self, box):
        result = add_essentials_modifier(box, "scatter_on_surface", settings={
            "Amount": 50, "Density Method": "Amount", "Object": "Camera"})
        assert result["inputs"]["Amount"] == 50
        assert result["inputs"]["Density Method"] == "Amount"
        assert result["inputs"]["Object"] == "Camera"
        assert get_object_info(box)["modifiers"][0]["type"] == "NODES"

    @pytest.mark.parametrize("settings, message", [
        ({"Object": "Boulder"}, "Boulder"),
        ({"Density Method": "Sideways"}, "Amount"),
        ({"Speed": 3}, "Amount"),
    ])
    def test_bad_settings_explain_and_leave_no_modifier(self, box, settings, message):
        with pytest.raises(RuntimeError, match=message):
            add_essentials_modifier(box, "scatter_on_surface", settings=settings)
        assert get_object_info(box)["modifiers"] == []
