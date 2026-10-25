"""Five tools a live sweep of every tool on Blender 5.2.3 found broken with
their default arguments; the mocks had no way to know."""

import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load(module):
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    sys.modules.setdefault("bmesh", MagicMock())
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "addon", "handlers",
                        f"{module}.py")
    spec = importlib.util.spec_from_file_location(f"addon.handlers.{module}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"addon.handlers.{module}"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestListRecentFiles:
    """5.2: filepaths.recent_files is how many to remember (an int); the list
    is recent-files.txt in the config folder."""

    def test_reads_the_config_file(self, monkeypatch, tmp_path):
        import bpy

        mod = _load("file_ops")
        (tmp_path / "recent-files.txt").write_text("/a/one.blend\n/b/two.blend\n\n")
        monkeypatch.setattr(bpy.context.preferences.filepaths, "recent_files", 200)
        monkeypatch.setattr(bpy.utils, "user_resource",
                            lambda kind, path="": str(tmp_path / path), raising=False)
        assert mod.handle_list_recent_files({}) == ["/a/one.blend", "/b/two.blend"]

    def test_no_file_is_an_empty_list(self, monkeypatch, tmp_path):
        import bpy

        mod = _load("file_ops")
        monkeypatch.setattr(bpy.utils, "user_resource",
                            lambda kind, path="": str(tmp_path / path), raising=False)
        assert mod.handle_list_recent_files({}) == []


class TestDuplicateMaterial:
    """5.x copies the node tree with the material; node_tree is read-only."""

    def test_copy_without_touching_node_tree(self, monkeypatch):
        import bpy

        mod = _load("materials")

        class Mat:
            def __init__(self, name):
                self.name, self._tree = name, object()

            @property
            def node_tree(self):
                return self._tree

            def copy(self):
                return Mat(self.name + ".001")

        source = Mat("Wood")
        monkeypatch.setattr(bpy.data, "materials", {"Wood": source})
        result = mod.handle_duplicate_material({"material_name": "Wood", "new_name": "Oak"})
        assert result["duplicate"] == "Oak"


class TestCurvePointHandleNames:
    """The tool speaks operator names (AUTOMATIC, FREE_ALIGN); a point's
    handle type is FREE, VECTOR, ALIGNED or AUTO."""

    @pytest.mark.parametrize("given, stored", [("AUTOMATIC", "AUTO"), ("FREE_ALIGN", "FREE"),
                                               ("VECTOR", "VECTOR"), ("ALIGNED", "ALIGNED")])
    def test_mapped_to_point_names(self, given, stored):
        mod = _load("curves")
        assert mod._point_handle_type(given) == stored


class TestSelectSimilarMode:
    """FACE_* types fail in vertex select mode: 'enum FACE_AREA not found'."""

    @pytest.mark.parametrize("similar, mode", [("FACE_AREA", "FACE"), ("EDGE_LENGTH", "EDGE"),
                                               ("VERT_NORMAL", "VERT")])
    def test_select_mode_follows_the_type(self, similar, mode):
        mod = _load("selection")
        assert mod._similar_select_mode(similar) == mode


class TestNativeSlice:
    """The native boolean has no SLICE: difference on the object, intersect on a copy."""

    def test_slice_makes_two_pieces(self, monkeypatch):
        import bpy

        mod = _load("booltool")
        applied = []

        def make(name):
            mods = []
            obj = SimpleNamespace(name=name, data=SimpleNamespace(copy=lambda: "mesh copy"),
                                  users_collection=[SimpleNamespace(objects=MagicMock())])

            def new(name, type):
                m = SimpleNamespace(name=name, operation=None, object=None, owner=obj)
                mods.append(m)
                return m

            obj.modifiers = SimpleNamespace(new=new, list=mods)
            obj.copy = lambda: make(name + ".001")
            return obj

        obj, target = make("Bread"), make("Knife")
        layer = SimpleNamespace(objects=SimpleNamespace(active=obj))
        monkeypatch.setattr(bpy.context, "view_layer", layer, raising=False)
        monkeypatch.setattr(bpy.ops.object, "modifier_apply",
                            lambda modifier: applied.append(
                                (layer.objects.active.name,
                                 layer.objects.active.modifiers.list[-1].operation)))
        removed = []
        monkeypatch.setattr(bpy.data, "objects",
                            SimpleNamespace(remove=lambda o, do_unlink: removed.append(o.name)))
        piece = mod._native_slice(obj, target)
        assert applied == [("Bread", "DIFFERENCE"), ("Bread.001", "INTERSECT")]
        assert piece.name == "Bread.001" and removed == ["Knife"]
