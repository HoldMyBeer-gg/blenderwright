"""The add-on's own checks, hit directly over the authenticated socket.

Anything on this machine that holds the token could send commands without
going through the MCP tools' validation, so the add-on must refuse unsafe
input itself. These send raw commands, as such a client would.
"""

import pytest

from blenderwright import server


def _raw(command, params):
    return server.get_connection().send_command(command, params)


@pytest.fixture
def paint(scene):
    from blenderwright.tools.materials import add_shader_node, create_material

    create_material("Paint")
    add_shader_node("Paint", "ShaderNodeMath")
    return "Paint"


@pytest.mark.parametrize("prop", ["__class__", "bl_idname", "name", "wave_type"])
def test_shader_node_property_allowlist(paint, prop):
    reply = _raw("set_shader_node_property", {"material_name": paint, "node_name": "Math",
                                              "property": prop, "value": "X"})
    assert reply["status"] == "error"


@pytest.mark.parametrize("prop", ["__class__", "bl_rna", "name", "show_viewport_x"])
def test_modifier_property_is_rna_only(scene, prop):
    from blenderwright.tools.modeling import add_modifier

    add_modifier("Cube", "BEVEL", name="Bevel")
    reply = _raw("set_modifier_property", {"object_name": "Cube", "modifier_name": "Bevel",
                                           "property": prop, "value": 1})
    assert reply["status"] == "error"


@pytest.mark.parametrize("option", ["filepath", "export_texture_dir"])
def test_export_text_settings_refused(scene, option):
    reply = _raw("export_file", {"filepath": str(scene / "a.glb"), "type": "",
                                 "selected_only": False, "options": {option: "/tmp/x"}})
    assert reply["status"] == "error" and "text setting" in reply["result"]


def test_unknown_command_refused(scene):
    reply = _raw("__import__", {})
    assert reply["status"] == "error"
