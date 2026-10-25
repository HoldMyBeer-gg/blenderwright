"""Tests for file_ops handler: 5.2 operators and per-format selection keywords."""

import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load_handler():
    """Load addon.handlers.file_ops without addon/handlers/__init__.py."""
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "file_ops.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.file_ops", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.file_ops"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def handler():
    import bpy

    bpy.ops.reset_mock()
    return _load_handler()


def _export(handler, filepath, selected_only=True):
    return handler.handle_export_file({"filepath": filepath, "selected_only": selected_only})


class TestExportSelection:
    @pytest.mark.parametrize("filepath, operator, keyword", [
        ("/tmp/a.fbx", ("export_scene", "fbx"), "use_selection"),
        ("/tmp/a.glb", ("export_scene", "gltf"), "use_selection"),
        ("/tmp/a.obj", ("wm", "obj_export"), "export_selected_objects"),
        ("/tmp/a.stl", ("wm", "stl_export"), "export_selected_objects"),
        ("/tmp/a.ply", ("wm", "ply_export"), "export_selected_objects"),
        ("/tmp/a.usdc", ("wm", "usd_export"), "selected_objects_only"),
        ("/tmp/a.abc", ("wm", "alembic_export"), "selected"),
    ])
    def test_each_exporter_gets_its_own_keyword(self, handler, filepath, operator, keyword):
        import bpy

        op = getattr(getattr(bpy.ops, operator[0]), operator[1])
        op.return_value = {"FINISHED"}

        _export(handler, filepath)

        assert op.call_args.kwargs[keyword] is True

    def test_whole_scene_export_passes_no_selection_keyword(self, handler):
        import bpy

        bpy.ops.wm.obj_export.return_value = {"FINISHED"}
        _export(handler, "/tmp/a.obj", selected_only=False)

        assert bpy.ops.wm.obj_export.call_args.kwargs == {"filepath": "/tmp/a.obj"}

    def test_cancelled_export_raises(self, handler):
        import bpy

        bpy.ops.wm.stl_export.return_value = {"CANCELLED"}
        with pytest.raises(RuntimeError):
            _export(handler, "/tmp/a.stl")


class TestFormats:
    def test_fbx_import_uses_the_native_importer(self, handler):
        import bpy

        bpy.ops.wm.fbx_import.return_value = {"FINISHED"}
        handler.handle_import_file({"filepath": "/tmp/a.fbx"})

        bpy.ops.wm.fbx_import.assert_called_once_with(filepath="/tmp/a.fbx")
        bpy.ops.import_scene.fbx.assert_not_called()

    def test_svg_cannot_be_exported(self, handler):
        with pytest.raises(ValueError):
            _export(handler, "/tmp/a.svg")

    @pytest.mark.parametrize("ext", [".dae", ".x3d"])
    def test_removed_formats_are_unsupported(self, handler, ext):
        with pytest.raises(ValueError):
            handler.handle_import_file({"filepath": f"/tmp/a{ext}"})
        with pytest.raises(ValueError):
            _export(handler, f"/tmp/a{ext}")


class FakeLibrary:
    """bpy.data.libraries.load: lists names, then fills dst lists in place on exit."""

    CONTENTS = {"objects": ["Cone", "Lamp"], "collections": ["Props"],
                "materials": ["Brass"], "node_groups": [], "worlds": ["Sky"],
                "meshes": ["Cone"]}

    def __init__(self):
        self.calls = []

    def load(self, path, link=False):
        lib = self

        class Ctx:
            def __enter__(self):
                self.src = SimpleNamespace(**{k: list(v) for k, v in lib.CONTENTS.items()})
                self.dst = SimpleNamespace(**{k: [] for k in lib.CONTENTS})
                lib.calls.append({"path": path, "link": link, "dst": self.dst})
                return self.src, self.dst

            def __exit__(self, *exc):
                if exc[0] is None:
                    for kind, names in vars(self.dst).items():
                        names[:] = [SimpleNamespace(name=n + (".001" if not link else ""),
                                                    library="kit" if link else None)
                                    for n in names]
                return False

        return Ctx()


