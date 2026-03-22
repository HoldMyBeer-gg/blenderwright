"""Blender handlers for mesh modeling operations."""

import bpy
from .. import dispatcher


def _ensure_object_mode():
    """Ensure we are in object mode."""
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _select_only(obj):
    """Deselect all and select only the given object, making it active."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _get_object(name):
    """Get a Blender object by name, raising if not found."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    return obj


def handle_add_modifier(params):
    """Add a modifier to an object."""
    _ensure_object_mode()
    obj = _get_object(params["object_name"])
    _select_only(obj)

    modifier_type = params["modifier_type"]
    name = params.get("name", "")

    mod = obj.modifiers.new(name=name or modifier_type, type=modifier_type)
    return {
        "object": obj.name,
        "modifier": mod.name,
        "type": mod.type,
    }


def handle_remove_modifier(params):
    """Remove a modifier from an object."""
    _ensure_object_mode()
    obj = _get_object(params["object_name"])
    modifier_name = params["modifier_name"]

    mod = obj.modifiers.get(modifier_name)
    if mod is None:
        raise ValueError(f"Modifier '{modifier_name}' not found on '{obj.name}'")

    obj.modifiers.remove(mod)
    return {"object": obj.name, "removed_modifier": modifier_name}


def handle_apply_modifier(params):
    """Apply a modifier to an object."""
    _ensure_object_mode()
    obj = _get_object(params["object_name"])
    _select_only(obj)
    modifier_name = params["modifier_name"]

    mod = obj.modifiers.get(modifier_name)
    if mod is None:
        raise ValueError(f"Modifier '{modifier_name}' not found on '{obj.name}'")

    bpy.ops.object.modifier_apply(modifier=modifier_name)
    return {"object": obj.name, "applied_modifier": modifier_name}


def handle_set_modifier_property(params):
    """Set a property on a modifier."""
    obj = _get_object(params["object_name"])
    modifier_name = params["modifier_name"]
    prop = params["property"]
    value = params["value"]

    mod = obj.modifiers.get(modifier_name)
    if mod is None:
        raise ValueError(f"Modifier '{modifier_name}' not found on '{obj.name}'")

    if not hasattr(mod, prop):
        raise ValueError(
            f"Modifier '{modifier_name}' has no property '{prop}'"
        )

    setattr(mod, prop, value)
    return {
        "object": obj.name,
        "modifier": modifier_name,
        "property": prop,
        "value": value,
    }


def handle_boolean_operation(params):
    """Perform a boolean operation between two objects."""
    _ensure_object_mode()
    obj = _get_object(params["object_name"])
    target = _get_object(params["target_name"])
    operation = params.get("operation", "DIFFERENCE")

    _select_only(obj)

    mod = obj.modifiers.new(name="Boolean", type="BOOLEAN")
    mod.operation = operation
    mod.object = target

    bpy.ops.object.modifier_apply(modifier=mod.name)

    return {
        "object": obj.name,
        "target": target.name,
        "operation": operation,
    }


def handle_subdivide_mesh(params):
    """Subdivide a mesh."""
    _ensure_object_mode()
    obj = _get_object(params["object_name"])

    if obj.type != "MESH":
        raise ValueError(f"Object '{obj.name}' is not a mesh")

    _select_only(obj)
    cuts = params.get("cuts", 1)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.subdivide(number_cuts=cuts)
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name, "cuts": cuts}


def handle_extrude_faces(params):
    """Extrude all faces of a mesh along their normals."""
    _ensure_object_mode()
    obj = _get_object(params["object_name"])

    if obj.type != "MESH":
        raise ValueError(f"Object '{obj.name}' is not a mesh")

    _select_only(obj)
    offset = params.get("offset", 1.0)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.mesh.extrude_region_move(
        TRANSFORM_OT_translate={"value": (0, 0, 0)}
    )
    bpy.ops.transform.shrink_fatten(value=-offset)
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name, "offset": offset}


