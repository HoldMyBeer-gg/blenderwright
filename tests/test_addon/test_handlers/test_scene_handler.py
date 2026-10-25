"""Tests for scene addon handlers: extension detection."""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_scene_handler():
    """Load addon.handlers.scene directly without triggering addon/handlers/__init__.py."""
    mock_dispatcher = MagicMock()
    mock_render_guard_mod = MagicMock()

    # Create an addon mock with dispatcher set so `from .. import dispatcher` resolves correctly
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher
    sys.modules["addon.render_guard"] = mock_render_guard_mod

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "scene.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.scene", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.scene"] = mod
    spec.loader.exec_module(mod)
    return mod, mock_dispatcher


@pytest.fixture
def scene_handler():
    """Provide loaded scene handler module and mock dispatcher."""
    mod, mock_dispatcher = _load_scene_handler()
    return mod, mock_dispatcher


class TestGetInstalledExtensions:
    def test_no_extensions_installed(self, scene_handler):
        """Returns empty installed list when no known extensions are in preferences.addons."""
        import bpy

        mod, _ = scene_handler
        mock_addons = MagicMock()
        mock_addons.__contains__ = MagicMock(return_value=False)
        bpy.context.preferences.addons = mock_addons

        result = mod.handle_get_installed_extensions({})

        assert result == {"installed": []}

    def test_legacy_key_bool_tool_detected(self, scene_handler):
        """Returns bool_tool when legacy key 'object_boolean_tools' is in preferences.addons."""
        import bpy

        mod, _ = scene_handler
        enabled_keys = {"object_boolean_tools"}
        mock_addons = MagicMock()
        mock_addons.__contains__ = MagicMock(side_effect=lambda k: k in enabled_keys)
        bpy.context.preferences.addons = mock_addons

        result = mod.handle_get_installed_extensions({})

        assert result == {"installed": ["bool_tool"]}

    def test_ext_key_bool_tool_detected(self, scene_handler):
        """Returns bool_tool when bl_ext key is in preferences.addons (Blender 4.2+)."""
        import bpy

        mod, _ = scene_handler
        enabled_keys = {"bl_ext.blender_org.object_boolean_tools"}
        mock_addons = MagicMock()
        mock_addons.__contains__ = MagicMock(side_effect=lambda k: k in enabled_keys)
        bpy.context.preferences.addons = mock_addons

        result = mod.handle_get_installed_extensions({})

        assert result == {"installed": ["bool_tool"]}

    def test_all_three_extensions_detected(self, scene_handler):
        """Returns all three extension IDs when all are enabled."""
        import bpy

        mod, _ = scene_handler
        enabled_keys = {
            "object_boolean_tools",
            "mesh_looptools",
            "node_wrangler",
        }
        mock_addons = MagicMock()
        mock_addons.__contains__ = MagicMock(side_effect=lambda k: k in enabled_keys)
        bpy.context.preferences.addons = mock_addons

        result = mod.handle_get_installed_extensions({})

        assert set(result["installed"]) == {"bool_tool", "looptools", "node_wrangler"}

    def test_get_installed_extensions_registered_in_dispatcher(self, scene_handler):
        """get_installed_extensions command is registered when register() is called."""
        mod, mock_dispatcher = scene_handler

        mod.register()

        registered_commands = [
            call.args[0] for call in mock_dispatcher.register_handler.call_args_list
        ]

        assert "get_installed_extensions" in registered_commands


class FakeUnitSettings:
    """Mimics Blender 5.2: valid unit names depend on the current system."""

    LENGTHS = {"METRIC": {"METERS", "CENTIMETERS"}, "IMPERIAL": {"FEET", "INCHES"}}

    def __init__(self):
        object.__setattr__(self, "system", "METRIC")
        object.__setattr__(self, "length_unit", "METERS")
        object.__setattr__(self, "mass_unit", "KILOGRAMS")
        object.__setattr__(self, "time_unit", "SECONDS")
        object.__setattr__(self, "temperature_unit", "KELVIN")
        object.__setattr__(self, "scale_length", 1.0)
        object.__setattr__(self, "system_rotation", "DEGREES")
        object.__setattr__(self, "use_separate", False)

    def __setattr__(self, key, value):
        if key == "length_unit" and value not in self.LENGTHS.get(self.system, ()):
            raise TypeError(f'enum "{value}" not found')
        object.__setattr__(self, key, value)


@pytest.fixture
def units(scene_handler):
    import bpy

    fake = FakeUnitSettings()
    bpy.context.scene.unit_settings = fake
    return scene_handler[0], fake


class TestSetUnitsHandler:
    def test_system_is_set_before_units(self, units):
        mod, fake = units
        result = mod.handle_set_units({"length_unit": "INCHES", "system": "IMPERIAL"})
        assert fake.system == "IMPERIAL" and fake.length_unit == "INCHES"
        assert result["length_unit"] == "INCHES"

    def test_reports_every_setting(self, units):
        mod, _ = units
        result = mod.handle_set_units({"scale_length": 0.01})
        assert result == {
            "system": "METRIC", "scale_length": 0.01, "length_unit": "METERS",
            "mass_unit": "KILOGRAMS", "time_unit": "SECONDS",
            "temperature_unit": "KELVIN", "system_rotation": "DEGREES",
            "use_separate": False,
        }

    def test_wrong_unit_for_system_names_the_system(self, units):
        mod, _ = units
        with pytest.raises(ValueError, match="METRIC"):
            mod.handle_set_units({"length_unit": "INCHES"})

    def test_unknown_keys_are_ignored(self, units):
        mod, fake = units
        mod.handle_set_units({"__class__": "x", "scale_length": 2.0})
        assert fake.scale_length == 2.0
        assert type(fake) is FakeUnitSettings

    def test_registered(self, scene_handler):
        mod, dispatcher = scene_handler
        mod.register()
        dispatcher.register_handler.assert_any_call("set_units", mod.handle_set_units)
