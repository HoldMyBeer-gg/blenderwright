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


def _scene_with_input(socket_type):
    """Mock an object whose geometry nodes modifier has one input socket."""
    import bpy

    item = MagicMock()
    item.item_type = "SOCKET"
    item.in_out = "INPUT"
    item.name = "Amount"
    item.identifier = "Socket_1"
    item.socket_type = socket_type

    modifier = MagicMock()
    modifier.type = "NODES"
    modifier.node_group.interface.items_tree = [item]
    modifier.properties.inputs = SimpleNamespace(Socket_1=SimpleNamespace(value=None))
    # Blender 5.2 rejects the old dict-style access on the modifier
    modifier.__setitem__.side_effect = TypeError("id properties not supported for this type")
    modifier.__getitem__.side_effect = TypeError("id properties not supported for this type")

    obj = MagicMock()
    obj.modifiers.get.return_value = modifier
    bpy.data.objects.get.return_value = obj
    return _StoredInputs(modifier.properties.inputs)


class _StoredInputs:
    """Read modifier input values by identifier, as the tests expect."""

    def __init__(self, inputs):
        self._inputs = inputs

    def __getitem__(self, identifier):
        return getattr(self._inputs, identifier).value


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


class TestBlender52InputAccess:
    """Blender 5.2 moved modifier inputs to modifier.properties.inputs."""

    def test_set_writes_through_properties(self, handler):
        stored = _scene_with_input("NodeSocketInt")
        _set(handler, 10)
        assert stored["Socket_1"] == 10

    def test_list_reads_current_value(self, handler):
        stored = _scene_with_input("NodeSocketFloat")
        _set(handler, 2.5)
        inputs = handler.handle_list_geometry_node_inputs({
            "object_name": "Cube", "modifier_name": "GeometryNodes",
        })
        assert inputs[0]["identifier"] == "Socket_1"
        assert inputs[0]["value"] == stored["Socket_1"] == 2.5

    def test_list_reports_none_for_inputs_without_a_value(self, handler):
        """Geometry sockets have an entry under properties.inputs but no .value."""
        _scene_with_input("NodeSocketGeometry")
        import bpy
        modifier = bpy.data.objects.get.return_value.modifiers.get.return_value
        modifier.properties.inputs = SimpleNamespace(Socket_1=SimpleNamespace(name="Geometry"))
        inputs = handler.handle_list_geometry_node_inputs({
            "object_name": "Cube", "modifier_name": "GeometryNodes",
        })
        assert inputs[0]["value"] is None

    def test_set_rejects_inputs_without_a_value(self, handler):
        _scene_with_input("NodeSocketGeometry")
        import bpy
        modifier = bpy.data.objects.get.return_value.modifiers.get.return_value
        modifier.properties.inputs = SimpleNamespace(Socket_1=SimpleNamespace(name="Geometry"))
        with pytest.raises(ValueError):
            _set(handler, 1)


class TestAddEssentialsModifier:
    """Blender 5.2's Essentials node-group modifiers, inputs set by display name."""

    def _setup(self, monkeypatch, handler):
        import bpy

        def item(name, socket_type, identifier):
            return SimpleNamespace(item_type="SOCKET", in_out="INPUT", name=name,
                                   socket_type=f"NodeSocket{socket_type}",
                                   identifier=identifier)

        group = SimpleNamespace(name="Scatter on Surface", bl_idname="GeometryNodeTree",
                                interface=SimpleNamespace(items_tree=[
                                    item("Mesh", "Geometry", "Socket_0"),
                                    item("Amount", "Int", "Socket_1"),
                                    item("Density Method", "Menu", "Socket_2"),
                                    item("Object", "Object", "Socket_3"),
                                    item("Scale", "Vector", "Socket_4"),
                                    item("Scale", "Float", "Socket_5"),
                                ]))

        class MenuEntry:
            def __init__(self):
                self._v = "Density"
            value = property(lambda s: s._v)

            @value.setter
            def value(self, v):
                if v not in ("Density", "Amount"):
                    raise TypeError(f'enum "{v}" not found in (\'Density\', \'Amount\')')
                self._v = v

        inputs = SimpleNamespace(
            Socket_0=SimpleNamespace(name="Mesh"),
            Socket_1=SimpleNamespace(value=1000), Socket_2=MenuEntry(),
            Socket_3=SimpleNamespace(value=None), Socket_4=SimpleNamespace(value=[1, 1, 1]),
            Socket_5=SimpleNamespace(value=1.0))

        class Modifiers(list):
            def new(self, name, type):
                m = SimpleNamespace(name=name, type=type, node_group=None,
                                    properties=SimpleNamespace(inputs=inputs))
                self.append(m)
                return m

        ground = SimpleNamespace(name="Ground", modifiers=Modifiers())
        rock = SimpleNamespace(name="Rock")
        objects = {"Ground": ground, "Rock": rock}
        monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(get=objects.get))
        monkeypatch.setattr(handler, "_essentials_gn_group", lambda name: group)
        return ground, inputs, rock

    def _add(self, handler, settings):
        return handler.handle_add_essentials_modifier(
            {"object_name": "Ground", "modifier": "scatter_on_surface", "settings": settings})

    def test_adds_a_nodes_modifier_with_the_group(self, handler, monkeypatch):
        ground, _, _ = self._setup(monkeypatch, handler)
        result = self._add(handler, {})
        assert ground.modifiers[0].type == "NODES"
        assert ground.modifiers[0].node_group.name == "Scatter on Surface"
        assert result["modifier"] == "Scatter on Surface"

    def test_sets_numbers_menus_objects_and_picks_same_named_by_shape(self, handler,
                                                                       monkeypatch):
        _, inputs, rock = self._setup(monkeypatch, handler)
        result = self._add(handler, {"Amount": 50, "Density Method": "Amount",
                                     "Object": "Rock", "Scale": [2, 2, 2]})
        assert inputs.Socket_1.value == 50 and inputs.Socket_2.value == "Amount"
        assert inputs.Socket_3.value is rock
        assert inputs.Socket_4.value == [2, 2, 2] and inputs.Socket_5.value == 1.0
        assert result["inputs"]["Object"] == "Rock"

    @pytest.mark.parametrize("settings, message", [
        ({"Object": "Boulder"}, "Boulder"),
        ({"Density Method": "Sideways"}, "Amount"),
        ({"Speed": 3}, "Amount"),
        ({"Mesh": 1}, "Mesh"),
    ])
    def test_bad_settings_explain_and_leave_no_modifier(self, handler, monkeypatch,
                                                        settings, message):
        ground, _, _ = self._setup(monkeypatch, handler)
        with pytest.raises(ValueError, match=message):
            self._add(handler, settings)
        assert ground.modifiers == []

    def test_unknown_modifier_refused_at_the_handler(self, handler, monkeypatch):
        self._setup(monkeypatch, handler)
        with pytest.raises(ValueError):
            handler.handle_add_essentials_modifier(
                {"object_name": "Ground", "modifier": "__class__", "settings": {}})


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
