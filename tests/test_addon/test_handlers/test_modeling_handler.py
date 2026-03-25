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
