"""Tests for file_ops handler: 5.2 operators and per-format selection keywords."""

import importlib.util
import os
import sys
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
