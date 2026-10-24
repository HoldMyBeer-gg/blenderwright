"""Tests for addon.handlers.modeling: specifically set_modifier_property type coercion."""

import os
import sys
import importlib.util
from types import SimpleNamespace
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


def _rna(kind, readonly=False, fixed=None, array=False):
    return SimpleNamespace(type=kind, is_readonly=readonly, is_array=array,
                           fixed_type=SimpleNamespace(identifier=fixed) if fixed else None)


class FakeModifier:
    """A modifier whose RNA declares its properties, like Blender's."""

    PROPS = {
        "levels": _rna("INT"), "ratio": _rna("FLOAT"), "use_smooth": _rna("BOOLEAN"),
        "wrap_method": _rna("ENUM"), "offset": _rna("FLOAT", array=True),
        "target": _rna("POINTER", fixed="Object"),
        "collection": _rna("POINTER", fixed="Collection"),
        "node_group": _rna("POINTER", fixed="NodeTree"),
        "is_active": _rna("BOOLEAN", readonly=True),
        "projectors": _rna("COLLECTION"),
        "name": _rna("STRING"),
    }

    def __init__(self, kind="SUBSURF"):
        self.type = kind
        self.name = "Mod"
        self.levels, self.ratio, self.use_smooth = 1, 1.0, False
        self.wrap_method, self.offset = "NEAREST_SURFACEPOINT", [0.0, 0.0, 0.0]
        self.target = self.collection = self.node_group = None
        self.bl_rna = SimpleNamespace(properties=self.PROPS)


@pytest.fixture
def mod_env(monkeypatch, modeling_handler):
    import bpy

    modifier = FakeModifier()
    obj = SimpleNamespace(name="Cube", modifiers=SimpleNamespace(get={"Mod": modifier}.get))
    ground = SimpleNamespace(name="Ground")
    rocks = SimpleNamespace(name="Rocks")
    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(
        get={"Cube": obj, "Ground": ground}.get))
    monkeypatch.setattr(bpy.data, "collections", SimpleNamespace(get={"Rocks": rocks}.get))
    return SimpleNamespace(mod=modifier, ground=ground, rocks=rocks)


def _set(handler, prop, value):
    return handler.handle_set_modifier_property({
        "object_name": "Cube", "modifier_name": "Mod", "property": prop, "value": value})


class TestSetModifierPropertyTypeCoercion:
    @pytest.mark.parametrize("prop, value, expected", [
        ("levels", "3", 3), ("ratio", "2.5", 2.5), ("use_smooth", 1, True),
        ("use_smooth", "true", True), ("use_smooth", "false", False), ("levels", 2, 2),
        ("offset", [0, 0, 1], [0, 0, 1]), ("wrap_method", "PROJECT", "PROJECT"),
    ])
    def test_values_are_coerced_to_the_property_type(self, modeling_handler, mod_env,
                                                     prop, value, expected):
        _set(modeling_handler, prop, value)
        assert getattr(mod_env.mod, prop) == expected


class TestObjectAndCollectionSettings:
    """Shrinkwrap, Lattice, Curve, Surface Deform and others need an object."""

    def test_object_by_name(self, modeling_handler, mod_env):
        result = _set(modeling_handler, "target", "Ground")
        assert mod_env.mod.target is mod_env.ground
        assert result["value"] == "Ground"

    def test_collection_by_name(self, modeling_handler, mod_env):
        _set(modeling_handler, "collection", "Rocks")
        assert mod_env.mod.collection is mod_env.rocks

    def test_missing_object(self, modeling_handler, mod_env):
        with pytest.raises(ValueError, match="Ghost"):
            _set(modeling_handler, "target", "Ghost")

    def test_unsupported_pointer_type(self, modeling_handler, mod_env):
        with pytest.raises(ValueError, match="node_group"):
            _set(modeling_handler, "node_group", "Tree")


class TestModifierPropertyErrorIsActionable:
    """Naming the valid properties turns a dead end into one retry."""

    def test_unknown_property_lists_the_valid_ones(self, modeling_handler, mod_env):
        with pytest.raises(ValueError) as exc:
            _set(modeling_handler, "subdivisions", 2)
        message = str(exc.value)
        assert "levels" in message and "target" in message
        assert "is_active" not in message and "projectors" not in message

    @pytest.mark.parametrize("prop", ["__class__", "bl_rna", "is_active", "projectors",
                                      "type"])
    def test_only_declared_writable_settings(self, modeling_handler, mod_env, prop):
        with pytest.raises(ValueError, match=prop):
            _set(modeling_handler, prop, 1)


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