@pytest.fixture
def lib(handler, monkeypatch):
    import bpy

    fake = FakeLibrary()
    monkeypatch.setattr(bpy.data, "libraries", fake)
    scene_objects, scene_children = [], []
    monkeypatch.setattr(bpy.context, "scene", SimpleNamespace(collection=SimpleNamespace(
        objects=SimpleNamespace(link=scene_objects.append),
        children=SimpleNamespace(link=scene_children.append))))
    made = []

    def new_object(name, data):
        obj = SimpleNamespace(name=name, data=data, instance_type="NONE",
                              instance_collection=None)
        made.append(obj)
        return obj

    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(new=new_object))
    monkeypatch.setattr(bpy.context.preferences.filepaths, "use_scripts_auto_execute", True)
    fake.scene_objects, fake.scene_children, fake.made = scene_objects, scene_children, made
    return fake


class TestLinkAppend:
    def test_list_reads_names_and_loads_nothing(self, handler, lib, tmp_path):
        path = tmp_path / "kit.blend"
        path.write_bytes(b"x")
        result = handler.handle_list_blend_contents({"filepath": str(path)})
        assert result["objects"] == ["Cone", "Lamp"] and result["worlds"] == ["Sky"]
        assert all(not names for names in vars(lib.calls[0]["dst"]).values())

    def test_scripts_are_disabled_first(self, handler, lib, tmp_path):
        import bpy

        path = tmp_path / "kit.blend"
        path.write_bytes(b"x")
        handler.handle_list_blend_contents({"filepath": str(path)})
        assert bpy.context.preferences.filepaths.use_scripts_auto_execute is False

    def test_append_objects_into_the_scene(self, handler, lib, tmp_path):
        path = tmp_path / "kit.blend"
        path.write_bytes(b"x")
        result = handler.handle_link_or_append({"filepath": str(path), "data_type": "OBJECT",
                                                "names": ["Cone"], "link": False})
        assert result["items"] == {"Cone": "Cone.001"}
        assert [o.name for o in lib.scene_objects] == ["Cone.001"]

    def test_linked_collection_becomes_an_instance(self, handler, lib, tmp_path):
        path = tmp_path / "kit.blend"
        path.write_bytes(b"x")
        result = handler.handle_link_or_append({"filepath": str(path),
                                                "data_type": "COLLECTION",
                                                "names": ["Props"], "link": True})
        inst = lib.made[0]
        assert inst.instance_type == "COLLECTION" and inst.instance_collection.name == "Props"
        assert result["instances"] == [inst.name]
        assert lib.scene_children == []

    def test_appended_collection_joins_the_scene(self, handler, lib, tmp_path):
        path = tmp_path / "kit.blend"
        path.write_bytes(b"x")
        handler.handle_link_or_append({"filepath": str(path), "data_type": "COLLECTION",
                                       "names": ["Props"], "link": False})
        assert [c.name for c in lib.scene_children] == ["Props.001"]

    def test_missing_names_listed_before_anything_loads(self, handler, lib, tmp_path):
        path = tmp_path / "kit.blend"
        path.write_bytes(b"x")
        with pytest.raises(ValueError, match="Rock"):
            handler.handle_link_or_append({"filepath": str(path), "data_type": "OBJECT",
                                           "names": ["Rock"], "link": False})
        assert lib.scene_objects == []

    @pytest.mark.parametrize("filepath, data_type", [
        ("kit.py", "OBJECT"), ("kit.blend", "TEXT"), ("missing.blend", "OBJECT"),
    ])
    def test_handler_refuses_bad_input(self, handler, lib, tmp_path, filepath, data_type):
        (tmp_path / "kit.py").write_text("x")
        (tmp_path / "kit.blend").write_bytes(b"x")
        with pytest.raises(ValueError):
            handler.handle_link_or_append({"filepath": str(tmp_path / filepath),
                                           "data_type": data_type, "names": ["Cone"]})


