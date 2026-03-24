"""Blender addon handlers for scene management commands."""

import bpy
from .. import dispatcher
from ..render_guard import render_guard

# Known Blender extensions and their addon keys (legacy and bl_ext namespace)
KNOWN_EXTENSIONS = {
    "bool_tool": {
        "legacy_key": "object_boolean_tools",
        "ext_key": "bl_ext.blender_org.object_boolean_tools",
        "name": "Bool Tool",
    },
    "looptools": {
        "legacy_key": "mesh_looptools",
        "ext_key": "bl_ext.blender_org.looptools",
        "name": "LoopTools",
    },
    "node_wrangler": {
        "legacy_key": "node_wrangler",
        "ext_key": "bl_ext.blender_org.node_wrangler",
        "name": "Node Wrangler",
    },
}

# Properties that can be set on bpy.context.scene
ALLOWED_PROPERTIES = {
    "frame_start",
    "frame_end",
    "frame_current",
    "frame_step",
    "fps",
    "unit_system",
    "render_engine",
    "use_gravity",
    "gravity",
}


def handle_get_scene_info(params: dict) -> dict:
    """Return full scene information including object tree, hierarchy, counts, frame range, fps, and render engine."""
    try:
        scene = bpy.context.scene

        # Build object list with hierarchy info
        objects = []
        type_counts: dict[str, int] = {}
        for obj in bpy.data.objects:
            obj_info = {
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
                "parent": obj.parent.name if obj.parent else None,
                "children": [child.name for child in obj.children],
                "visible": obj.visible_get(),
            }
            objects.append(obj_info)
            type_counts[obj.type] = type_counts.get(obj.type, 0) + 1

        return {
            "scene_name": scene.name,
            "objects": objects,
            "object_count": len(objects),
            "type_counts": type_counts,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "frame_current": scene.frame_current,
            "fps": scene.render.fps,
            "render_engine": scene.render.engine,
            "unit_system": scene.unit_settings.system,
            "use_gravity": scene.use_gravity,
            "gravity": list(scene.gravity),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to get scene info: {e}")


def handle_set_scene_property(params: dict) -> dict:
    """Set a property on the current scene."""
    prop = params.get("property")
    value = params.get("value")

    if prop not in ALLOWED_PROPERTIES:
        raise ValueError(f"Property '{prop}' is not allowed. Allowed: {sorted(ALLOWED_PROPERTIES)}")

    try:
        scene = bpy.context.scene

        if prop == "fps":
            scene.render.fps = int(value)
        elif prop == "unit_system":
            scene.unit_settings.system = value
        elif prop == "render_engine":
            scene.render.engine = value
        elif prop == "gravity":
            scene.gravity = tuple(value)
        elif prop == "use_gravity":
            scene.use_gravity = bool(value)
        else:
            setattr(scene, prop, int(value))

        return {"property": prop, "value": value, "success": True}
    except Exception as e:
        raise RuntimeError(f"Failed to set scene property '{prop}': {e}")


def handle_list_scenes(params: dict) -> list:
    """List all scenes in the current Blender file."""
    try:
        scenes = []
        for scene in bpy.data.scenes:
            scenes.append({
                "name": scene.name,
                "object_count": len(scene.objects),
                "is_active": scene == bpy.context.scene,
            })
        return scenes
    except Exception as e:
        raise RuntimeError(f"Failed to list scenes: {e}")


def handle_create_scene(params: dict) -> dict:
    """Create a new scene."""
    name = params.get("name", "Scene")

    try:
        new_scene = bpy.data.scenes.new(name=name)
        return {
            "name": new_scene.name,
            "success": True,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to create scene '{name}': {e}")


def handle_delete_scene(params: dict) -> dict:
    """Delete a scene by name."""
    name = params.get("name")

    try:
        if len(bpy.data.scenes) <= 1:
            raise ValueError("Cannot delete the last remaining scene")

        scene = bpy.data.scenes.get(name)
        if scene is None:
            raise ValueError(f"Scene '{name}' not found")

        bpy.data.scenes.remove(scene)
        return {"name": name, "deleted": True}
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to delete scene '{name}': {e}")


def handle_get_installed_extensions(params: dict) -> dict:
    """Return list of known extensions that are currently enabled.

    Checks both legacy addon keys and bl_ext.blender_org namespace keys
    to support Blender 4.2+ extension system.

    Returns:
        Dict with 'installed' list of extension IDs that are enabled.
    """
    installed = []
    prefs = bpy.context.preferences.addons
    for key, info in KNOWN_EXTENSIONS.items():
        if info["legacy_key"] in prefs or info["ext_key"] in prefs:
            installed.append(key)
    return {"installed": installed}


def handle_reset_render_guard(params: dict) -> dict:
    """Force-clear a stuck render guard.

    Args:
        params: Unused parameters dict.

    Returns:
        Dict with 'status' and 'was_rendering' keys.
    """
    was_rendering = render_guard.reset()
    return {"status": "reset", "was_rendering": was_rendering}


def register():
    """Register scene handlers with the dispatcher."""
    dispatcher.register_handler("get_scene_info", handle_get_scene_info)
    dispatcher.register_handler("set_scene_property", handle_set_scene_property)
    dispatcher.register_handler("list_scenes", handle_list_scenes)
    dispatcher.register_handler("create_scene", handle_create_scene)
    dispatcher.register_handler("delete_scene", handle_delete_scene)
    dispatcher.register_handler("get_installed_extensions", handle_get_installed_extensions)
    dispatcher.register_handler("reset_render_guard", handle_reset_render_guard)
