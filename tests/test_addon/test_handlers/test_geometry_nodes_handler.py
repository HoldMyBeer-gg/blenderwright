"""Unit tests for the geometry nodes handler: values that arrive as text."""

import importlib.util
import os
import sys
from types import SimpleNamespace
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


class TestTextValues:
    """Pure logic: how text sent for a socket is converted for its type.
    Setting the value in Blender is covered by tests_live/test_geometry_nodes.py."""

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
        value = handler._from_text(text, socket_type)
        assert value == expected and type(value) is type(expected)

    def test_string_socket_keeps_numeric_text(self, handler):
        """A String socket set to "5" must stay text, not become the number 5."""
        assert handler._from_text("5", "NodeSocketString") == "5"

    def test_unparseable_text_is_passed_through(self, handler):
        assert handler._from_text("lots", "NodeSocketFloat") == "lots"

    @pytest.mark.parametrize("text", ["inf", "nan", "1e999"])
    def test_non_finite_text_is_not_converted(self, handler, text):
        assert handler._from_text(text, "NodeSocketFloat") == text

    def test_real_numbers_are_untouched(self, handler):
        assert handler._from_text(2.5, "NodeSocketFloat") == 2.5


class TestUnknownNodeSuggestions:
    """Pure logic: which real node types to offer for a wrong guess."""

    KNOWN = {"GeometryNodeMeshCube", "GeometryNodeCubeGridTopology", "GeometryNodeMeshGrid",
             "ShaderNodeMath", "GeometryNodeSetPosition"}

    def test_tail_match_finds_the_mesh_cube(self, handler):
        message = handler._unknown_node_message("GeometryNodeCube", self.KNOWN)
        assert "GeometryNodeMeshCube" in message

    def test_close_spelling(self, handler):
        assert "GeometryNodeSetPosition" in handler._unknown_node_message(
            "GeometryNodeSetPositon", self.KNOWN)

    def test_nothing_close_gives_no_hint(self, handler):
        assert "Did you mean" not in handler._unknown_node_message("GeometryNodeZzz", self.KNOWN)


class TestEssentialsLoadOnce:
    """Appending groups one at a time duplicates their shared dependencies
    ("Randomize Transforms.001"), so the first use appends all of them together."""

    def test_one_append_brings_every_modifier_group(self, handler, monkeypatch):
        import bpy

        store = {}
        loads = []

        class Load:
            def __init__(self, path, link):
                self.dst = SimpleNamespace(node_groups=[])

            def __enter__(self):
                return SimpleNamespace(), self.dst

            def __exit__(self, *exc):
                loads.append(list(self.dst.node_groups))
                # Blender swaps the names for data-blocks inside the caller's own list
                self.dst.node_groups[:] = [store.setdefault(n, SimpleNamespace(
                    name=n, bl_idname="GeometryNodeTree")) for n in self.dst.node_groups]

        monkeypatch.setattr(bpy.data, "node_groups", SimpleNamespace(get=store.get))
        monkeypatch.setattr(bpy.data, "libraries", SimpleNamespace(load=Load))
        monkeypatch.setattr(bpy.utils, "system_resource", lambda *a, **k: "/blender/assets")

        array = handler._essentials_gn_group("Array")
        tube = handler._essentials_gn_group("Curve to Tube")

        assert len(loads) == 1
        assert set(loads[0]) == set(handler.ESSENTIALS_MODIFIERS.values())
        assert (array.name, tube.name) == ("Array", "Curve to Tube")