def _packed_image(name, filepath):
    return SimpleNamespace(name=name, filepath=filepath, packed_file=object())


@pytest.fixture
def packing(handler):
    import bpy

    bpy.data.images = [_packed_image("Wood", "//textures/wood.png"),
                       SimpleNamespace(name="Loose", filepath="/a/b.png", packed_file=None)]
    bpy.data.sounds = []
    bpy.data.fonts = []
    bpy.data.volumes = []
    bpy.data.filepath = "/work/scene.blend"
    bpy.data.use_autopack = False
    return handler


class TestPackResourcesHandler:
    def test_packs_and_lists_what_is_packed(self, packing):
        import bpy

        result = packing.handle_pack_resources({})
        bpy.ops.file.pack_all.assert_called_once_with()
        assert result["packed"] == [{"type": "image", "name": "Wood"}]
        assert result["autopack"] is False

    def test_autopack(self, packing):
        import bpy

        result = packing.handle_pack_resources({"autopack": True})
        assert bpy.data.use_autopack is True and result["autopack"] is True


class TestUnpackResourcesHandler:
    def test_writes_next_to_the_blend_only(self, packing):
        import bpy

        packing.handle_unpack_resources({"overwrite": False})
        bpy.ops.file.unpack_all.assert_called_once_with(method="USE_LOCAL")

    def test_overwrite_uses_write_local(self, packing):
        import bpy

        packing.handle_unpack_resources({"overwrite": True})
        bpy.ops.file.unpack_all.assert_called_once_with(method="WRITE_LOCAL")

    def test_reports_where_files_went(self, packing):
        result = packing.handle_unpack_resources({"overwrite": False})
        assert result["unpacked"] == [
            {"type": "image", "name": "Wood", "filepath": "//textures/wood.png"},
        ]

    def test_unsaved_file_is_refused(self, packing):
        import bpy

        bpy.data.filepath = ""
        with pytest.raises(ValueError, match="Save"):
            packing.handle_unpack_resources({"overwrite": False})
        bpy.ops.file.unpack_all.assert_not_called()

    def test_registered(self, handler):
        handler.register()
        calls = {c.args[0] for c in handler.dispatcher.register_handler.call_args_list}
        assert {"pack_resources", "unpack_resources"} <= calls


@pytest.fixture
def paths(handler, monkeypatch, tmp_path):
    import bpy

    present = tmp_path / "wood.png"
    present.write_bytes(b"x")
    blocks = [(SimpleNamespace(name="wood.png", id_type="IMAGE"), "//wood.png"),
              (SimpleNamespace(name="rock.png", id_type="IMAGE"), "//gone/rock.png")]

    def foreach(visit, **kwargs):
        for idb, path in blocks:
            visit(idb, path, SimpleNamespace(is_readonly=False))

    monkeypatch.setattr(bpy.data, "file_path_foreach", foreach, raising=False)
    monkeypatch.setattr(bpy.data, "filepath", str(tmp_path / "scene.blend"), raising=False)
    monkeypatch.setattr(bpy.path, "abspath",
                        lambda p: str(tmp_path / p[2:]) if p.startswith("//") else p)
    return handler


