"""Tests for the compositor handler against a small fake node graph.

The fake follows Blender 5.2: the compositor is a CompositorNodeTree node
group, Render Layers feeds a Group Output, and node options are input
sockets (menus take their display names).
"""

import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load_handler():
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "addon", "handlers", "compositor.py")
    spec = importlib.util.spec_from_file_location("addon.handlers.compositor", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.compositor"] = mod
    spec.loader.exec_module(mod)
    return mod


class Socket:
    def __init__(self, node, name, kind, value=None, menu=None, is_output=False):
        self.node, self.name, self.type = node, name, kind
        self._value, self._menu = value, menu
        self.is_output = is_output
        self.links = []
        self.enabled = True

    @property
    def is_linked(self):
        return bool(self.links)

    @property
    def default_value(self):
        return self._value

    @default_value.setter
    def default_value(self, value):
        if self._menu is not None and value not in self._menu:
            raise TypeError(f'enum "{value}" not found in {tuple(self._menu)}')
        self._value = value


TEMPLATES = {
    "CompositorNodeRLayers": ([], [("Image", "RGBA"), ("Alpha", "VALUE")]),
    "NodeGroupOutput": ([("Image", "RGBA")], []),
    "CompositorNodeViewer": ([("Image", "RGBA")], []),
    "CompositorNodeGlare": ([("Image", "RGBA"),
                             ("Type", "MENU", "Bloom", ["Bloom", "Fog Glow", "Streaks"]),
                             ("Strength", "VALUE", 1.0), ("Clamp", "BOOLEAN", False)],
                            [("Image", "RGBA"), ("Glare", "RGBA")]),
    "CompositorNodeColorBalance": ([("Image", "RGBA"), ("Lift", "VALUE", 0.0),
                                    ("Lift", "RGBA", [1, 1, 1, 1])], [("Image", "RGBA")]),
    "CompositorNodeGroup": ([("Image", "RGBA"), ("Factor", "VALUE", 1.0),
                             ("Scale", "VECTOR", [0.8, 0.8])], [("Image", "RGBA")]),
}


class Node:
    def __init__(self, tree, bl_idname, name):
        self.tree, self.bl_idname, self.name, self.label = tree, bl_idname, name, ""
        self.location = (0, 0)
        self.node_tree = None
        ins, outs = TEMPLATES.get(bl_idname, ([("Image", "RGBA")], [("Image", "RGBA")]))
        self.inputs = [Socket(self, *spec) for spec in ins]
        self.outputs = [Socket(self, n, k, is_output=True) for n, k in outs]


class Links(list):
    def new(self, from_socket, to_socket):
        for old in list(to_socket.links):
            self.remove(old)
        link = SimpleNamespace(from_socket=from_socket, to_socket=to_socket,
                               from_node=from_socket.node, to_node=to_socket.node)
        from_socket.links.append(link)
        to_socket.links.append(link)
        self.append(link)
        return link

    def remove(self, link):
        link.from_socket.links.remove(link)
        link.to_socket.links.remove(link)
        super().remove(link)


class Nodes(list):
    def __init__(self, tree):
        super().__init__()
        self.tree = tree

    def new(self, bl_idname):
        base = {"CompositorNodeRLayers": "Render Layers", "NodeGroupOutput": "Group Output",
                "CompositorNodeViewer": "Viewer"}.get(bl_idname,
                                                      bl_idname.replace("CompositorNode", ""))
        name, n = base, 1
        while self.get(name):
            name, n = f"{base}.{n:03d}", n + 1
        node = Node(self.tree, bl_idname, name)
        self.append(node)
        return node

    def get(self, name):
        return next((n for n in self if n.name == name), None)

    def remove(self, node):
        for sock in node.inputs + node.outputs:
            for link in list(sock.links):
                self.tree.links.remove(link)
        super().remove(node)


class Tree:
    def __init__(self, name):
        self.name, self.bl_idname = name, "CompositorNodeTree"
        self.links = Links()
        self.nodes = Nodes(self)
        self.interface = MagicMock()


@pytest.fixture
def scene(monkeypatch):
    import bpy

    sc = SimpleNamespace(compositing_node_group=None,
                         render=SimpleNamespace(use_compositing=False),
                         view_layers=[SimpleNamespace(name="ViewLayer")])
    monkeypatch.setattr(bpy.context, "scene", sc)
    made = []

    def new_group(name, kind):
        tree = Tree(name)
        made.append(tree)
        return tree

    monkeypatch.setattr(bpy.data, "node_groups", SimpleNamespace(new=new_group, made=made))
    return sc


@pytest.fixture
def h(scene):
    return _load_handler()


def _chain(tree):
    """Node names from Render Layers to Group Output along the image links."""
    out = next(n for n in tree.nodes if n.bl_idname == "NodeGroupOutput")
    names, node = [out.name], out
    while node.inputs and node.inputs[0].links:
        node = node.inputs[0].links[0].from_node
        names.append(node.name)
    return list(reversed(names))


def _viewer_source(tree):
    viewer = next(n for n in tree.nodes if n.bl_idname == "CompositorNodeViewer")
    return viewer.inputs[0].links[0].from_node.name


class TestSetup:
    def test_builds_render_to_output_and_assigns_it(self, h, scene):
        result = h.handle_setup_compositor({})
        tree = scene.compositing_node_group
        assert _chain(tree) == ["Render Layers", "Group Output"]
        assert _viewer_source(tree) == "Render Layers"
        assert scene.render.use_compositing is True
        assert result["chain"] == ["Render Layers", "Group Output"]

    def test_is_idempotent(self, h, scene):
        h.handle_setup_compositor({})
        first = scene.compositing_node_group
        h.handle_setup_compositor({})
        assert scene.compositing_node_group is first

    def test_reset_starts_clean(self, h, scene):
        h.handle_add_compositor_effect({"effect": "glare", "settings": {}})
        h.handle_setup_compositor({"reset": True})
        assert _chain(scene.compositing_node_group) == ["Render Layers", "Group Output"]


class TestAddEffect:
    def test_inserts_before_the_output_and_viewer_follows(self, h, scene):
        result = h.handle_add_compositor_effect({"effect": "glare", "settings": {}})
        tree = scene.compositing_node_group
        assert _chain(tree) == ["Render Layers", "Glare", "Group Output"]
        assert _viewer_source(tree) == "Glare"
        assert result["node_name"] == "Glare"

    def test_effects_stack_in_order(self, h, scene):
        h.handle_add_compositor_effect({"effect": "glare", "settings": {}})
        h.handle_add_compositor_effect({"effect": "color_balance", "settings": {}})
        assert _chain(scene.compositing_node_group) == [
            "Render Layers", "Glare", "ColorBalance", "Group Output"]

    def test_settings_are_applied(self, h, scene):
        h.handle_add_compositor_effect({"effect": "glare", "settings": {
            "Type": "Fog Glow", "Strength": 0.4, "Clamp": True}})
        glare = scene.compositing_node_group.nodes.get("Glare")
        values = {s.name: s.default_value for s in glare.inputs}
        assert values["Type"] == "Fog Glow" and values["Strength"] == 0.4
        assert values["Clamp"] is True

    def test_bad_menu_value_lists_the_options(self, h, scene):
        with pytest.raises(ValueError, match="Fog Glow"):
            h.handle_add_compositor_effect({"effect": "glare", "settings": {"Type": "Laser"}})

    def test_unknown_input_lists_the_valid_ones(self, h, scene):
        with pytest.raises(ValueError, match="Strength"):
            h.handle_add_compositor_effect({"effect": "glare", "settings": {"Power": 2}})

    def test_failed_settings_leave_no_node_behind(self, h, scene):
        with pytest.raises(ValueError):
            h.handle_add_compositor_effect({"effect": "glare", "settings": {"Power": 2}})
        assert _chain(scene.compositing_node_group) == ["Render Layers", "Group Output"]

    def test_same_named_inputs_pick_by_value_shape(self, h, scene):
        h.handle_add_compositor_effect({"effect": "color_balance",
                                        "settings": {"Lift": [0.9, 0.9, 1.0, 1.0]}})
        node = scene.compositing_node_group.nodes.get("ColorBalance")
        lifts = [s for s in node.inputs if s.name == "Lift"]
        assert lifts[0].default_value == 0.0
        assert lifts[1].default_value == [0.9, 0.9, 1.0, 1.0]

    def test_essentials_asset_becomes_a_group_node(self, h, scene, monkeypatch):
        group = SimpleNamespace(name="Vignette")
        monkeypatch.setattr(h, "_essentials_group", lambda name: group)
        result = h.handle_add_compositor_effect({"effect": "vignette",
                                                 "settings": {"Scale": [0.9, 0.7]}})
        assert result["node_name"] == "Vignette"
        node = scene.compositing_node_group.nodes.get(result["node_name"])
        assert node.node_tree is group
        assert next(s for s in node.inputs if s.name == "Scale").default_value == [0.9, 0.7]

    def test_unknown_effect_refused_at_the_handler(self, h, scene):
        with pytest.raises(ValueError):
            h.handle_add_compositor_effect({"effect": "__class__", "settings": {}})


class TestEditRemoveList:
    def test_set_changes_an_existing_effect(self, h, scene):
        h.handle_add_compositor_effect({"effect": "glare", "settings": {}})
        h.handle_set_compositor_effect({"node_name": "Glare", "settings": {"Strength": 0.2}})
        glare = scene.compositing_node_group.nodes.get("Glare")
        assert next(s for s in glare.inputs if s.name == "Strength").default_value == 0.2

    def test_remove_reconnects(self, h, scene):
        h.handle_add_compositor_effect({"effect": "glare", "settings": {}})
        h.handle_add_compositor_effect({"effect": "color_balance", "settings": {}})
        h.handle_remove_compositor_effect({"node_name": "Glare"})
        tree = scene.compositing_node_group
        assert _chain(tree) == ["Render Layers", "ColorBalance", "Group Output"]
        assert _viewer_source(tree) == "ColorBalance"

    @pytest.mark.parametrize("name", ["Render Layers", "Group Output", "Viewer"])
    def test_core_nodes_cannot_be_removed(self, h, scene, name):
        h.handle_setup_compositor({})
        with pytest.raises(ValueError):
            h.handle_remove_compositor_effect({"node_name": name})

    def test_missing_node(self, h, scene):
        h.handle_setup_compositor({})
        with pytest.raises(ValueError, match="Nope"):
            h.handle_set_compositor_effect({"node_name": "Nope", "settings": {"x": 1}})

    def test_list_reports_chain_and_settings(self, h, scene):
        h.handle_add_compositor_effect({"effect": "glare", "settings": {"Strength": 0.5}})
        result = h.handle_list_compositor({})
        assert [e["node_name"] for e in result["chain"]] == [
            "Render Layers", "Glare", "Group Output"]
        glare = result["chain"][1]
        assert glare["effect"] == "glare"
        assert glare["settings"]["Strength"] == 0.5

    def test_list_without_compositor(self, h, scene):
        assert h.handle_list_compositor({}) == {"tree": None, "chain": []}
