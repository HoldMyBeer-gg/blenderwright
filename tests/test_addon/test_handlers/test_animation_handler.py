"""Tests for animation handler: F-curves live in action channelbags since 5.0."""

import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load_handler():
    """Load addon.handlers.animation without addon/handlers/__init__.py."""
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "animation.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.animation", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.animation"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def handler():
    return _load_handler()


def _keyframe(frame, value):
    return SimpleNamespace(co=(frame, value), interpolation="BEZIER")


def _animated_object(fcurves):
    """Mock an object whose action slot holds the given F-curves."""
    import bpy
    from bpy_extras import anim_utils

    action = SimpleNamespace()  # 5.x actions have no .fcurves
    obj = MagicMock()
    obj.name = "Cube"
    obj.animation_data.action = action
    bpy.data.objects.get = MagicMock(return_value=obj)
    anim_utils.action_get_channelbag_for_slot.return_value = SimpleNamespace(fcurves=fcurves)
    return obj


def _fcurve(data_path, index, keyframes):
    return SimpleNamespace(data_path=data_path, array_index=index, keyframe_points=keyframes)


class TestListKeyframes:
    def test_reads_fcurves_from_the_channelbag(self, handler):
        _animated_object([_fcurve("location", 0, [_keyframe(10, 2.0), _keyframe(1, 0.0)])])

        keyframes = handler.handle_list_keyframes({"object_name": "Cube"})

        assert [k["frame"] for k in keyframes] == [1, 10]
        assert keyframes[0]["data_path"] == "location"

    def test_slot_without_channelbag_has_no_keyframes(self, handler):
        from bpy_extras import anim_utils

        _animated_object([])
        anim_utils.action_get_channelbag_for_slot.return_value = None

        assert handler.handle_list_keyframes({"object_name": "Cube"}) == []


class TestSetInterpolation:
    def test_updates_only_the_matching_channel(self, handler):
        x = [_keyframe(1, 0.0), _keyframe(10, 1.0)]
        y = [_keyframe(1, 0.0)]
        _animated_object([_fcurve("location", 0, x), _fcurve("location", 1, y)])

        result = handler.handle_set_interpolation({
            "object_name": "Cube", "data_path": "location[0]", "interpolation": "LINEAR",
        })

        assert result["keyframes_updated"] == 2
        assert [k.interpolation for k in x] == ["LINEAR", "LINEAR"]
        assert y[0].interpolation == "BEZIER"

    def test_no_matching_keyframes_raises(self, handler):
        _animated_object([_fcurve("rotation_euler", 0, [_keyframe(1, 0.0)])])

        with pytest.raises(ValueError):
            handler.handle_set_interpolation({
                "object_name": "Cube", "data_path": "location", "interpolation": "LINEAR",
            })


class FakeDriver:
    def __init__(self):
        self.type = "SCRIPTED"
        self._expression = ""
        self.is_simple_expression = True
        self.is_valid = True
        self.use_self = False

        class Variables(list):
            def new(self):
                var = SimpleNamespace(name="var", type="SINGLE_PROP",
                                      targets=[SimpleNamespace(), SimpleNamespace()])
                self.append(var)
                return var

        self.variables = Variables()

    @property
    def expression(self):
        return self._expression

    @expression.setter
    def expression(self, value):
        self._expression = value
        # Blender's verdict; the fake trusts nothing with a dot or a quote
        self.is_simple_expression = not any(c in value for c in ".'\"[")


@pytest.fixture
def driven(monkeypatch):
    import bpy

    removed = []
    curves = []

    def driver_add(path, index=-1):
        fc = SimpleNamespace(data_path=path, array_index=max(index, 0), driver=FakeDriver())
        curves.append(fc)
        return fc

    def driver_remove(path, index=-1):
        before = len(curves)
        curves[:] = [c for c in curves if not (c.data_path == path and (
            index == -1 or c.array_index == index))]
        removed.append((path, index))
        return before != len(curves)

    cube = MagicMock()
    cube.name = "Cube"
    cube.driver_add = driver_add
    cube.driver_remove = driver_remove
    cube.path_resolve = lambda path, coerce=True: 0.0
    cube.animation_data = SimpleNamespace(drivers=curves)
    light = SimpleNamespace(name="Light")
    objects = {"Cube": cube, "Light": light}
    bpy.data.objects.get = MagicMock(side_effect=objects.get)
    return SimpleNamespace(cube=cube, curves=curves, removed=removed, light=light)