class TestManageExternalPathsHandler:
    def test_list_flags_missing(self, paths):
        result = paths.handle_manage_external_paths({"action": "LIST"})
        assert result["files"] == [
            {"type": "IMAGE", "name": "wood.png", "path": "//wood.png", "exists": True},
            {"type": "IMAGE", "name": "rock.png", "path": "//gone/rock.png", "exists": False},
        ]
        assert result["missing"] == 1

    def test_make_relative(self, paths):
        import bpy

        paths.handle_manage_external_paths({"action": "MAKE_RELATIVE"})
        bpy.ops.file.make_paths_relative.assert_called_once_with()

    def test_relative_needs_saved_file(self, paths, monkeypatch):
        import bpy

        monkeypatch.setattr(bpy.data, "filepath", "")
        with pytest.raises(ValueError, match="Save"):
            paths.handle_manage_external_paths({"action": "MAKE_RELATIVE"})

    def test_find_missing(self, paths, tmp_path):
        import bpy

        paths.handle_manage_external_paths({"action": "FIND_MISSING",
                                            "directory": str(tmp_path)})
        bpy.ops.file.find_missing_files.assert_called_once_with(
            directory=str(tmp_path), find_all=False)

    def test_find_missing_rechecks_directory(self, paths, tmp_path):
        import bpy

        with pytest.raises(ValueError):
            paths.handle_manage_external_paths({"action": "FIND_MISSING",
                                                "directory": str(tmp_path / "nope")})
        bpy.ops.file.find_missing_files.assert_not_called()

    def test_unknown_action(self, paths):
        with pytest.raises(ValueError):
            paths.handle_manage_external_paths({"action": "DELETE"})

    def test_find_missing_refuses_root(self, paths):
        import bpy

        with pytest.raises(ValueError):
            paths.handle_manage_external_paths({"action": "FIND_MISSING",
                                                "directory": os.path.abspath(os.sep)})
        bpy.ops.file.find_missing_files.assert_not_called()


@pytest.fixture
def library(handler, monkeypatch, tmp_path):
    import bpy

    root = tmp_path / "lib"
    (root / "props").mkdir(parents=True)
    (root / "props" / "chairs.blend").write_bytes(b"BLENDER")
    (root / "notes.txt").write_text("x")
    outside = tmp_path / "outside.blend"
    outside.write_bytes(b"BLENDER")
    (root / "escape.blend").symlink_to(outside)
    libs = [SimpleNamespace(name="Mine", path=str(root), enabled=True, use_remote_url=False),
            SimpleNamespace(name="Online", path=str(tmp_path), enabled=True,
                            use_remote_url=True),
            SimpleNamespace(name="Off", path=str(root), enabled=False, use_remote_url=False)]
    monkeypatch.setattr(bpy.context.preferences.filepaths, "asset_libraries", libs)
    monkeypatch.setattr(bpy.utils, "system_resource",
                        lambda kind, path="": str(tmp_path / "essentials"), raising=False)
    return handler, root


class _FakeLoad:
    """libraries.load: only Chair is marked as an asset."""

    def __init__(self, path, assets_only=False, link=False):
        self.names = ["Chair"] if assets_only else ["Chair", "Plain"]

    def __enter__(self):
        return SimpleNamespace(objects=self.names), SimpleNamespace()

    def __exit__(self, *exc):
        return False


class TestAssetLibraryHandler:
    def test_lists_local_enabled_libraries_and_essentials(self, library):
        h, root = library
        result = h.handle_list_asset_libraries({})
        assert [lib["name"] for lib in result["libraries"]] == ["Essentials", "Mine"]

    def test_remote_library_is_refused(self, library):
        h, _ = library
        with pytest.raises(ValueError, match="Online"):
            h.handle_list_assets({"library": "Online"})

    def test_file_resolves_inside_the_library(self, library):
        h, root = library
        assert h._library_file("Mine", "props/chairs.blend") == str(
            (root / "props" / "chairs.blend").resolve())

    @pytest.mark.parametrize("rel", ["../outside.blend", "escape.blend", "notes.txt",
                                     "/etc/x.blend", "missing.blend"])
    def test_file_outside_or_wrong_is_refused(self, library, rel):
        h, _ = library
        with pytest.raises(ValueError):
            h._library_file("Mine", rel)

    def test_place_delegates_to_link_or_append(self, library, monkeypatch):
        import bpy

        h, root = library
        monkeypatch.setattr(bpy.data.libraries, "load", _FakeLoad)
        seen = {}
        monkeypatch.setattr(h, "handle_link_or_append",
                            lambda params: seen.update(params) or {"ok": True})
        h.handle_place_asset({"library": "Mine", "file": "props/chairs.blend",
                              "asset_type": "OBJECT", "name": "Chair", "link": False})
        assert seen == {"filepath": str((root / "props" / "chairs.blend").resolve()),
                        "data_type": "OBJECT", "names": ["Chair"], "link": False}

    def test_only_marked_assets_are_placed(self, library, monkeypatch):
        import bpy

        h, _ = library
        monkeypatch.setattr(bpy.data.libraries, "load", _FakeLoad)
        monkeypatch.setattr(h, "handle_link_or_append", lambda params: {"ok": True})
        with pytest.raises(ValueError, match="not an asset"):
            h.handle_place_asset({"library": "Mine", "file": "props/chairs.blend",
                                  "asset_type": "OBJECT", "name": "Plain", "link": False})


