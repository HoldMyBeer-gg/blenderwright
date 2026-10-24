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