def _add(handler, **kw):
    params = {"object_name": "Cube", "data_path": "location", "index": 2,
              "driver_type": "SCRIPTED", "expression": "lx * 2",
              "variables": [{"name": "lx", "type": "TRANSFORMS", "object": "Light",
                             "transform_type": "LOC_X", "transform_space": "WORLD_SPACE"}]}
    params.update(kw)
    return handler.handle_add_driver(params)


class TestDrivers:
    def test_adds_a_transform_driver(self, handler, driven):
        result = _add(handler)
        fc = driven.curves[0]
        var = fc.driver.variables[0]
        assert (fc.data_path, fc.array_index, fc.driver.expression) == ("location", 2, "lx * 2")
        assert (var.name, var.type, var.targets[0].id, var.targets[0].transform_type) == (
            "lx", "TRANSFORMS", driven.light, "LOC_X")
        assert result["expression"] == "lx * 2"

    def test_single_prop_variable(self, handler, driven):
        _add(handler, data_path="data.energy", index=-1, expression="e * 10", variables=[
            {"name": "e", "type": "SINGLE_PROP", "object": "Light", "data_path": "location"}])
        target = driven.curves[0].driver.variables[0].targets[0]
        assert (target.id_type, target.id, target.data_path) == ("OBJECT", driven.light,
                                                                 "location")

    @pytest.mark.parametrize("expr", ["__import__('os')", "bpy.data", "lx ** 2", "nope"])
    def test_handler_refuses_unsafe_expressions_before_blender_sees_them(self, handler,
                                                                         driven, expr):
        with pytest.raises(ValueError):
            _add(handler, expression=expr)
        assert driven.curves == []

    def test_blender_must_agree_it_is_simple(self, handler, driven, monkeypatch):
        """If the handler's check ever passes something Blender would hand to
        Python, the driver is removed before anything evaluates it."""
        monkeypatch.setattr(handler, "_check_expression", lambda expr, names: None)
        with pytest.raises(ValueError, match="simple"):
            _add(handler, expression="lx.real")
        assert driven.curves == []

    def test_unknown_variable_object(self, handler, driven):
        with pytest.raises(ValueError, match="Ghost"):
            _add(handler, variables=[{"name": "lx", "type": "TRANSFORMS", "object": "Ghost",
                                      "transform_type": "LOC_X"}])
        assert driven.curves == []

    def test_bad_data_path_refused(self, handler, driven):
        with pytest.raises(ValueError):
            _add(handler, data_path="location()")

    def test_remove_and_list(self, handler, driven):
        _add(handler)
        listing = handler.handle_list_drivers({"object_name": "Cube"})
        assert listing["drivers"][0]["expression"] == "lx * 2"
        assert listing["drivers"][0]["variables"][0]["name"] == "lx"
        result = handler.handle_remove_driver({"object_name": "Cube", "data_path": "location",
                                               "index": 2})
        assert result["removed"] is True and driven.curves == []


class TestDriverOwnerAcrossDataBlocks:
    """Blender refuses driver_add on paths that cross into another data block
    ("path spans ID blocks"): a light's energy lives on the Light data, so the
    driver goes there with the rest of the path."""

    def test_data_path_hops_to_the_light_data(self, handler, monkeypatch):
        import bpy

        made = []

        def owner(name):
            o = SimpleNamespace(name=name)
            o.id_data = o  # a data block is its own id_data
            o.driver_add = lambda path, index=-1: made.append((name, path, index)) or \
                SimpleNamespace(data_path=path, array_index=0, driver=FakeDriver())
            o.driver_remove = lambda path, index=-1: True
            return o

        light_data = owner("LightData")
        light_obj = owner("Lamp")

        def resolve(path, coerce=True):
            return {"data": light_data, "data.energy": 1000.0}[path]

        light_obj.path_resolve = resolve
        light_data.path_resolve = lambda path, coerce=True: 1000.0
        bpy.data.objects.get = MagicMock(side_effect={"Lamp": light_obj}.get)

        result = handler.handle_add_driver({
            "object_name": "Lamp", "data_path": "data.energy", "index": -1,
            "driver_type": "SCRIPTED", "expression": "frame * 10", "variables": []})
        assert made == [("LightData", "energy", -1)]
        assert result["owner"] == "LightData"


