"""Blender handlers for Grease Pencil operations."""

import bpy
from .. import dispatcher


def _ensure_object_mode():
    """Ensure we are in object mode."""
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _get_gpencil_object(name):
    """Get a Grease Pencil object by name."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.type != "GPENCIL":
        raise ValueError(f"Object '{name}' is not a Grease Pencil object")
    return obj


def handle_create_gpencil_object(params):
    """Create a new Grease Pencil object."""
    _ensure_object_mode()
    name = params.get("name", "")
    location = tuple(params.get("location", (0, 0, 0)))

    bpy.ops.object.gpencil_add(type="EMPTY", location=location)
    obj = bpy.context.active_object

    if name:
        obj.name = name
        obj.data.name = name

    return {"name": obj.name, "location": list(obj.location)}


def handle_add_gpencil_layer(params):
    """Add a layer to a Grease Pencil object."""
    _ensure_object_mode()
    obj = _get_gpencil_object(params["object_name"])
    layer_name = params["layer_name"]

    layer = obj.data.layers.new(name=layer_name)

    return {"object": obj.name, "layer": layer.info}


def handle_remove_gpencil_layer(params):
    """Remove a layer from a Grease Pencil object."""
    _ensure_object_mode()
    obj = _get_gpencil_object(params["object_name"])
    layer_name = params["layer_name"]

    layer = obj.data.layers.get(layer_name)
    if layer is None:
        raise ValueError(
            f"Layer '{layer_name}' not found on '{obj.name}'"
        )

    obj.data.layers.remove(layer)

    return {"object": obj.name, "removed_layer": layer_name}


def handle_add_gpencil_stroke(params):
    """Add a stroke to a Grease Pencil layer."""
    _ensure_object_mode()
    obj = _get_gpencil_object(params["object_name"])
    layer_name = params["layer_name"]
    points_data = params["points"]
    pressure = params.get("pressure", 1.0)
    strength = params.get("strength", 1.0)

    layer = obj.data.layers.get(layer_name)
    if layer is None:
        raise ValueError(
            f"Layer '{layer_name}' not found on '{obj.name}'"
        )

    # Ensure at least one frame exists
    if len(layer.frames) == 0:
        frame = layer.frames.new(bpy.context.scene.frame_current)
    else:
        frame = layer.frames[0]

    stroke = frame.strokes.new()
    stroke.points.add(len(points_data))

    for i, pt in enumerate(points_data):
        stroke.points[i].co = tuple(pt)
        stroke.points[i].pressure = pressure
        stroke.points[i].strength = strength

    return {
        "object": obj.name,
        "layer": layer.info,
        "point_count": len(points_data),
    }


def handle_set_gpencil_stroke_property(params):
    """Set a property on a Grease Pencil stroke."""
    _ensure_object_mode()
    obj = _get_gpencil_object(params["object_name"])
    layer_name = params["layer_name"]
    stroke_index = params["stroke_index"]
    prop = params["property"]
    value = params["value"]

    layer = obj.data.layers.get(layer_name)
    if layer is None:
        raise ValueError(
            f"Layer '{layer_name}' not found on '{obj.name}'"
        )

    if len(layer.frames) == 0:
        raise ValueError(f"Layer '{layer_name}' has no frames")

    frame = layer.frames[0]
    if stroke_index >= len(frame.strokes):
        raise ValueError(
            f"Stroke index {stroke_index} out of range "
            f"(layer has {len(frame.strokes)} strokes)"
        )

    stroke = frame.strokes[stroke_index]

    if not hasattr(stroke, prop):
        raise ValueError(f"Stroke has no property '{prop}'")

    setattr(stroke, prop, value)

    return {
        "object": obj.name,
        "layer": layer.info,
        "stroke_index": stroke_index,
        "property": prop,
        "value": value,
    }


def register():
    """Register all Grease Pencil handlers with the dispatcher."""
    dispatcher.register_handler("create_gpencil_object", handle_create_gpencil_object)
    dispatcher.register_handler("add_gpencil_layer", handle_add_gpencil_layer)
    dispatcher.register_handler("remove_gpencil_layer", handle_remove_gpencil_layer)
    dispatcher.register_handler("add_gpencil_stroke", handle_add_gpencil_stroke)
    dispatcher.register_handler(
        "set_gpencil_stroke_property", handle_set_gpencil_stroke_property
    )
