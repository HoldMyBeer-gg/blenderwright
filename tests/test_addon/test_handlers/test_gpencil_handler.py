"""Unit tests for annotation handler (Blender 5.x Annotation API)."""

import sys
import os
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_gpencil_handler():
    """Load addon.handlers.gpencil directly without triggering addon/handlers/__init__.py."""
    mock_dispatcher = MagicMock()
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "gpencil.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.gpencil", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.gpencil"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def gpencil_handler():
    """Provide loaded gpencil handler module."""
    return _load_gpencil_handler()


class TestHandleCreateAnnotation:
    def test_handle_create_annotation(self, gpencil_handler):
        """Handler calls bpy.data.annotations.new(name) and returns annotation name."""
        import bpy

        mock_ann = MagicMock()
        mock_ann.name = "TestAnnotation"
        bpy.data.annotations.new.return_value = mock_ann

        result = gpencil_handler.handle_create_annotation({"name": "TestAnnotation"})

        bpy.data.annotations.new.assert_called_with("TestAnnotation")
        assert result["name"] == "TestAnnotation"

    def test_handle_create_annotation_default_name(self, gpencil_handler):
        """Handler uses default name when none provided."""
        import bpy

        mock_ann = MagicMock()
        mock_ann.name = "Annotation"
        bpy.data.annotations.new.return_value = mock_ann

        result = gpencil_handler.handle_create_annotation({})

        bpy.data.annotations.new.assert_called_with("Annotation")
        assert "name" in result


class TestHandleAddAnnotationLayer:
    def test_handle_add_annotation_layer(self, gpencil_handler):
        """Handler accesses annotation data and calls layers.new(name=layer_name)."""
        import bpy

        mock_layer = MagicMock()
        mock_layer.info = "Layer1"
        mock_ann = MagicMock()
        mock_ann.name = "TestAnnotation"
        mock_ann.layers.new.return_value = mock_layer
        bpy.data.annotations.get.return_value = mock_ann

        result = gpencil_handler.handle_add_annotation_layer({
            "annotation_name": "TestAnnotation",
            "layer_name": "Layer1",
        })

        bpy.data.annotations.get.assert_called_with("TestAnnotation")
        mock_ann.layers.new.assert_called_with(name="Layer1")
        assert result["annotation"] == "TestAnnotation"
        assert result["layer"] == "Layer1"

    def test_handle_add_annotation_layer_not_found(self, gpencil_handler):
        """Handler raises ValueError when annotation not found."""
        import bpy

        bpy.data.annotations.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            gpencil_handler.handle_add_annotation_layer({
                "annotation_name": "Missing",
                "layer_name": "Layer1",
            })


class TestHandleRemoveAnnotationLayer:
    def test_handle_remove_annotation_layer(self, gpencil_handler):
        """Handler removes named layer from annotation data."""
        import bpy

        mock_layer = MagicMock()
        mock_ann = MagicMock()
        mock_ann.name = "TestAnnotation"
        mock_ann.layers.get.return_value = mock_layer
        bpy.data.annotations.get.return_value = mock_ann

        result = gpencil_handler.handle_remove_annotation_layer({
            "annotation_name": "TestAnnotation",
            "layer_name": "Layer1",
        })

        mock_ann.layers.remove.assert_called_with(mock_layer)
        assert result["removed_layer"] == "Layer1"

    def test_handle_remove_annotation_layer_not_found(self, gpencil_handler):
        """Handler raises ValueError when layer not found."""
        import bpy

        mock_ann = MagicMock()
        mock_ann.name = "TestAnnotation"
        mock_ann.layers.get.return_value = None
        bpy.data.annotations.get.return_value = mock_ann

        with pytest.raises(ValueError, match="not found"):
            gpencil_handler.handle_remove_annotation_layer({
                "annotation_name": "TestAnnotation",
                "layer_name": "Missing",
            })


class TestHandleAddAnnotationStroke:
    def test_handle_add_annotation_stroke(self, gpencil_handler):
        """Handler creates stroke on frame, sets co and pressure. Does NOT set .strength."""
        import bpy

        mock_point_0 = MagicMock(spec=["co", "pressure"])
        mock_point_1 = MagicMock(spec=["co", "pressure"])
        mock_stroke = MagicMock()

        def getitem(i):
            return [mock_point_0, mock_point_1][i]

        mock_stroke.points.__getitem__.side_effect = getitem

        mock_frame = MagicMock()
        mock_frame.strokes.new.return_value = mock_stroke

        mock_layer = MagicMock()
        mock_layer.info = "Layer1"
        mock_layer.frames = [mock_frame]

        mock_ann = MagicMock()
        mock_ann.name = "TestAnnotation"
        mock_ann.layers.get.return_value = mock_layer
        bpy.data.annotations.get.return_value = mock_ann
        bpy.context.scene.frame_current = 1

        points = [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0]]
        result = gpencil_handler.handle_add_annotation_stroke({
            "annotation_name": "TestAnnotation",
            "layer_name": "Layer1",
            "points": points,
            "pressure": 0.8,
        })

        assert result["point_count"] == 2
        assert result["annotation"] == "TestAnnotation"

    def test_handle_add_annotation_stroke_no_strength_set(self, gpencil_handler):
        """Verify that the handler does NOT set .strength on stroke points."""
        import inspect

        source = inspect.getsource(gpencil_handler.handle_add_annotation_stroke)
        assert ".strength" not in source, (
            "handle_add_annotation_stroke must not set .strength on points"
        )


class TestNoLegacyGpencilAPI:
    def test_no_gpencil_add_operator(self):
        """Handler file does not contain 'gpencil_add' string (removed in Blender 5.x)."""
        handler_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "addon", "handlers", "gpencil.py",
        )
        with open(handler_path) as f:
            content = f.read()
        assert "gpencil_add" not in content, (
            "Handler must not reference removed bpy.ops.object.gpencil_add"
        )

    def test_no_gpencil_type_check(self):
        """Handler file does not contain old GPENCIL type checks."""
        handler_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "addon", "handlers", "gpencil.py",
        )
        with open(handler_path) as f:
            content = f.read()
        assert 'obj.type != "GPENCIL"' not in content, (
            "Handler must not use obj.type != 'GPENCIL' check"
        )
        assert 'obj.type == "GPENCIL"' not in content, (
            "Handler must not use obj.type == 'GPENCIL' check"
        )
