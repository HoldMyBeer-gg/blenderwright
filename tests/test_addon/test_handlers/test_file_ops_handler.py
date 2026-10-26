"""Path security in the file_ops handler on a real filesystem: asset files must stay
inside their library. The rest of file_ops is tested live (tests_live/test_file_ops.py)."""

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
