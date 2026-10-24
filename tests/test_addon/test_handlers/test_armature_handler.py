"""Armature handlers must reject a missing name, not pass None to Blender.

The TCP socket accepts raw JSON from any local process, so a handler can be
reached without the MCP tool's validation. bpy_prop_collection.get(None)
raises an opaque SystemError in Blender 5.2.
"""

import importlib.util
import os
import sys
from unittest.mock import MagicMock

import pytest


def _load_handler():
    """Load addon.handlers.armature without addon/handlers/__init__.py."""
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "armature.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.armature", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.armature"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def handler():
    return _load_handler()


CASES = [
    ("handle_add_bone", {"armature_name": "Rig", "bone_name": "Bone"}),
    ("handle_set_bone_property", {"armature_name": "Rig", "bone_name": "Bone",
                                  "property": "roll", "value": 0.0}),
    ("handle_add_constraint", {"object_name": "Rig", "constraint_type": "COPY_LOCATION"}),
    ("handle_parent_mesh_to_armature", {"mesh_name": "Body", "armature_name": "Rig"}),
    ("handle_set_pose", {"armature_name": "Rig", "bone_name": "Bone"}),
]

MISSING = [
    (name, key, {k: v for k, v in params.items() if k != key})
    for name, params in CASES
    for key in params
    if key.endswith("_name")
]


@pytest.mark.parametrize("handler_name, key, params", MISSING,
                         ids=[f"{n}-{k}" for n, k, _ in MISSING])
def test_missing_name_is_rejected_before_blender(handler, handler_name, key, params):
    import bpy

    bpy.data.objects.get = MagicMock()
    with pytest.raises(KeyError, match=key):
        getattr(handler, handler_name)(params)
    for call in bpy.data.objects.get.call_args_list:
        assert call.args and call.args[0] is not None


def test_dead_helpers_are_gone(handler):
    assert not hasattr(handler, "_ensure_mode")
