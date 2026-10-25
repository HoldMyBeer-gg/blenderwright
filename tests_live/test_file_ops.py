"""Import, export, linking, packing and external paths in a real Blender.
Replaces the fake-bpy file_ops tests except the path-security ones (asset
library containment, where unpack may write), which test our own path
logic on a real filesystem and stay as unit tests."""

import os
import shutil

import pytest

from blenderwright import server
from blenderwright.server import mcp
from blenderwright.tools.objects import create_object, get_object_info

T = {x.name: x.fn for x in mcp._tool_manager.list_tools()}
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _names():
    return {o["name"] for o in T["list_objects"]()}


class TestExport:
    @pytest.mark.parametrize("ext", ["glb", "gltf", "fbx", "obj", "stl", "ply", "usdc", "abc"])
    def test_every_format_writes(self, scene, ext):
        out = scene / f"scene.{ext}"
        T["export_file"](str(out))
        assert out.exists() and out.stat().st_size > 0

    @pytest.mark.parametrize("ext", ["obj", "glb", "stl"])
    def test_selected_only_is_smaller(self, scene, ext):
        create_object("UV_SPHERE", name="Ball", location=[3, 0, 0])
        T["select_objects"](["Cube"])
        whole, part = scene / f"whole.{ext}", scene / f"part.{ext}"
        T["export_file"](str(whole))
        T["export_file"](str(part), selected_only=True)
        assert part.stat().st_size < whole.stat().st_size

    def test_svg_cannot_be_exported(self, scene):
        with pytest.raises(Exception):
            T["export_file"](str(scene / "x.svg"))

    def test_import_obj(self, scene):
        T["import_file"](os.path.join(ASSETS, "tri.obj"))
        assert "tri" in _names()


class TestLinkAppend:
    @pytest.fixture
    def library(self, scene):
        create_object("UV_SPHERE", name="Ball")
        T["create_collection"]("Kit")
        create_object("CUBE", name="Brick", location=[4, 0, 0])
        T["move_to_collection"](["Brick"], "Kit")
        T["save_file"](str(scene / "library.blend"))
        T["open_file"](str(scene / "scene.blend"))
        return str(scene / "library.blend")

    def test_list_contents(self, library):
        contents = T["list_blend_contents"](library)
        assert "Ball" in contents["objects"] and "Kit" in contents["collections"]

    def test_append_objects(self, library):
        T["link_or_append"](library, "OBJECT", ["Ball"])
        assert "Ball" in _names()

    def test_linked_collection_becomes_an_instance(self, library):
        result = T["link_or_append"](library, "COLLECTION", ["Kit"], link=True)
        assert result["instances"] == ["Kit"]
        assert get_object_info("Kit")["type"] == "EMPTY"

    def test_appended_collection_joins_the_scene(self, library):
        T["link_or_append"](library, "COLLECTION", ["Kit"])
        assert "Brick" in _names()

    def test_missing_names_listed_before_anything_loads(self, library):
        with pytest.raises(RuntimeError, match="Ghost"):
            T["link_or_append"](library, "OBJECT", ["Ball", "Ghost"])
        assert "Ball" not in _names()

    def test_make_local_override_and_reload(self, library):
        T["link_or_append"](library, "OBJECT", ["Ball"], link=True)
        listing = T["manage_linked_data"]("LIST")
        assert {"type": "OBJECT", "name": "Ball", "library": "library.blend"} in listing["linked"]
        T["manage_linked_data"]("OVERRIDE", data_name="Ball")
        assert T["manage_linked_data"]("LIST")["overrides"]
        T["manage_linked_data"]("RELOAD", library="library.blend")
        with pytest.raises(RuntimeError, match="not linked"):
            T["manage_linked_data"]("MAKE_LOCAL", data_name="Nope", data_type="MATERIAL")


class TestPackAndPaths:
    @pytest.fixture
    def textured(self, scene):
        """The texture sits in the project folder: on Windows CI the repo and
        the temp folder are on different drives, and no relative path crosses
        drives."""
        shutil.copy(os.path.join(ASSETS, "tex.png"), scene / "tex.png")
        T["add_texture_node"]("Material", str(scene / "tex.png"))
        return scene

    def test_pack_then_unpack_beside_the_blend(self, textured):
        packed = T["pack_resources"](autopack=True)
        assert packed["packed"] and packed["autopack"] is True
        T["save_file"]()
        unpacked = T["unpack_resources"]()
        assert all(item["filepath"].startswith("//") for item in unpacked["unpacked"])

    def test_external_paths_list_relative_and_find(self, textured):
        listing = T["manage_external_paths"]("LIST")
        assert listing["missing"] == 0 and listing["files"]
        T["save_file"]()
        relative = T["manage_external_paths"]("MAKE_RELATIVE")
        assert all(f["path"].startswith("//") for f in relative["files"])
        found = T["manage_external_paths"]("FIND_MISSING", directory=str(textured))
        assert found["missing"] == 0

    def test_searching_a_filesystem_root_is_refused_by_the_addon(self, scene):
        reply = server.get_connection().send_command("manage_external_paths",
                                                     {"action": "FIND_MISSING", "directory": "/"})
        assert reply["status"] == "error"
