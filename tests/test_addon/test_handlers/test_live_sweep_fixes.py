"""Five tools a live sweep of every tool on Blender 5.2.3 found broken with
their default arguments; the mocks had no way to know."""

import importlib.util
import os
import sys
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