class TestKeyframeProperty:
    def _scene(self, monkeypatch):
        import bpy

        keyed = []

        class Socket:
            def __init__(self):
                self.default_value = [0.8, 0.8, 0.8, 1.0]

        sockets = {"Base Color": Socket()}

        class Inputs:
            def __getitem__(self, k):
                return sockets[k]

        node = SimpleNamespace(inputs=Inputs())
        tree = SimpleNamespace(name="Shader Nodetree")
        tree.id_data = tree
        tree.nodes = {"Principled BSDF": node}

        def tree_resolve(path, coerce=True):
            table = {'nodes["Principled BSDF"].inputs["Base Color"]': sockets["Base Color"],
                     'nodes["Principled BSDF"].inputs["Base Color"].default_value':
                         sockets["Base Color"].default_value}
            if path not in table:
                raise ValueError(path)
            return table[path]

        tree.path_resolve = tree_resolve
        tree.keyframe_insert = lambda path, index=-1, frame=0: keyed.append(
            ("tree", path, index, frame)) or True
        material = SimpleNamespace(name="Paint", node_tree=tree)
        material.id_data = material
        material.path_resolve = lambda path, coerce=True: {"node_tree": tree}[path]

        def cube_resolve(path, coerce=True):
            table = {"active_material": material, "active_material.node_tree": tree,
                     'active_material.node_tree.nodes["Principled BSDF"].inputs["Base Color"]'
                     '.default_value': sockets["Base Color"].default_value}
            if path not in table:
                raise ValueError(path)
            return table[path]

        cube = SimpleNamespace(name="Cube", path_resolve=cube_resolve)
        cube.id_data = cube
        bpy.data.objects.get = MagicMock(side_effect={"Cube": cube}.get)
        world = SimpleNamespace(name="World", strength=1.0)
        world.id_data = world
        world.path_resolve = lambda path, coerce=True: getattr(world, path)
        world.keyframe_insert = lambda path, index=-1, frame=0: keyed.append(
            ("world", path, index, frame)) or True
        monkeypatch.setattr(bpy.context, "scene", SimpleNamespace(world=world))
        return SimpleNamespace(keyed=keyed, sockets=sockets, world=world)

    def test_material_colour_is_keyed_on_its_node_tree(self, handler, monkeypatch):
        env = self._scene(monkeypatch)
        result = handler.handle_keyframe_property({
            "target": "OBJECT", "object_name": "Cube", "frame": 24, "index": -1,
            "value": [1.0, 0.0, 0.0, 1.0],
            "data_path": 'active_material.node_tree.nodes["Principled BSDF"].inputs'
                         '["Base Color"].default_value'})
        assert env.sockets["Base Color"].default_value == [1.0, 0.0, 0.0, 1.0]
        assert env.keyed == [("tree", 'nodes["Principled BSDF"].inputs["Base Color"]'
                                      '.default_value', -1, 24)]
        assert result["owner"] == "Shader Nodetree"

    def test_world_target(self, handler, monkeypatch):
        env = self._scene(monkeypatch)
        handler.handle_keyframe_property({"target": "WORLD", "data_path": "strength",
                                          "frame": 1, "index": -1, "value": 0.2})
        assert env.world.strength == 0.2
        assert env.keyed == [("world", "strength", -1, 1)]

    def test_unknown_path_is_explained(self, handler, monkeypatch):
        self._scene(monkeypatch)
        with pytest.raises(ValueError, match="no property"):
            handler.handle_keyframe_property({"target": "OBJECT", "object_name": "Cube",
                                              "data_path": "colour", "frame": 1})

    def test_bad_target_and_path_refused(self, handler, monkeypatch):
        self._scene(monkeypatch)
        with pytest.raises(ValueError):
            handler.handle_keyframe_property({"target": "CAMERA", "data_path": "lens",
                                              "frame": 1})
        with pytest.raises(ValueError):
            handler.handle_keyframe_property({"target": "WORLD", "data_path": "__class__",
                                              "frame": 1})


def test_non_animatable_property_is_explained(handler, monkeypatch):
    import bpy

    def refuse(path, index=-1, frame=0):
        raise TypeError('bpy_struct.keyframe_insert() property "name" not animatable')

    cube = SimpleNamespace(name="Cube", keyframe_insert=refuse,
                           path_resolve=lambda path, coerce=True: "Cube")
    cube.id_data = cube
    bpy.data.objects.get = MagicMock(side_effect={"Cube": cube}.get)
    with pytest.raises(ValueError, match="cannot be animated"):
        handler.handle_keyframe_property({"target": "OBJECT", "object_name": "Cube",
                                          "data_path": "name", "frame": 1})
