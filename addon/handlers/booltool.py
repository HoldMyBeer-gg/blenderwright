"""Blender handlers for Bool Tool addon operations."""

import bpy
from .. import dispatcher


def _ensure_addon_enabled():
    """Enable the Bool Tool addon if not already loaded."""
    addon_name = "object_boolean_tools"
    if addon_name not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=addon_name)


def _ensure_object_mode():
    """Ensure we are in object mode."""
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _get_object(name):
    """Get a Blender object by name, raising if not found."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    return obj


def _setup_booltool_selection(object_name, target_name):
    """Set up selection for Bool Tool: target selected, object active.

    Bool Tool expects the active object to be the main object and
    the other selected object(s) to be the target/cutter.
    """
    _ensure_addon_enabled()
    _ensure_object_mode()

    obj = _get_object(object_name)
    target = _get_object(target_name)

    if obj.type != "MESH":
        raise ValueError(f"Object '{obj.name}' is not a mesh")
    if target.type != "MESH":
        raise ValueError(f"Object '{target.name}' is not a mesh")

    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    return obj, target


def handle_booltool_auto_union(params):
    """Perform Bool Tool auto union."""
    obj, target = _setup_booltool_selection(
        params["object_name"], params["target_name"]
    )
    bpy.ops.object.booltool_auto_union()
    return {
        "object": obj.name,
        "operation": "AUTO_UNION",
    }


def handle_booltool_auto_difference(params):
    """Perform Bool Tool auto difference."""
    obj, target = _setup_booltool_selection(
        params["object_name"], params["target_name"]
    )
    bpy.ops.object.booltool_auto_difference()
    return {
        "object": obj.name,
        "operation": "AUTO_DIFFERENCE",
    }


def handle_booltool_auto_intersect(params):
    """Perform Bool Tool auto intersect."""
    obj, target = _setup_booltool_selection(
        params["object_name"], params["target_name"]
    )
    bpy.ops.object.booltool_auto_intersect()
    return {
        "object": obj.name,
        "operation": "AUTO_INTERSECT",
    }


def handle_booltool_auto_slice(params):
    """Perform Bool Tool auto slice."""
    obj, target = _setup_booltool_selection(
        params["object_name"], params["target_name"]
    )
    bpy.ops.object.booltool_auto_slice()
    return {
        "object": obj.name,
        "operation": "AUTO_SLICE",
    }


def register():
    """Register all Bool Tool handlers with the dispatcher."""
    dispatcher.register_handler("booltool_auto_union", handle_booltool_auto_union)
    dispatcher.register_handler("booltool_auto_difference", handle_booltool_auto_difference)
    dispatcher.register_handler("booltool_auto_intersect", handle_booltool_auto_intersect)
    dispatcher.register_handler("booltool_auto_slice", handle_booltool_auto_slice)
