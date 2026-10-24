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
