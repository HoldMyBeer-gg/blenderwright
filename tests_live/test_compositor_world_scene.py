"""Compositor, world lighting, light linking, collections, view layers and
units in a real Blender. Replaces those fake-bpy handler tests."""

import pytest

from blenderwright import server
from blenderwright.server import mcp
from blenderwright.tools.objects import create_object, get_object_info

T = {x.name: x.fn for x in mcp._tool_manager.list_tools()}


def _chain():
    return [step["node_name"] for step in T["list_compositor"]()["chain"]]


class TestCompositor:
    def test_nothing_until_set_up(self, scene):
        assert T["list_compositor"]() == {"tree": None, "chain": []}

    def test_setup_is_idempotent_and_reset_starts_clean(self, scene):
        assert T["setup_compositor"]()["chain"] == ["Render Layers", "Group Output"]
        T["add_compositor_effect"]("blur")
        T["setup_compositor"]()
        assert "Blur" in _chain()
        assert T["setup_compositor"](reset=True)["chain"] == ["Render Layers", "Group Output"]

    def test_effects_stack_in_order_with_settings(self, scene):
        T["setup_compositor"]()
        blur = T["add_compositor_effect"]("blur", {"Size": [8, 8]})
        assert blur["settings"]["Size"] == [8.0, 8.0]
        T["add_compositor_effect"]("glare")
        assert _chain()[1:3] == ["Blur", "Glare"]

    def test_essentials_effect_is_a_group_node(self, scene):
        result = T["add_compositor_effect"]("chromatic_aberration")
        assert result["settings"]["Type"] == "Scale"

    @pytest.mark.parametrize("settings, match", [({"Type": "Sideways"}, "Gaussian"),
                                                 ({"Speed": 3}, "Size")])
    def test_bad_settings_explain_and_leave_nothing(self, scene, settings, match):
        T["setup_compositor"]()
        with pytest.raises(RuntimeError, match=match):
            T["add_compositor_effect"]("blur", settings)
        assert "Blur" not in _chain()

    def test_set_remove_and_core_nodes(self, scene):
        T["setup_compositor"]()
        T["add_compositor_effect"]("blur")
        T["add_compositor_effect"]("glare")
        assert T["set_compositor_effect"]("Blur", {"Size": [3, 3]})["settings"]["Size"] == [3, 3]
        T["remove_compositor_effect"]("Blur")
        assert _chain()[1] == "Glare"  # reconnected around the gap
        for core in ("Render Layers", "Group Output"):
            with pytest.raises(RuntimeError):
                T["remove_compositor_effect"](core)
        with pytest.raises(RuntimeError, match="Nope"):
            T["remove_compositor_effect"]("Nope")

    def test_unknown_effect_refused_by_the_addon(self, scene):
        reply = server.get_connection().send_command("add_compositor_effect",
                                                     {"effect": "__class__", "settings": {}})
        assert reply["status"] == "error"


class TestWorld:
    def test_builtin_hdri_with_rotation(self, scene):
        T["set_world_background"](builtin_hdri="forest", rotation=1.0, strength=2.0)

    def test_sky(self, scene):
        result = T["set_world_sky"](sun_elevation=0.5)
        assert result["sky_type"] == "MULTIPLE_SCATTERING"
        assert result["sun_elevation"] == pytest.approx(0.5)

    @pytest.mark.parametrize("command, params", [
        ("set_world_background", {"builtin_hdri": "../../etc/passwd"}),
        ("set_world_sky", {"sky_type": "__class__"}),
    ])
    def test_unknown_names_refused_by_the_addon(self, scene, command, params):
        assert server.get_connection().send_command(command, params)["status"] == "error"


class TestLightLinking:
    def test_receivers_replace_and_clear(self, scene):
        create_object("UV_SPHERE", name="Ball", location=[3, 0, 0])
        r1 = T["set_light_linking"]("Light", ["Cube"])
        assert r1["objects"] == ["Cube"]
        r2 = T["set_light_linking"]("Light", ["Ball"], mode="EXCLUDE")
        assert r2["objects"] == ["Ball"] and r2["mode"] == "EXCLUDE"
        assert T["set_light_linking"]("Light", [], role="BLOCKERS")["objects"] == []

    def test_missing_object(self, scene):
        with pytest.raises(RuntimeError, match="Ghost"):
            T["set_light_linking"]("Light", ["Ghost"])


class TestCollections:
    def test_instance_and_make_real(self, scene):
        T["create_collection"]("Kit")
        create_object("CUBE", name="Brick", location=[5, 0, 0])
        T["move_to_collection"](["Brick"], "Kit")
        inst = T["create_collection_instance"]("Kit", name="KitCopy", location=[0, 5, 0])
        assert inst["name"] == "KitCopy" and get_object_info("KitCopy")["type"] == "EMPTY"
        real = T["make_instances_real"]("KitCopy")
        assert real["objects"]

    def test_name_defaults_and_missing(self, scene):
        assert T["create_collection_instance"]("Collection")["name"] == "Collection"
        with pytest.raises(RuntimeError, match="Ghost"):
            T["create_collection_instance"]("Ghost")
        with pytest.raises(RuntimeError, match="instance"):
            T["make_instances_real"]("Cube")


class TestViewLayers:
    def test_add_activate_rename_override_remove(self, scene):
        T["manage_view_layer"]("ADD", view_layer="FG")
        layers = T["manage_view_layer"]("SET_ACTIVE", view_layer="FG")["view_layers"]
        assert next(v for v in layers if v["name"] == "FG")["active"] is True
        T["create_material"]("Clay")
        layers = T["manage_view_layer"]("SET", view_layer="FG",
                                        material_override="Clay")["view_layers"]
        assert next(v for v in layers if v["name"] == "FG")["material_override"] == "Clay"
        T["manage_view_layer"]("SET", view_layer="FG", material_override="")
        T["manage_view_layer"]("RENAME", view_layer="FG", new_name="Front")
        names = [v["name"] for v in T["manage_view_layer"]("REMOVE", view_layer="Front")[
            "view_layers"]]
        assert names == ["ViewLayer"]

    def test_limits_and_errors(self, scene):
        with pytest.raises(RuntimeError, match="already"):
            T["manage_view_layer"]("ADD", view_layer="ViewLayer")
        with pytest.raises(RuntimeError, match="last"):
            T["manage_view_layer"]("REMOVE", view_layer="ViewLayer")
        with pytest.raises(RuntimeError, match="Sky"):
            T["manage_view_layer"]("SET", view_layer="ViewLayer", world_override="Sky")

    def test_layer_collection_flags(self, scene):
        T["create_collection"]("Props", parent="Collection")
        result = T["set_layer_collection"]("Props", holdout=True)
        assert result["holdout"] is True
        with pytest.raises(RuntimeError, match="Ghost"):
            T["set_layer_collection"]("Ghost", exclude=True)


class TestUnits:
    def test_system_first_then_units(self, scene):
        result = T["set_units"](system="IMPERIAL", length_unit="INCHES")
        assert (result["system"], result["length_unit"]) == ("IMPERIAL", "INCHES")

    def test_wrong_unit_for_the_system(self, scene):
        T["set_units"](system="METRIC")
        with pytest.raises(RuntimeError, match="METRIC"):
            T["set_units"](length_unit="INCHES")

    def test_suggestions(self, scene):
        names = [s["extension_id"] for s in T["suggest_extensions"]("boolean cut")["suggestions"]]
        assert "bool_tool" in names
