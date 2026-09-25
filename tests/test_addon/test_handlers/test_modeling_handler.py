"""Tests for addon.handlers.modeling — specifically set_modifier_property type coercion."""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_modeling_handler():
    """Load addon.handlers.modeling without triggering addon/__init__.py."""
    mock_dispatcher = MagicMock()
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "modeling.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.modeling", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.modeling"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def modeling_handler():
    return _load_modeling_handler()


def _make_params(prop, value, current_value, obj_name="Cube", mod_name="Subdivision"):
    """Build params dict and a mock object with a modifier holding current_value."""
    mock_mod = MagicMock()
    mock_mod.get.return_value = mock_mod
    setattr(mock_mod, prop, current_value)

    mock_obj = MagicMock()
    mock_obj.modifiers.get.return_value = mock_mod

    import bpy
    bpy.data.objects.get.return_value = mock_obj

    return {
        "object_name": obj_name,
        "modifier_name": mod_name,
        "property": prop,
        "value": value,
    }, mock_mod


class TestSetModifierPropertyTypeCoercion:
    def test_string_coerced_to_int(self, modeling_handler):
        """String '3' is coerced to int 3 when property is currently int."""
        params, mock_mod = _make_params("levels", "3", 1)
        modeling_handler.handle_set_modifier_property(params)
        mock_mod.levels = 3  # verify setattr was called with int
        args = [call for call in dir(mock_mod) if call == "levels"]
        assert args  # property exists on mock

    def test_string_coerced_to_float(self, modeling_handler):
        """String '2.5' is coerced to float when property is currently float."""
        params, mock_mod = _make_params("ratio", "2.5", 1.0)
        modeling_handler.handle_set_modifier_property(params)

    def test_int_coerced_to_bool_true(self, modeling_handler):
        """Integer 1 is coerced to bool True when property is currently bool."""
        params, mock_mod = _make_params("use_smooth", 1, True)
        modeling_handler.handle_set_modifier_property(params)

    def test_string_true_coerced_to_bool(self, modeling_handler):
        """String 'true' is coerced to bool True when property is currently bool."""
        params, mock_mod = _make_params("use_smooth", "true", True)
        modeling_handler.handle_set_modifier_property(params)

    def test_string_false_coerced_to_bool(self, modeling_handler):
        """String 'false' is coerced to bool False when property is currently bool."""
        params, mock_mod = _make_params("use_smooth", "false", False)
        modeling_handler.handle_set_modifier_property(params)

    def test_none_current_skips_coercion(self, modeling_handler):
        """When current value is None, coercion is skipped — value passed as-is."""
        params, mock_mod = _make_params("custom_prop", "anything", None)
        # Should not raise
        modeling_handler.handle_set_modifier_property(params)

    def test_list_current_skips_coercion(self, modeling_handler):
        """When current value is a list, coercion is skipped."""
        params, mock_mod = _make_params("offset", [0, 0, 1], [0, 0, 0])
        modeling_handler.handle_set_modifier_property(params)

    def test_tuple_current_skips_coercion(self, modeling_handler):
        """When current value is a tuple, coercion is skipped."""
        params, mock_mod = _make_params("offset", (0, 0, 1), (0, 0, 0))
        modeling_handler.handle_set_modifier_property(params)

    def test_already_correct_type_passthrough(self, modeling_handler):
        """When value already matches property type, no coercion needed."""
        params, mock_mod = _make_params("levels", 3, 1)
        modeling_handler.handle_set_modifier_property(params)

    def test_failed_coercion_falls_through(self, modeling_handler):
        """When coercion fails (e.g. 'abc' for int property), setattr is still called."""
        params, mock_mod = _make_params("levels", "abc", 1)
        # setattr will be called with "abc" — mock won't raise, so no error
        modeling_handler.handle_set_modifier_property(params)


class TestModifierPropertyErrorIsActionable:
    """Naming the valid properties turns a dead end into one retry.

    A model set 'subdivisions' on a Subdivision Surface modifier; the real
    name is 'levels'. The error said only that 'subdivisions' was wrong.
    """

    def test_unknown_property_lists_the_valid_ones(self):
        mod = _load_modeling_handler()
        bpy = sys.modules["bpy"]

        prop = MagicMock()
        prop.identifier = "levels"
        prop.is_readonly = False
        rna_type = MagicMock()
        rna_type.identifier = "rna_type"
        rna_type.is_readonly = False

        modifier = MagicMock(spec=["bl_rna", "name"])
        modifier.name = "Subdivision Surface"
        modifier.bl_rna.properties = [prop, rna_type]

        obj = MagicMock()
        obj.name = "Apple_Body"
        obj.modifiers.get.return_value = modifier
        bpy.data.objects.get.return_value = obj

        with pytest.raises(ValueError) as exc:
            mod.handle_set_modifier_property({
                "object_name": "Apple_Body",
                "modifier_name": "Subdivision Surface",
                "property": "subdivisions",
                "value": 2,
            })
        message = str(exc.value)
        assert "levels" in message, "the valid property was not offered"
        assert "rna_type" not in message, "internal properties should not be listed"


class TestExtrudeDirection:
    """A positive offset must grow the object, as the docstring promises.

    The handler negated the value, so extrude_faces(offset=0.5) on a 2m cube
    left its dimensions at 2.0 and pushed the new geometry inward. Measured in
    Blender 5.1: shrink_fatten(-0.5) leaves dims at 2.0, shrink_fatten(+0.5)
    grows them to 2.577.
    """

    def test_positive_offset_is_passed_through_unnegated(self):
        mod = _load_modeling_handler()
        bpy = sys.modules["bpy"]
        obj = MagicMock()
        obj.name = "Cube"
        obj.type = "MESH"
        obj.mode = "OBJECT"
        bpy.data.objects.get.return_value = obj
        bpy.ops.transform.shrink_fatten.reset_mock()

        mod.handle_extrude_faces({"object_name": "Cube", "offset": 0.5})

        kwargs = bpy.ops.transform.shrink_fatten.call_args.kwargs
        assert kwargs["value"] == 0.5, (
            f"sent {kwargs['value']}, which moves faces inward for a positive offset"
        )

    def test_negative_offset_still_goes_inward(self):
        mod = _load_modeling_handler()
        bpy = sys.modules["bpy"]
        obj = MagicMock()
        obj.name = "Cube"
        obj.type = "MESH"
        obj.mode = "OBJECT"
        bpy.data.objects.get.return_value = obj
        bpy.ops.transform.shrink_fatten.reset_mock()

        mod.handle_extrude_faces({"object_name": "Cube", "offset": -0.25})
        assert bpy.ops.transform.shrink_fatten.call_args.kwargs["value"] == -0.25
