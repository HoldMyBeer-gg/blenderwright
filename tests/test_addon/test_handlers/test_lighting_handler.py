"""Handler tests for world HDRI options and the procedural sky."""

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
                        "addon", "handlers", "lighting.py")
    spec = importlib.util.spec_from_file_location("addon.handlers.lighting", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.lighting"] = mod
    spec.loader.exec_module(mod)
    return mod


class Socket(dict):
    pass


def _node(kind):
    inputs = {"Color": SimpleNamespace(default_value=None),
              "Strength": SimpleNamespace(default_value=None),
              "Vector": SimpleNamespace(default_value=None),
              "Rotation": SimpleNamespace(default_value=[0.0, 0.0, 0.0]),
              "Surface": SimpleNamespace(default_value=None)}
    outputs = {"Color": "color-out", "Background": "bg-out", "Generated": "gen-out",
               "Vector": "vec-out"}
    return SimpleNamespace(bl_idname=kind, inputs=inputs, outputs=outputs, location=None,
                           image=None)


class Nodes(list):
    def new(self, type):
        node = _node(type)
        self.append(node)
        return node


@pytest.fixture
def world(monkeypatch):
    import bpy

    links = []
    tree = SimpleNamespace(nodes=Nodes(), links=SimpleNamespace(
        new=lambda a, b: links.append((a, b))))
    w = SimpleNamespace(node_tree=tree, use_nodes=True)
    monkeypatch.setattr(bpy.context, "scene", SimpleNamespace(world=w))
    loaded = []
    monkeypatch.setattr(bpy.data, "images", SimpleNamespace(
        load=lambda path, check_existing=True: loaded.append(path) or SimpleNamespace(
            name=os.path.basename(path))))
    monkeypatch.setattr(bpy.utils, "system_resource",
                        lambda kind, path="": f"/blender/datafiles/{path}")
    return SimpleNamespace(tree=tree, links=links, loaded=loaded)


@pytest.fixture
def h(world):
    return _load_handler()


def _kinds(world):
    return [n.bl_idname for n in world.tree.nodes]


def test_builtin_hdri_loads_from_blenders_studio_lights(h, world):
    result = h.handle_set_world_background({"builtin_hdri": "sunset", "strength": 1.2})
    assert world.loaded == ["/blender/datafiles/studiolights/world/sunset.exr"]
    assert result["builtin_hdri"] == "sunset"


def test_unknown_builtin_refused_at_the_handler(h, world):
    with pytest.raises(Exception, match="mars"):
        h.handle_set_world_background({"builtin_hdri": "../../mars"})
    assert world.loaded == []


def test_rotation_adds_a_mapping_around_z(h, world):
    h.handle_set_world_background({"builtin_hdri": "forest", "rotation": 1.5})
    mapping = next(n for n in world.tree.nodes if n.bl_idname == "ShaderNodeMapping")
    assert mapping.inputs["Rotation"].default_value[2] == 1.5
    assert "ShaderNodeTexCoord" in _kinds(world)


def test_no_rotation_no_mapping(h, world):
    h.handle_set_world_background({"builtin_hdri": "forest"})
    assert "ShaderNodeMapping" not in _kinds(world)


def test_sky(h, world):
    result = h.handle_set_world_sky({
        "sky_type": "MULTIPLE_SCATTERING", "sun_elevation": 0.1, "sun_rotation": 2.0,
        "sun_intensity": 1.0, "sun_disc": True, "altitude": 100.0, "air_density": 1.0,
        "aerosol_density": 2.0, "ozone_density": 1.0, "strength": 1.5})
    sky = next(n for n in world.tree.nodes if n.bl_idname == "ShaderNodeTexSky")
    assert (sky.sky_type, sky.sun_elevation, sky.sun_rotation, sky.aerosol_density) == (
        "MULTIPLE_SCATTERING", 0.1, 2.0, 2.0)
    bg = next(n for n in world.tree.nodes if n.bl_idname == "ShaderNodeBackground")
    assert bg.inputs["Strength"].default_value == 1.5
    assert ("color-out", bg.inputs["Color"]) in world.links
    assert result["sky_type"] == "MULTIPLE_SCATTERING"


def test_unknown_sky_type_refused(h, world):
    with pytest.raises(Exception):
        h.handle_set_world_sky({"sky_type": "__class__"})


class Collection:
    """Like Blender: collection_objects line up with objects, and carry no .object."""

    def __init__(self, name):
        self.name = name
        self.members = []
        self.collection_objects = []
        col = self

        class Objects:
            def __iter__(self):
                return iter(list(col.members))

            def link(self, obj):
                col.members.append(obj)
                col.collection_objects.append(SimpleNamespace(
                    light_linking=SimpleNamespace(link_state="INCLUDE")))

            def unlink(self, obj):
                i = col.members.index(obj)
                col.members.pop(i)
                col.collection_objects.pop(i)

        self.objects = Objects()


@pytest.fixture
def linking(monkeypatch):
    import bpy

    objs = {n: SimpleNamespace(name=n) for n in ("Hero", "Prop", "Wall")}
    key = SimpleNamespace(name="Key", light_linking=SimpleNamespace(
        receiver_collection=None, blocker_collection=None))
    objs["Key"] = key
    made = {}
    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(get=objs.get))
    monkeypatch.setattr(bpy.data, "collections", SimpleNamespace(
        new=lambda name: made.setdefault(name, Collection(name)), get=made.get))
    return SimpleNamespace(key=key, objs=objs, made=made)


def test_light_linking_receivers(h, linking):
    result = h.handle_set_light_linking({"light_name": "Key", "objects": ["Hero", "Prop"],
                                         "role": "RECEIVERS", "mode": "INCLUDE"})
    col = linking.key.light_linking.receiver_collection
    assert [o.name for o in col.members] == ["Hero", "Prop"]
    assert all(co.light_linking.link_state == "INCLUDE" for co in col.collection_objects)
    assert result["objects"] == ["Hero", "Prop"]


def test_light_linking_replaces_and_excludes(h, linking):
    h.handle_set_light_linking({"light_name": "Key", "objects": ["Hero", "Prop"],
                                "role": "RECEIVERS", "mode": "INCLUDE"})
    h.handle_set_light_linking({"light_name": "Key", "objects": ["Wall"],
                                "role": "RECEIVERS", "mode": "EXCLUDE"})
    col = linking.key.light_linking.receiver_collection
    assert [o.name for o in col.members] == ["Wall"]
    assert col.collection_objects[0].light_linking.link_state == "EXCLUDE"


def test_light_linking_blockers_and_clear(h, linking):
    h.handle_set_light_linking({"light_name": "Key", "objects": ["Wall"],
                                "role": "BLOCKERS", "mode": "INCLUDE"})
    assert linking.key.light_linking.blocker_collection is not None
    h.handle_set_light_linking({"light_name": "Key", "objects": [], "role": "BLOCKERS",
                                "mode": "INCLUDE"})
    assert linking.key.light_linking.blocker_collection is None


def test_light_linking_missing_object(h, linking):
    with pytest.raises(ValueError, match="Ghost"):
        h.handle_set_light_linking({"light_name": "Key", "objects": ["Ghost"],
                                    "role": "RECEIVERS", "mode": "INCLUDE"})
