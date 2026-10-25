"""Handler tests for build_geometry_nodes against a small fake node graph."""

import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load():
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "addon", "handlers", "geometry_nodes.py")
    spec = importlib.util.spec_from_file_location("addon.handlers.geometry_nodes", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.geometry_nodes"] = mod
    spec.loader.exec_module(mod)
    return mod


class Prop:
    def __init__(self, type, readonly=False):
        self.type, self.is_readonly = type, readonly


class Socket:
    def __init__(self, name, identifier=None, bl_idname="NodeSocketFloat", enabled=True,
                 default_value=0.0):
        self.name, self.identifier = name, identifier or name
        self.bl_idname, self.enabled, self.default_value = bl_idname, enabled, default_value
        self.is_linked = False


NODE_TYPES = {
    "ShaderNodeMath": lambda: ([Socket("Value"), Socket("Value", "Value_001"),
                                Socket("Value", "Value_002", enabled=False)],
                               [Socket("Value")], {"operation": Prop("ENUM"),
                                                   "use_clamp": Prop("BOOLEAN")}),
    "GeometryNodeMeshGrid": lambda: ([Socket("Size X"), Socket("Vertices X",
                                      bl_idname="NodeSocketInt", default_value=3)],
                                     [Socket("Mesh", bl_idname="NodeSocketGeometry")], {}),
    "GeometryNodeObjectInfo": lambda: ([Socket("Object", bl_idname="NodeSocketObject",
                                               default_value=None)],
                                       [Socket("Geometry", bl_idname="NodeSocketGeometry")], {}),
}


class Node:
    def __init__(self, bl_idname, group):
        self.bl_idname, self.name, self.location = bl_idname, bl_idname, (0, 0)
        if bl_idname == "NodeGroupInput":
            self.name, self.inputs = "Group Input", []
            self.outputs = [Socket(i.name) for i in group.interface.items if i.in_out == "INPUT"]
            props = {}
        elif bl_idname == "NodeGroupOutput":
            self.name, self.outputs = "Group Output", []
            self.inputs = [Socket(i.name) for i in group.interface.items if i.in_out == "OUTPUT"]
            props = {}
        else:
            self.inputs, self.outputs, props = NODE_TYPES[bl_idname]()
        props = dict(props, name=Prop("STRING"), location=Prop("FLOAT"),
                     rna_type=Prop("POINTER", readonly=True))
        self.bl_rna = SimpleNamespace(properties=props)
        self.operation, self.use_clamp = "ADD", False


class Group:
    def __init__(self, name):
        self.name = name
        self.interface = SimpleNamespace(items=[])
        self.interface.new_socket = self._new_socket
        self.links_made = []
        self.node_list = []
        self.nodes = SimpleNamespace(new=self._new_node)
        self.links = SimpleNamespace(new=lambda a, b: self.links_made.append((a, b)))

    def _new_socket(self, name, in_out, socket_type):
        item = SimpleNamespace(name=name, in_out=in_out, socket_type=socket_type,
                               default_value=None, min_value=None, max_value=None)
        self.interface.items.append(item)
        return item

    def _new_node(self, type):
        node = Node(type, self)
        self.node_list.append(node)
        return node


@pytest.fixture
def gn(monkeypatch):
    import bpy

    mod = _load()
    made, removed = [], []

    def new_group(name, type):
        g = Group(name)
        made.append(g)
        return g

    groups = SimpleNamespace(new=new_group, remove=lambda g: removed.append(g))
    monkeypatch.setattr(bpy.data, "node_groups", groups)
    old_group = Group("Old")
    modifier = SimpleNamespace(name="GN", type="NODES", node_group=old_group)
    obj = SimpleNamespace(name="Ground", modifiers=SimpleNamespace(
        get=lambda n: modifier if n == "GN" else None,
        new=MagicMock(return_value=modifier)))
    target = SimpleNamespace(name="Target")
    monkeypatch.setattr(bpy.data, "objects", {"Ground": obj, "Target": target})
    monkeypatch.setattr(mod, "_known_node_types", lambda: set(NODE_TYPES), raising=False)
    monkeypatch.setattr(mod, "_base_node_props", lambda: {"name", "location", "rna_type"},
                        raising=False)
    return mod, made, removed, modifier, old_group, target


def _build(mod, spec):
    return mod.handle_build_geometry_nodes({"object_name": "Ground", "modifier_name": "GN",
                                            "spec": {"inputs": [], "outputs": [], "nodes": [],
                                                     "links": []} | spec})


def _node(group, name):
    return next(n for n in group.node_list if n.name == name)


class TestBuild:
    def test_swaps_in_the_new_group_on_success(self, gn):
        mod, made, removed, modifier, old, _ = gn
        result = _build(mod, {"nodes": [{"name": "grid", "type": "GeometryNodeMeshGrid",
                                         "settings": {}, "inputs": {"Vertices X": 12}}]})
        assert modifier.node_group is made[0] and removed == []
        assert _node(made[0], "grid").inputs[1].default_value == 12
        assert result["nodes"] == 3  # grid plus Group Input and Output

    def test_failure_removes_the_half_built_group_and_keeps_the_old(self, gn):
        mod, made, removed, modifier, old, _ = gn
        with pytest.raises(ValueError, match="Nope"):
            _build(mod, {"nodes": [{"name": "m", "type": "ShaderNodeMath", "settings": {},
                                    "inputs": {"Nope": 1}}]})
        assert modifier.node_group is old and removed == made

    def test_settings_before_inputs_and_rna_only(self, gn):
        mod, made, *_ = gn
        _build(mod, {"nodes": [{"name": "m", "type": "ShaderNodeMath",
                                "settings": {"operation": "SINE"}, "inputs": {}}]})
        assert _node(made[0], "m").operation == "SINE"

    @pytest.mark.parametrize("key", ["name", "location", "rna_type", "bl_idname", "missing"])
    def test_unsafe_settings_refused(self, gn, key):
        mod, made, removed, *_ = gn
        with pytest.raises(ValueError, match="setting"):
            _build(mod, {"nodes": [{"name": "m", "type": "ShaderNodeMath",
                                    "settings": {key: 1}, "inputs": {}}]})
        assert removed == made

    def test_unknown_node_type(self, gn):
        mod, made, removed, *_ = gn
        with pytest.raises(ValueError, match="node type"):
            _build(mod, {"nodes": [{"name": "x", "type": "GeometryNodeTeleport",
                                    "settings": {}, "inputs": {}}]})

    def test_links_by_name_identifier_and_index(self, gn):
        mod, made, *_ = gn
        _build(mod, {
            "nodes": [{"name": "a", "type": "ShaderNodeMath", "settings": {}, "inputs": {}},
                      {"name": "b", "type": "ShaderNodeMath", "settings": {}, "inputs": {}}],
            "links": [["a", "Value", "b", "Value_001"], ["a", 0, "b", 0]]})
        a, b = _node(made[0], "a"), _node(made[0], "b")
        # The first link is the Geometry pass-through: nothing else feeds Group Output
        assert made[0].links_made[1:] == [(a.outputs[0], b.inputs[1]),
                                          (a.outputs[0], b.inputs[0])]

    def test_geometry_passes_through_and_group_sockets_link(self, gn):
        mod, made, *_ = gn
        _build(mod, {"inputs": [{"name": "Size", "type": "FLOAT", "default": 4.0}],
                     "nodes": [{"name": "grid", "type": "GeometryNodeMeshGrid",
                                "settings": {}, "inputs": {}}],
                     "links": [["Group Input", "Size", "grid", "Size X"],
                               ["grid", "Mesh", "Group Output", "Geometry"]]})
        group = made[0]
        assert [(i.name, i.in_out) for i in group.interface.items] == [
            ("Geometry", "INPUT"), ("Size", "INPUT"), ("Geometry", "OUTPUT")]
        assert group.interface.items[1].default_value == 4.0

    def test_object_socket_takes_a_name(self, gn):
        mod, made, *_, target = gn
        _build(mod, {"nodes": [{"name": "info", "type": "GeometryNodeObjectInfo",
                                "settings": {}, "inputs": {"Object": "Target"}}]})
        assert _node(made[0], "info").inputs[0].default_value is target

    def test_missing_object_for_socket(self, gn):
        mod, *_ = gn
        with pytest.raises(ValueError, match="Ghost"):
            _build(mod, {"nodes": [{"name": "info", "type": "GeometryNodeObjectInfo",
                                    "settings": {}, "inputs": {"Object": "Ghost"}}]})


class TestKnownNodeTypes:
    """5.2 creates bpy.types classes lazily: __subclasses__() of GeometryNode is
    empty until a class is touched, so add_geometry_node refused every node."""

    def test_found_by_name_not_by_subclass_scan(self, monkeypatch):
        import bpy

        mod = _load()

        class Lazy(type):
            def __subclasses__(cls):
                return []  # what 5.2 reports before a class is touched

        class Node(metaclass=Lazy):
            pass

        class GeometryNode(Node):
            pass

        class FunctionNode(Node):
            pass

        class ShaderNode(Node):
            pass

        class GeometryNodeMeshGrid(GeometryNode):
            pass

        class GeometryNodeFieldToListItem:  # an item type, not a node
            pass

        lazy = SimpleNamespace(Node=Node, GeometryNode=GeometryNode, FunctionNode=FunctionNode,
                               ShaderNode=ShaderNode, GeometryNodeMeshGrid=GeometryNodeMeshGrid,
                               GeometryNodeFieldToListItem=GeometryNodeFieldToListItem)
        monkeypatch.setattr(bpy, "types", lazy)
        known = mod._known_node_types()
        assert "GeometryNodeMeshGrid" in known
        assert "GeometryNodeFieldToListItem" not in known

    def test_add_geometry_node_uses_it(self, monkeypatch):
        import bpy

        mod = _load()
        group = Group("GN")
        monkeypatch.setattr(bpy.data, "objects", [])
        monkeypatch.setattr(bpy.data, "node_groups", {"GN": group})
        monkeypatch.setattr(mod, "_known_node_types", lambda: {"ShaderNodeMath"})
        mod.handle_add_geometry_node({"modifier_name": "GN", "node_type": "ShaderNodeMath",
                                      "location": [0, 0]})
        with pytest.raises(ValueError, match="Unknown node type"):
            mod.handle_add_geometry_node({"modifier_name": "GN",
                                          "node_type": "GeometryNodeMeshGrid",
                                          "location": [0, 0]})
