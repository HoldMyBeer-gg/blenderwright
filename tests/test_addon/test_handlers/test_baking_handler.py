"""Handler tests for bake_texture against small fakes."""

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
                        "addon", "handlers", "baking.py")
    spec = importlib.util.spec_from_file_location("addon.handlers.baking", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.baking"] = mod
    spec.loader.exec_module(mod)
    return mod


class Nodes(list):
    active = None

    def new(self, kind):
        node = SimpleNamespace(bl_idname=kind, image=None, name=f"{kind}.{len(self)}")
        self.append(node)
        return node


def _material(name):
    return SimpleNamespace(name=name, node_tree=SimpleNamespace(nodes=Nodes()))


def _obj(name, uvs=True, materials=("Wood",)):
    return SimpleNamespace(
        name=name, type="MESH",
        data=SimpleNamespace(uv_layers=["UVMap"] if uvs else []),
        material_slots=[SimpleNamespace(material=_material(m)) for m in materials],
        select_set=MagicMock())


@pytest.fixture
def env(monkeypatch, tmp_path):
    import bpy

    objects = {"Low": _obj("Low"), "High": _obj("High"), "NoUV": _obj("NoUV", uvs=False),
               "NoMat": _obj("NoMat", materials=())}
    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(get=objects.get))
    images = []

    def new_image(name, width, height, alpha=False, float_buffer=False):
        img = SimpleNamespace(name=name, size=(width, height), float_buffer=float_buffer,
                              colorspace_settings=SimpleNamespace(name="sRGB"),
                              filepath_raw="", file_format="", save=MagicMock())
        images.append(img)
        return img

    monkeypatch.setattr(bpy.data, "images", SimpleNamespace(new=new_image))
    scene = SimpleNamespace(render=SimpleNamespace(engine="BLENDER_EEVEE"),
                            cycles=SimpleNamespace(samples=4096))
    monkeypatch.setattr(bpy.context, "scene", scene)
    monkeypatch.setattr(bpy.context, "view_layer", SimpleNamespace(
        objects=SimpleNamespace(active=None)))
    monkeypatch.setattr(bpy.context, "selected_objects", [])
    monkeypatch.setattr(bpy.context, "object", None)
    bake = MagicMock(return_value={"FINISHED"})
    monkeypatch.setattr(bpy.ops.object, "bake", bake)
    return SimpleNamespace(objects=objects, images=images, scene=scene, bake=bake,
                           out=str(tmp_path / "map.png"))


@pytest.fixture
def h(env):
    return _load_handler()


def _bake(h, env, **extra):
    params = {"object_name": "Low", "bake_type": "DIFFUSE", "filepath": env.out,
              "resolution": 256, "margin": 8, "samples": 4, "diffuse_color_only": True,
              "normal_space": "TANGENT", **extra}
    return h.handle_bake_texture(params)


def test_bakes_and_saves(h, env):
    result = _bake(h, env)
    kwargs = env.bake.call_args.kwargs
    assert kwargs["type"] == "DIFFUSE" and kwargs["pass_filter"] == {"COLOR"}
    assert kwargs["use_selected_to_active"] is False and kwargs["margin"] == 8
    img = env.images[0]
    assert img.size == (256, 256) and img.filepath_raw == env.out
    img.save.assert_called_once()
    assert result["filepath"] == env.out


def test_engine_and_samples_are_restored(h, env):
    _bake(h, env)
    assert env.scene.render.engine == "BLENDER_EEVEE"
    assert env.scene.cycles.samples == 4096


def test_restored_even_when_the_bake_fails(h, env):
    env.bake.side_effect = RuntimeError("Error: No valid selected objects")
    with pytest.raises(RuntimeError):
        _bake(h, env)
    assert env.scene.render.engine == "BLENDER_EEVEE"
    assert env.objects["Low"].material_slots[0].material.node_tree.nodes == []


def test_temporary_image_nodes_are_removed(h, env):
    _bake(h, env)
    nodes = env.objects["Low"].material_slots[0].material.node_tree.nodes
    assert nodes == []


def test_normal_maps_are_non_color_and_tangent(h, env):
    _bake(h, env, bake_type="NORMAL")
    assert env.images[0].colorspace_settings.name == "Non-Color"
    assert env.bake.call_args.kwargs["normal_space"] == "TANGENT"


def test_high_to_low(h, env):
    _bake(h, env, bake_type="NORMAL", source_object="High", cage_extrusion=0.05,
          max_ray_distance=0.2)
    kwargs = env.bake.call_args.kwargs
    assert kwargs["use_selected_to_active"] is True
    assert (kwargs["cage_extrusion"], kwargs["max_ray_distance"]) == (0.05, 0.2)
    env.objects["High"].select_set.assert_any_call(True)


@pytest.mark.parametrize("name, message", [
    ("NoUV", "UV"), ("NoMat", "material"), ("Ghost", "Ghost"),
])
def test_unbakeable_objects_are_explained(h, env, name, message):
    with pytest.raises(ValueError, match=message):
        _bake(h, env, object_name=name)
    env.bake.assert_not_called()


def test_unknown_type_and_extension_refused_at_the_handler(h, env, tmp_path):
    with pytest.raises(ValueError):
        _bake(h, env, bake_type="__class__")
    with pytest.raises(ValueError):
        _bake(h, env, filepath=str(tmp_path / "evil.py"))
