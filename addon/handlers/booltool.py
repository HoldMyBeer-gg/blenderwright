"""Blender handlers for boolean operations with Bool Tool fallback.

Tries the Bool Tool extension operators first (boolean_auto_*).
If Bool Tool is not installed, falls back to native boolean modifier
workflow and includes a warning in the response.
"""

import bpy
from .. import dispatcher


# Possible Bool Tool addon/extension names across Blender versions
_BOOLTOOL_NAMES = [
    "bl_ext.blender_org.bool_tool",  # Blender 5.x extension
    "bool_tool",                      # Extension short name
    "object_boolean_tools",           # Legacy bundled addon (Blender <=4.1)
]


def _is_booltool_available():
    """Check if any variant of Bool Tool is loaded."""
    addons = bpy.context.preferences.addons
    for name in _BOOLTOOL_NAMES:
        if name in addons:
            return True
    # Also check if the operators exist directly
    return hasattr(bpy.ops.object, "boolean_auto_union")


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


def _setup_selection(object_name, target_name):
    """Set up selection: both selected, object active."""
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


def _native_boolean(obj, target, operation):
    """Fallback: apply boolean via native modifier, then delete target."""
    mod = obj.modifiers.new(name="Boolean", type="BOOLEAN")
    mod.operation = operation
    mod.object = target

    bpy.ops.object.modifier_apply(modifier=mod.name)

    # Clean up target object (Bool Tool does this automatically)
    bpy.data.objects.remove(target, do_unlink=True)


def _do_boolean(params, operation, booltool_op_name):
    """Perform a boolean op via Bool Tool if available, else native fallback."""
    obj, target = _setup_selection(params["object_name"], params["target_name"])

    warning = None

    if _is_booltool_available():
        # Try the new extension operator names first (boolean_auto_*)
        # then the legacy names (booltool_auto_*)
        op = getattr(bpy.ops.object, booltool_op_name, None)
        legacy_name = booltool_op_name.replace("boolean_auto_", "booltool_auto_")
        legacy_op = getattr(bpy.ops.object, legacy_name, None)

        try:
            if op is not None:
                op()
            elif legacy_op is not None:
                legacy_op()
            else:
                raise RuntimeError("operator not found")
        except Exception as e:
            # Bool Tool operator failed (e.g. no viewport context) — fall back
            _native_boolean(obj, target, operation)
            warning = (
                f"Bool Tool operator '{booltool_op_name}' failed: {e}. "
                f"Fell back to native boolean modifier ({operation})."
            )
    else:
        _native_boolean(obj, target, operation)
        warning = (
            f"Bool Tool addon is not installed. "
            f"Fell back to native boolean modifier ({operation}). "
            f"Install Bool Tool from Blender Extensions for better results."
        )

    result = {
        "object": obj.name,
        "operation": operation,
    }
    if warning:
        result["warning"] = warning

    return result


def handle_booltool_auto_union(params):
    """Perform boolean union via Bool Tool or native fallback."""
    return _do_boolean(params, "UNION", "boolean_auto_union")


def handle_booltool_auto_difference(params):
    """Perform boolean difference via Bool Tool or native fallback."""
    return _do_boolean(params, "DIFFERENCE", "boolean_auto_difference")


def handle_booltool_auto_intersect(params):
    """Perform boolean intersect via Bool Tool or native fallback."""
    return _do_boolean(params, "INTERSECT", "boolean_auto_intersect")


def handle_booltool_auto_slice(params):
    """Perform boolean slice via Bool Tool or native fallback."""
    return _do_boolean(params, "SLICE", "boolean_auto_slice")


def register():
    """Register all Bool Tool handlers with the dispatcher."""
    dispatcher.register_handler("booltool_auto_union", handle_booltool_auto_union)
    dispatcher.register_handler("booltool_auto_difference", handle_booltool_auto_difference)
    dispatcher.register_handler("booltool_auto_intersect", handle_booltool_auto_intersect)
    dispatcher.register_handler("booltool_auto_slice", handle_booltool_auto_slice)