def handle_bevel_edges(params):
    """Bevel all edges of a mesh."""
    _ensure_object_mode()
    obj = _get_object(params["object_name"])

    if obj.type != "MESH":
        raise ValueError(f"Object '{obj.name}' is not a mesh")

    _select_only(obj)
    width = params.get("width", 0.1)
    segments = params.get("segments", 1)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.select_mode(type="EDGE")
    bpy.ops.mesh.bevel(offset=width, segments=segments)
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name, "width": width, "segments": segments}


def handle_loop_cut(params):
    """Add loop cuts to a mesh object."""
    _ensure_object_mode()
    obj = _get_object(params["object_name"])

    if obj.type != "MESH":
        raise ValueError(f"Object '{obj.name}' is not a mesh")

    _select_only(obj)
    cuts = params.get("cuts", 1)

    # Use the subdivide modifier approach for reliability in headless mode
    mod = obj.modifiers.new(name="LoopCut_Temp", type="SUBSURF")
    mod.levels = 0
    mod.render_levels = 0

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.loopcut_slide(
        MESH_OT_loopcut={
            "number_cuts": cuts,
            "smoothness": 0,
            "falloff": "INVERSE_SQUARE",
        }
    )
    bpy.ops.object.mode_set(mode="OBJECT")

    # Clean up temp modifier
    temp_mod = obj.modifiers.get("LoopCut_Temp")
    if temp_mod:
        obj.modifiers.remove(temp_mod)

    return {"object": obj.name, "cuts": cuts}


def handle_set_smooth_shading(params):
    """Set smooth or flat shading on an object."""
    _ensure_object_mode()
    obj = _get_object(params["object_name"])

    if obj.type != "MESH":
        raise ValueError(f"Object '{obj.name}' is not a mesh")

    _select_only(obj)
    smooth = params.get("smooth", True)

    if smooth:
        bpy.ops.object.shade_smooth()
    else:
        bpy.ops.object.shade_flat()

    return {"object": obj.name, "smooth": smooth}


def handle_merge_vertices(params):
    """Merge vertices by distance."""
    _ensure_object_mode()
    obj = _get_object(params["object_name"])

    if obj.type != "MESH":
        raise ValueError(f"Object '{obj.name}' is not a mesh")

    _select_only(obj)
    threshold = params.get("threshold", 0.0001)

    vert_count_before = len(obj.data.vertices)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=threshold)
    bpy.ops.object.mode_set(mode="OBJECT")

    vert_count_after = len(obj.data.vertices)
    removed = vert_count_before - vert_count_after

    return {
        "object": obj.name,
        "threshold": threshold,
        "vertices_removed": removed,
    }


def handle_separate_mesh(params):
    """Separate a mesh into parts."""
    _ensure_object_mode()
    obj = _get_object(params["object_name"])

    if obj.type != "MESH":
        raise ValueError(f"Object '{obj.name}' is not a mesh")

    _select_only(obj)
    separate_type = params.get("type", "SELECTED")

    bpy.ops.object.mode_set(mode="EDIT")
    if separate_type != "SELECTED":
        bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type=separate_type)
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name, "type": separate_type}


def register():
    """Register all modeling handlers with the dispatcher."""
    dispatcher.register_handler("add_modifier", handle_add_modifier)
    dispatcher.register_handler("remove_modifier", handle_remove_modifier)
    dispatcher.register_handler("apply_modifier", handle_apply_modifier)
    dispatcher.register_handler("set_modifier_property", handle_set_modifier_property)
    dispatcher.register_handler("boolean_operation", handle_boolean_operation)
    dispatcher.register_handler("subdivide_mesh", handle_subdivide_mesh)
    dispatcher.register_handler("extrude_faces", handle_extrude_faces)
    dispatcher.register_handler("bevel_edges", handle_bevel_edges)
    dispatcher.register_handler("loop_cut", handle_loop_cut)
    dispatcher.register_handler("set_smooth_shading", handle_set_smooth_shading)
    dispatcher.register_handler("merge_vertices", handle_merge_vertices)
    dispatcher.register_handler("separate_mesh", handle_separate_mesh)
