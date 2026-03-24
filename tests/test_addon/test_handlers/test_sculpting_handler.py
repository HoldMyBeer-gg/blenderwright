"""Tests for sculpting handler — validates 5.1 API compliance."""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_sculpting_handler():
    """Load addon.handlers.sculpting directly without triggering addon/handlers/__init__.py."""
    mock_dispatcher = MagicMock()
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "sculpting.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.sculpting", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.sculpting"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def sculpting_handler():
    """Provide loaded sculpting handler module."""
    return _load_sculpting_handler()


class TestHandleSetBrushProperty:
    def test_handle_set_brush_property_size(self, sculpting_handler):
        """Setting brush size assigns brush.size as int."""
        import bpy

        brush = MagicMock()
        bpy.context.tool_settings.sculpt.brush = brush
        result = sculpting_handler.handle_set_brush_property({"property": "size", "value": 50})

        assert brush.size == 50
        assert result["property"] == "size"

    def test_handle_set_brush_property_strength(self, sculpting_handler):
        """Setting brush strength assigns brush.strength as float."""
        import bpy

        brush = MagicMock()
        bpy.context.tool_settings.sculpt.brush = brush
        result = sculpting_handler.handle_set_brush_property(
            {"property": "strength", "value": 0.75}
        )

        assert brush.strength == 0.75
        assert result["property"] == "strength"

    def test_handle_set_brush_property_stroke_method_dots(self, sculpting_handler):
        """Setting stroke_method to DOTS assigns brush.stroke_method."""
        import bpy

        brush = MagicMock()
        bpy.context.tool_settings.sculpt.brush = brush
        result = sculpting_handler.handle_set_brush_property(
            {"property": "stroke_method", "value": "DOTS"}
        )

        assert brush.stroke_method == "DOTS"
        assert result["success"] is True

    def test_handle_set_brush_property_stroke_method_invalid(self, sculpting_handler):
        """Setting stroke_method to an invalid value raises ValueError."""
        import bpy

        brush = MagicMock()
        bpy.context.tool_settings.sculpt.brush = brush
        with pytest.raises(ValueError, match="stroke_method"):
            sculpting_handler.handle_set_brush_property(
                {"property": "stroke_method", "value": "INVALID"}
            )

    def test_handle_set_brush_property_unknown(self, sculpting_handler):
        """Setting an unknown brush property raises ValueError."""
        import bpy

        brush = MagicMock()
        bpy.context.tool_settings.sculpt.brush = brush
        with pytest.raises(ValueError, match="Unknown brush property"):
            sculpting_handler.handle_set_brush_property(
                {"property": "nonexistent", "value": 1}
            )


class TestHandleEnterSculptMode:
    def test_handle_enter_sculpt_mode(self, sculpting_handler):
        """Entering sculpt mode calls mode_set with SCULPT."""
        import bpy

        mock_obj = MagicMock()
        mock_obj.type = "MESH"
        mock_obj.name = "Cube"
        mock_obj.mode = "OBJECT"
        bpy.data.objects.get = MagicMock(return_value=mock_obj)

        result = sculpting_handler.handle_enter_sculpt_mode({"object_name": "Cube"})

        bpy.ops.object.mode_set.assert_called_with(mode="SCULPT")
        assert result["mode"] == "SCULPT"
        assert result["success"] is True
