"""Names Blender itself allows, in a real Blender.

FBX and 3ds Max imports bring names like 'Material #25' and 'mixamorig:Hips',
and Blender 5.2 names hold up to 255 bytes. Every such name must be usable.
"""

import pytest

from blenderwright.server import mcp
from blenderwright.tools.objects import create_object, get_object_info

T = {x.name: x.fn for x in mcp._tool_manager.list_tools()}

IMPORTED = ["mixamorig:Hips", "Wood (Oak)", "Würfel", "立方体", "Rig|Spine #2"]


@pytest.mark.parametrize("name", IMPORTED)
def test_objects_with_imported_names_can_be_addressed(scene, name):
    created = create_object("CUBE", name=name)["name"]
    assert created == name
    assert get_object_info(name)["name"] == name


def test_a_long_name_is_kept_whole(scene):
    name = "Fuselage_Leading_Edge_Panel_" * 7  # 196 characters
    assert create_object("CUBE", name=name)["name"] == name
    assert get_object_info(name)["name"] == name


def test_a_new_name_past_255_bytes_is_cut_to_what_blender_keeps(scene):
    created = create_object("CUBE", name="é" * 200)["name"]
    assert created == "é" * 127
    assert get_object_info(created)["name"] == created


def test_append_names_from_an_imported_file(scene):
    T["create_material"]("Material #25")
    create_object("CUBE", name="mixamorig:Hips")
    T["assign_material"]("mixamorig:Hips", "Material #25")  # unused data is not saved
    library = str(scene / "imported.blend")
    T["save_file"](library)
    T["open_file"](str(scene / "scene.blend"))

    contents = T["list_blend_contents"](library)
    assert "Material #25" in contents["materials"]
    T["link_or_append"](library, "MATERIAL", ["Material #25"])
    T["link_or_append"](library, "OBJECT", ["mixamorig:Hips"])
    assert "Material #25" in {m["name"] for m in T["list_materials"]()}
    assert get_object_info("mixamorig:Hips")["type"] == "MESH"
