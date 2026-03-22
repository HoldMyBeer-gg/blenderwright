"""Blender command handlers - registers all handlers with the dispatcher."""

from . import (
    scene,
    objects,
    transforms,
    modeling,
    materials,
    lighting,
    camera,
    animation,
    rendering,
    curves,
    sculpting,
    uv,
    physics,
    geometry_nodes,
    armature,
    collections,
    file_ops,
    viewport,
    code_exec,
)

_modules = [
    scene,
    objects,
    transforms,
    modeling,
    materials,
    lighting,
    camera,
    animation,
    rendering,
    curves,
    sculpting,
    uv,
    physics,
    geometry_nodes,
    armature,
    collections,
    file_ops,
    viewport,
    code_exec,
]


def register():
    for mod in _modules:
        if hasattr(mod, "register"):
            mod.register()


def unregister():
    for mod in reversed(_modules):
        if hasattr(mod, "unregister"):
            mod.unregister()
