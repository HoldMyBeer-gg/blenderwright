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


class _Prop:
    def __init__(self, type, readonly=False):
        self.type, self.is_readonly = type, readonly


class FakeRBC:
    bl_rna = type("R", (), {"properties": {
        "type": _Prop("ENUM"), "object1": _Prop("POINTER"), "object2": _Prop("POINTER"),
        "use_breaking": _Prop("BOOLEAN"), "breaking_threshold": _Prop("FLOAT"),
        "disable_collisions": _Prop("BOOLEAN"), "use_limit_ang_z": _Prop("BOOLEAN"),
        "limit_ang_z_upper": _Prop("FLOAT"), "rna_type": _Prop("POINTER", readonly=True),
    }})()

    def __init__(self, type):
        self.type, self.object1, self.object2 = type, None, None
        self.use_breaking, self.breaking_threshold, self.disable_collisions = False, 10.0, True


@pytest.fixture
def rbc(handler, monkeypatch):
    import bpy
    from types import SimpleNamespace

    a = SimpleNamespace(name="Door", rigid_body=object(), location=(0.0, 0.0, 0.0))
    b = SimpleNamespace(name="Frame", rigid_body=object(), location=(2.0, 0.0, 4.0))
    loose = SimpleNamespace(name="Loose", rigid_body=None, location=(0.0, 0.0, 0.0))
    objects = {o.name: o for o in (a, b, loose)}
    made = []

    class Objects(dict):
        def new(self, name, data):
            empty = SimpleNamespace(name=name, location=None, rotation_euler=None,
                                    empty_display_type="PLAIN_AXES", rigid_body_constraint=None)
            made.append(empty)
            return empty

    monkeypatch.setattr(bpy.data, "objects", Objects(objects))
    scene = SimpleNamespace(rigidbody_world=object(),
                            collection=SimpleNamespace(objects=SimpleNamespace(link=MagicMock())))
    monkeypatch.setattr(bpy.context, "scene", scene, raising=False)

    def constraint_add(type):
        bpy.context.view_layer.objects.active.rigid_body_constraint = FakeRBC(type)

    monkeypatch.setattr(bpy.ops.rigidbody, "constraint_add", constraint_add)
    monkeypatch.setattr(handler, "_select_only", lambda obj: setattr(
        bpy.context.view_layer.objects, "active", obj))
    return handler, made


def _add(handler, **extra):
    params = {"object1": "Door", "object2": "Frame", "type": "HINGE", "name": "Hinge",
              "disable_collisions": True, "settings": {}} | extra
    return handler.handle_add_rigid_body_constraint(params)


class TestAddRigidBodyConstraintHandler:
    def test_joins_the_two_objects_at_their_midpoint(self, rbc):
        handler, made = rbc
        result = _add(handler)
        c = made[0].rigid_body_constraint
        assert c.type == "HINGE" and c.object1.name == "Door" and c.object2.name == "Frame"
        assert tuple(made[0].location) == (1.0, 0.0, 2.0)
        assert result["empty"] == "Hinge"

    def test_breaking_threshold_turns_breaking_on(self, rbc):
        handler, made = rbc
        _add(handler, breaking_threshold=25.0)
        c = made[0].rigid_body_constraint
        assert c.use_breaking is True and c.breaking_threshold == 25.0

    def test_settings_from_rna(self, rbc):
        handler, made = rbc
        _add(handler, settings={"use_limit_ang_z": True, "limit_ang_z_upper": 1.0})
        assert made[0].rigid_body_constraint.limit_ang_z_upper == 1.0

    @pytest.mark.parametrize("bad", ["object1", "rna_type", "bl_rna", "nope"])
    def test_unsafe_or_unknown_settings_refused(self, rbc, bad):
        handler, _ = rbc
        with pytest.raises(ValueError, match="setting"):
            _add(handler, settings={bad: 1})

    def test_both_need_rigid_bodies(self, rbc):
        handler, _ = rbc
        with pytest.raises(ValueError, match="add_rigid_body"):
            _add(handler, object2="Loose")

    def test_missing_object(self, rbc):
        handler, _ = rbc
        with pytest.raises(ValueError, match="Ghost"):
            _add(handler, object2="Ghost")


class TestSetRigidBodyWorldHandler:
    def test_creates_world_when_missing(self, handler, monkeypatch):
        import bpy
        from types import SimpleNamespace

        world = SimpleNamespace(enabled=True, time_scale=1.0, substeps_per_frame=10,
                                solver_iterations=10, use_split_impulse=False)
        scene = SimpleNamespace(rigidbody_world=None)
        monkeypatch.setattr(bpy.context, "scene", scene, raising=False)
        monkeypatch.setattr(bpy.ops.rigidbody, "world_add",
                            lambda: setattr(scene, "rigidbody_world", world))
        result = handler.handle_set_rigid_body_world({"substeps_per_frame": 30})
        assert world.substeps_per_frame == 30
        assert result == {"enabled": True, "time_scale": 1.0, "substeps_per_frame": 30,
                          "solver_iterations": 10, "use_split_impulse": False}
