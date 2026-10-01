"""Unit tests for the geometry nodes handler: values that arrive as text."""

import importlib.util
import os
import sys
from unittest.mock import MagicMock

import pytest


def _load_handler():
    """Load addon.handlers.geometry_nodes without addon/handlers/__init__.py."""
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "geometry_nodes.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.geometry_nodes", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.geometry_nodes"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def handler():
    return _load_handler()


def _scene_with_input(socket_type):
    """Mock an object whose geometry nodes modifier has one input socket."""
    import bpy

    item = MagicMock()
    item.item_type = "SOCKET"
    item.in_out = "INPUT"
    item.name = "Amount"
    item.identifier = "Socket_1"
    item.socket_type = socket_type

    stored = {}
    modifier = MagicMock()
    modifier.type = "NODES"
    modifier.node_group.interface.items_tree = [item]
    modifier.__setitem__.side_effect = stored.__setitem__

    obj = MagicMock()
    obj.modifiers.get.return_value = modifier
    bpy.data.objects.get.return_value = obj
    return stored


def _set(handler, value):
    return handler.handle_set_geometry_node_input({
        "object_name": "Cube", "modifier_name": "GeometryNodes",
        "input_name": "Amount", "value": value,
    })


class TestTextValues:
    @pytest.mark.parametrize("socket_type, text, expected", [
        ("NodeSocketFloat", "5.5", 5.5),
        ("NodeSocketFloat", "5", 5.0),
        ("NodeSocketFloatDistance", "0.25", 0.25),
        ("NodeSocketInt", "5", 5),
        ("NodeSocketInt", "5.0", 5),
        ("NodeSocketBool", "true", True),
        ("NodeSocketBool", "False", False),
    ])
    def test_text_is_converted_for_the_socket(self, handler, socket_type, text, expected):
        stored = _scene_with_input(socket_type)
        _set(handler, text)
        assert stored["Socket_1"] == expected
        assert type(stored["Socket_1"]) is type(expected)

    def test_string_socket_keeps_numeric_text(self, handler):
        """A String socket set to "5" must stay text, not become the number 5."""
        stored = _scene_with_input("NodeSocketString")
        _set(handler, "5")
        assert stored["Socket_1"] == "5"

    def test_unparseable_text_is_passed_through(self, handler):
        stored = _scene_with_input("NodeSocketFloat")
        _set(handler, "lots")
        assert stored["Socket_1"] == "lots"

    @pytest.mark.parametrize("text", ["inf", "nan", "1e999"])
    def test_non_finite_text_is_not_converted(self, handler, text):
        stored = _scene_with_input("NodeSocketFloat")
        _set(handler, text)
        assert stored["Socket_1"] == text

    def test_real_numbers_are_untouched(self, handler):
        stored = _scene_with_input("NodeSocketFloat")
        _set(handler, 2.5)
        assert stored["Socket_1"] == 2.5
