"""Handler tests for collection instances."""

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
                        "addon", "handlers", "collections.py")
    spec = importlib.util.spec_from_file_location("addon.handlers.collections", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.collections"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def env(monkeypatch):
    import bpy

    props = SimpleNamespace(name="Props")
    collections = {"Props": props}
    objects, linked = {}, []

    def new_object(name, data):
        obj = SimpleNamespace(name=name, data=data, instance_type="NONE",
                              instance_collection=None, location=None,
                              rotation_euler=None, scale=None, select_set=MagicMock())
        objects[name] = obj
        return obj

    monkeypatch.setattr(bpy.data, "collections", SimpleNamespace(get=collections.get))
    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(new=new_object, get=objects.get))
    monkeypatch.setattr(bpy.context, "scene", SimpleNamespace(collection=SimpleNamespace(
        objects=SimpleNamespace(link=linked.append))))
    return SimpleNamespace(objects=objects, linked=linked, props=props)


@pytest.fixture
def h(env):
    return _load_handler()


def test_instance_is_an_empty_showing_the_collection(h, env):
    result = h.handle_create_collection_instance({
        "collection_name": "Props", "name": "Props_A", "location": [1, 2, 0],
        "rotation": [0, 0, 1.5], "scale": [2, 2, 2]})
    inst = env.objects["Props_A"]
    assert inst.data is None and inst.instance_type == "COLLECTION"
    assert inst.instance_collection is env.props
    assert (inst.location, inst.rotation_euler, inst.scale) == ([1, 2, 0], [0, 0, 1.5],
                                                                [2, 2, 2])
    assert env.linked == [inst]
    assert result == {"name": "Props_A", "collection": "Props"}


def test_name_defaults_to_the_collection(h, env):
    result = h.handle_create_collection_instance({"collection_name": "Props"})
    assert result["name"] == "Props"


def test_missing_collection(h, env):
    with pytest.raises(ValueError, match="Rocks"):
        h.handle_create_collection_instance({"collection_name": "Rocks"})


def test_make_real_needs_an_instance(h, env, monkeypatch):
    env.objects["Plain"] = SimpleNamespace(name="Plain", instance_type="NONE",
                                           instance_collection=None)
    with pytest.raises(ValueError, match="not a collection instance"):
        h.handle_make_instances_real({"object_name": "Plain"})


def test_make_real_reports_new_objects(h, env, monkeypatch):
    import bpy

    h.handle_create_collection_instance({"collection_name": "Props", "name": "Inst"})
    made = [SimpleNamespace(name="Cone.001"), SimpleNamespace(name="Lamp.001")]
    monkeypatch.setattr(h, "_activate", lambda obj: None)
    op = MagicMock(return_value={"FINISHED"})
    monkeypatch.setattr(bpy.ops.object, "duplicates_make_real", op)
    monkeypatch.setattr(bpy.context, "selected_objects", made)
    result = h.handle_make_instances_real({"object_name": "Inst", "keep_hierarchy": True})
    op.assert_called_once_with(use_base_parent=False, use_hierarchy=True)
    assert result["objects"] == ["Cone.001", "Lamp.001"]


class _Layers(list):
    def __init__(self, scene):
        super().__init__()
        self._scene = scene

    def new(self, name):
        layer = _layer(name, self._scene)
        self.append(layer)
        return layer

    def get(self, name):
        return next((v for v in self if v.name == name), None)

    def remove(self, layer):
        super().remove(layer)


def _layer_collection(name, children=()):
    return SimpleNamespace(name=name, collection=SimpleNamespace(name=name),
                           children=list(children), exclude=False, holdout=False,
                           indirect_only=False)


def _layer(name, scene):
    tree = _layer_collection("Scene Collection", [
        _layer_collection("Set", [_layer_collection("Props")])])
    return SimpleNamespace(name=name, use=True, material_override=None, world_override=None,
                           layer_collection=tree)


