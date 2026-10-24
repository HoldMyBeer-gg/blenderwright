"""Tests for physics handler: bake through temp_override, not a context dict."""

import importlib.util
import os
import sys
from unittest.mock import MagicMock

import pytest


def _load_handler():
    """Load addon.handlers.physics without addon/handlers/__init__.py."""
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "physics.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.physics", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.physics"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def handler():
    import bpy

    bpy.ops.ptcache.bake.reset_mock()
    bpy.context.temp_override.reset_mock()
    return _load_handler()


def _object(modifiers=(), particle_systems=(), rigid_body=None):
    import bpy

    obj = MagicMock()
    obj.modifiers = list(modifiers)
    obj.particle_systems = list(particle_systems)
    obj.rigid_body = rigid_body
    bpy.data.objects.get = MagicMock(return_value=obj)
    return obj


def _assert_baked_with_override(point_cache):
    import bpy

    bpy.context.temp_override.assert_any_call(point_cache=point_cache)
    for call in bpy.ops.ptcache.bake.call_args_list:
        assert call.args == ()
        assert call.kwargs == {"bake": True}
    assert bpy.ops.ptcache.bake.called


class TestBakePhysics:
    def test_rigid_body_bakes_the_world_cache(self, handler):
        import bpy

        _object(rigid_body=MagicMock())
        cache = bpy.context.scene.rigidbody_world.point_cache

        result = handler.handle_bake_physics({"object_name": "Cube", "physics_type": "RIGID_BODY"})

        _assert_baked_with_override(cache)
        assert "RIGID_BODY" in str(result)

    def test_cloth_bakes_the_modifier_cache(self, handler):
        cloth = MagicMock()
        cloth.type = "CLOTH"
        _object(modifiers=[cloth])

        handler.handle_bake_physics({"object_name": "Cube", "physics_type": "CLOTH"})

        _assert_baked_with_override(cloth.point_cache)

    def test_particles_bake_the_system_cache(self, handler):
        ps = MagicMock()
        _object(particle_systems=[ps])

        handler.handle_bake_physics({"object_name": "Cube", "physics_type": "PARTICLE_SYSTEM"})

        _assert_baked_with_override(ps.point_cache)


class TestForceFieldCollisionSoftBody:
    def test_force_field_comes_from_effector_add(self, handler, monkeypatch):
        """An empty made with bpy.data.objects.new has no field data (obj.field is
        None); only the effector_add operator allocates it."""
        import bpy
        from types import SimpleNamespace

        made = []

        def effector_add(type, location, rotation):
            obj = SimpleNamespace(name=type.title(), location=location,
                                  rotation_euler=rotation,
                                  field=SimpleNamespace(type=type))
            made.append(obj)
            bpy.context.active_object = obj
            return {"FINISHED"}

        monkeypatch.setattr(bpy.ops.object, "effector_add", effector_add, raising=False)
        monkeypatch.setattr(handler, "_ensure_object_mode", lambda: None, raising=False)
        result = handler.handle_add_force_field({
            "type": "WIND", "name": "Gust", "location": [0, 0, 1], "rotation": [1.57, 0, 0],
            "strength": 5.0, "flow": 1.0, "noise": 0.5, "seed": 3, "falloff_type": "TUBE",
            "falloff_power": 2.0, "max_distance": 4.0})
        obj = made[0]
        f = obj.field
        assert obj.name == "Gust"
        assert (f.type, f.strength, f.flow, f.noise, f.seed, f.falloff_type,
                f.falloff_power, f.use_max_distance, f.distance_max) == (
            "WIND", 5.0, 1.0, 0.5, 3, "TUBE", 2.0, True, 4.0)
        assert result["name"] == "Gust"

    def test_unknown_field_type_refused(self, handler):
        with pytest.raises(ValueError):
            handler.handle_add_force_field({"type": "BOID"})

    def test_collision(self, handler):
        from types import SimpleNamespace

        coll = SimpleNamespace()
        mods = []
        obj = _object()
        obj.type = "MESH"
        obj.modifiers = SimpleNamespace(new=lambda name, type: mods.append(type),
                                        __iter__=None)
        obj.collision = coll
        handler.handle_add_collision({"object_name": "Cube", "thickness": 0.05,
                                      "damping": 0.2, "friction": 10.0, "stickiness": 0.0,
                                      "permeability": 0.1})
        assert mods == ["COLLISION"]
        assert (coll.thickness_outer, coll.damping, coll.cloth_friction,
                coll.permeability) == (0.05, 0.2, 10.0, 0.1)

    def test_soft_body(self, handler):
        from types import SimpleNamespace

        sb = SimpleNamespace()
        mods = []
        obj = _object()
        obj.type = "MESH"
        obj.modifiers = SimpleNamespace(new=lambda name, type: mods.append(type))
        obj.soft_body = sb
        handler.handle_add_soft_body({"object_name": "Cube", "mass": 2.0, "goal": False,
                                      "goal_strength": 0.7, "pull": 0.9, "push": 0.8,
                                      "bend": 0.5, "damping": 1.0, "friction": 0.5,
                                      "self_collision": True})
        assert mods == ["SOFT_BODY"]
        assert (sb.mass, sb.use_goal, sb.pull, sb.push, sb.bend, sb.use_self_collision) == (
            2.0, False, 0.9, 0.8, 0.5, True)

    def test_soft_body_bakes(self, handler):
        import bpy

        soft = MagicMock()
        soft.type = "SOFT_BODY"
        _object(modifiers=[soft])
        handler.handle_bake_physics({"object_name": "Cube", "physics_type": "SOFT_BODY"})
        bpy.context.temp_override.assert_any_call(point_cache=soft.point_cache)
