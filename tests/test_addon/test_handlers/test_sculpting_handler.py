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


class TestRemeshVoxelBudget:
    """voxel_size is bounded 0.001-10.0 with no relation to object size.

    0.001 on a 2m object is a 2000^3 grid. Blender stops responding, the
    caller's socket burns all 150 retries (about five minutes) and the call
    dies with a timeout that says nothing about why. The only layer that can
    judge this is the handler, which knows the object's dimensions.
    """

    def _obj(self, dims):
        obj = MagicMock()
        obj.name = "Thing"
        obj.type = "MESH"
        obj.mode = "OBJECT"
        obj.dimensions = dims
        return obj

    def test_absurd_grid_is_refused_before_blender_sees_it(self):
        mod = _load_sculpting_handler()
        bpy = sys.modules["bpy"]
        bpy.data.objects.get.return_value = self._obj((2.0, 2.0, 2.0))
        with pytest.raises(ValueError) as exc:
            mod.handle_remesh({"object_name": "Thing", "voxel_size": 0.001,
                               "mode": "VOXEL"})
        message = str(exc.value)
        assert "voxel" in message.lower()
        assert "0.0" in message, "the error should suggest a workable size"

    def test_a_sane_voxel_size_is_allowed(self):
        mod = _load_sculpting_handler()
        bpy = sys.modules["bpy"]
        bpy.data.objects.get.return_value = self._obj((2.0, 2.0, 2.0))
        mod.handle_remesh({"object_name": "Thing", "voxel_size": 0.05,
                           "mode": "VOXEL"})

    def test_budget_scales_with_the_object(self):
        """0.05 is fine on a 2m object and absurd on a 200m one."""
        mod = _load_sculpting_handler()
        bpy = sys.modules["bpy"]
        bpy.data.objects.get.return_value = self._obj((200.0, 200.0, 200.0))
        with pytest.raises(ValueError):
            mod.handle_remesh({"object_name": "Thing", "voxel_size": 0.05,
                               "mode": "VOXEL"})

    def test_non_voxel_modes_do_not_apply_the_budget(self):
        """SHARP/SMOOTH/BLOCKS ignore voxel_size entirely."""
        mod = _load_sculpting_handler()
        bpy = sys.modules["bpy"]
        bpy.data.objects.get.return_value = self._obj((2.0, 2.0, 2.0))
        mod.handle_remesh({"object_name": "Thing", "voxel_size": 0.001,
                           "mode": "SHARP"})

    def test_result_says_voxel_size_was_ignored_for_other_modes(self):
        """It previously reported success as though it had been used."""
        mod = _load_sculpting_handler()
        bpy = sys.modules["bpy"]
        bpy.data.objects.get.return_value = self._obj((2.0, 2.0, 2.0))
        result = mod.handle_remesh({"object_name": "Thing", "voxel_size": 0.001,
                                    "mode": "SHARP"})
        assert result.get("voxel_size") is None