@pytest.fixture
def layers(monkeypatch):
    import bpy

    mod = _load_handler()
    scene = SimpleNamespace()
    scene.view_layers = _Layers(scene)
    first = scene.view_layers.new("ViewLayer")
    window = SimpleNamespace(view_layer=first)
    clay = SimpleNamespace(name="Clay")
    monkeypatch.setattr(bpy.context, "scene", scene, raising=False)
    monkeypatch.setattr(bpy.context, "window", window, raising=False)
    monkeypatch.setattr(bpy.context, "view_layer", first, raising=False)
    monkeypatch.setattr(bpy.data, "materials", {"Clay": clay})
    monkeypatch.setattr(bpy.data, "worlds", {})
    return mod, scene, window, clay


def _vl(mod, action, **extra):
    return mod.handle_manage_view_layer({"action": action} | extra)


class TestManageViewLayerHandler:
    def test_list_marks_active(self, layers):
        mod, *_ = layers
        assert _vl(mod, "LIST")["view_layers"] == [
            {"name": "ViewLayer", "active": True, "use_for_render": True,
             "material_override": None, "world_override": None}]

    def test_add_and_activate(self, layers):
        mod, scene, window, _ = layers
        _vl(mod, "ADD", view_layer="FG")
        _vl(mod, "SET_ACTIVE", view_layer="FG")
        assert window.view_layer.name == "FG"

    def test_add_duplicate_refused(self, layers):
        mod, *_ = layers
        with pytest.raises(ValueError, match="already"):
            _vl(mod, "ADD", view_layer="ViewLayer")

    def test_cannot_remove_the_last(self, layers):
        mod, *_ = layers
        with pytest.raises(ValueError, match="last"):
            _vl(mod, "REMOVE", view_layer="ViewLayer")

    def test_remove(self, layers):
        mod, scene, *_ = layers
        _vl(mod, "ADD", view_layer="FG")
        _vl(mod, "REMOVE", view_layer="FG")
        assert [v.name for v in scene.view_layers] == ["ViewLayer"]

    def test_rename(self, layers):
        mod, scene, *_ = layers
        _vl(mod, "RENAME", view_layer="ViewLayer", new_name="Beauty")
        assert scene.view_layers[0].name == "Beauty"

    def test_material_override_by_name_and_clear(self, layers):
        mod, scene, _, clay = layers
        _vl(mod, "SET", view_layer="ViewLayer", material_override="Clay")
        assert scene.view_layers[0].material_override == clay
        _vl(mod, "SET", view_layer="ViewLayer", material_override="")
        assert scene.view_layers[0].material_override is None

    def test_missing_override_target(self, layers):
        mod, *_ = layers
        with pytest.raises(ValueError, match="Sky"):
            _vl(mod, "SET", view_layer="ViewLayer", world_override="Sky")

    def test_missing_layer_lists_real_ones(self, layers):
        mod, *_ = layers
        with pytest.raises(ValueError, match="ViewLayer"):
            _vl(mod, "SET_ACTIVE", view_layer="Nope")


class TestSetLayerCollectionHandler:
    def test_nested_collection_on_active_layer(self, layers):
        mod, scene, *_ = layers
        result = mod.handle_set_layer_collection({"collection_name": "Props", "holdout": True})
        props = scene.view_layers[0].layer_collection.children[0].children[0]
        assert props.holdout is True and result["holdout"] is True

    def test_named_layer(self, layers):
        mod, scene, *_ = layers
        _vl(mod, "ADD", view_layer="FG")
        mod.handle_set_layer_collection({"collection_name": "Set", "view_layer": "FG",
                                         "exclude": True})
        assert scene.view_layers[1].layer_collection.children[0].exclude is True
        assert scene.view_layers[0].layer_collection.children[0].exclude is False

    def test_missing_collection(self, layers):
        mod, *_ = layers
        with pytest.raises(ValueError, match="Ghost"):
            mod.handle_set_layer_collection({"collection_name": "Ghost", "exclude": True})