class _ID:
    def __init__(self, name, library=None, **extra):
        self.name, self.library, self.override_library = name, library, None
        self.__dict__.update(extra)

    def make_local(self):
        self.library = None
        return self


@pytest.fixture
def linked(handler, monkeypatch):
    import bpy

    lib = SimpleNamespace(name="chairs.blend", filepath="/lib/chairs.blend", is_missing=False,
                          reload=MagicMock())
    mesh = _ID("ChairMesh", lib)
    scene_objects = SimpleNamespace(unlink=MagicMock())
    chair_linked = _ID("Chair", lib, data=mesh, type="MESH",
                       users_collection=[SimpleNamespace(library=None, objects=scene_objects)])
    chair_local = _ID("Chair", None, data=None, type="MESH", users_collection=[])
    oak = _ID("Oak", lib)

    def override(scene, view_layer, do_fully_editable=False, reference=None):
        made = _ID("Chair", None, type="MESH")
        made.override_library = SimpleNamespace(reference=chair_linked)
        return made

    chair_linked.override_hierarchy_create = override
    monkeypatch.setattr(bpy.data, "libraries", [lib])
    monkeypatch.setattr(bpy.data, "objects", [chair_local, chair_linked])
    monkeypatch.setattr(bpy.data, "materials", [oak])
    for attr in ("collections", "node_groups", "worlds", "meshes"):
        monkeypatch.setattr(bpy.data, attr, [mesh] if attr == "meshes" else [])
    return handler, lib, chair_linked, chair_local, oak, mesh, scene_objects


def _linked(h, action, **extra):
    return h.handle_manage_linked_data({"action": action} | extra)


class TestManageLinkedDataHandler:
    def test_list(self, linked):
        h, *_ = linked
        result = _linked(h, "LIST")
        assert result["libraries"] == [{"name": "chairs.blend", "filepath": "/lib/chairs.blend",
                                        "missing": False}]
        assert {"type": "OBJECT", "name": "Chair", "library": "chairs.blend"} in result["linked"]

    def test_make_local_picks_the_linked_one_and_its_mesh(self, linked):
        h, lib, chair_linked, chair_local, oak, mesh, _ = linked
        _linked(h, "MAKE_LOCAL", data_name="Chair", data_type="OBJECT")
        assert chair_linked.library is None and mesh.library is None

    def test_make_local_of_local_data_refused(self, linked):
        h, *_ = linked
        with pytest.raises(ValueError, match="not linked"):
            _linked(h, "MAKE_LOCAL", data_name="Nope", data_type="MATERIAL")

    def test_override_replaces_the_linked_object_in_the_scene(self, linked):
        h, lib, chair_linked, *_rest, scene_objects = linked
        result = _linked(h, "OVERRIDE", data_name="Chair", data_type="OBJECT")
        scene_objects.unlink.assert_called_once_with(chair_linked)
        assert result["override"] == "Chair"

    def test_reload(self, linked):
        h, lib, *_ = linked
        _linked(h, "RELOAD", library="chairs.blend")
        lib.reload.assert_called_once_with()

    def test_reload_unknown_library(self, linked):
        h, *_ = linked
        with pytest.raises(ValueError, match="chairs.blend"):
            _linked(h, "RELOAD", library="other.blend")
