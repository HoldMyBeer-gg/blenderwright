"""Blender handlers for Annotation operations (Blender 5.x)."""

import bpy
from .. import dispatcher


def _get_annotation(name):
    """Get an annotation data block by name."""
    ann = bpy.data.annotations.get(name)
    if ann is None:
        raise ValueError(f"Annotation '{name}' not found")
    return ann


def handle_create_annotation(params):
    """Create a new annotation data block.

    Args:
        params: Dict with optional "name" key.

    Returns:
        Dict with the created annotation's name.
    """
    name = params.get("name", "Annotation")
    ann = bpy.data.annotations.new(name)
    return {"name": ann.name}


def handle_add_annotation_layer(params):
    """Add a layer to an annotation.

    Args:
        params: Dict with "annotation_name" and "layer_name" keys.

    Returns:
        Dict with annotation name and layer info.
    """
    ann = _get_annotation(params["annotation_name"])
    layer_name = params["layer_name"]
    layer = ann.layers.new(name=layer_name)
    return {"annotation": ann.name, "layer": layer.info}


def handle_remove_annotation_layer(params):
    """Remove a layer from an annotation.

    Args:
        params: Dict with "annotation_name" and "layer_name" keys.

    Returns:
        Dict with annotation name and removed layer name.
    """
    ann = _get_annotation(params["annotation_name"])
    layer_name = params["layer_name"]
    layer = ann.layers.get(layer_name)
    if layer is None:
        raise ValueError(f"Layer '{layer_name}' not found on '{ann.name}'")
    ann.layers.remove(layer)
    return {"annotation": ann.name, "removed_layer": layer_name}


def handle_add_annotation_stroke(params):
    """Add a stroke to an annotation layer.

    Args:
        params: Dict with "annotation_name", "layer_name", "points", and optional "pressure".

    Returns:
        Dict with annotation name, layer info, and point count.
    """
    ann = _get_annotation(params["annotation_name"])
    layer_name = params["layer_name"]
    points_data = params["points"]
    pressure = params.get("pressure", 1.0)

    layer = ann.layers.get(layer_name)
    if layer is None:
        raise ValueError(f"Layer '{layer_name}' not found on '{ann.name}'")

    if len(layer.frames) == 0:
        frame = layer.frames.new(bpy.context.scene.frame_current)
    else:
        frame = layer.frames[0]

    stroke = frame.strokes.new()
    stroke.points.add(len(points_data))

    for i, pt in enumerate(points_data):
        stroke.points[i].co = tuple(pt)
        stroke.points[i].pressure = pressure

    return {
        "annotation": ann.name,
        "layer": layer.info,
        "point_count": len(points_data),
    }


def handle_set_annotation_stroke_property(params):
    """Set a property on an annotation stroke.

    Args:
        params: Dict with "annotation_name", "layer_name", "stroke_index",
                "property", and "value".

    Returns:
        Dict confirming the property change.
    """
    ann = _get_annotation(params["annotation_name"])
    layer_name = params["layer_name"]
    stroke_index = params["stroke_index"]
    prop = params["property"]
    value = params["value"]

    layer = ann.layers.get(layer_name)
    if layer is None:
        raise ValueError(f"Layer '{layer_name}' not found on '{ann.name}'")

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
        "annotation": ann.name,
        "layer": layer.info,
        "stroke_index": stroke_index,
        "property": prop,
        "value": value,
    }


def register():
    """Register annotation handlers with the dispatcher."""
    dispatcher.register_handler("create_annotation", handle_create_annotation)
    dispatcher.register_handler("add_annotation_layer", handle_add_annotation_layer)
    dispatcher.register_handler("remove_annotation_layer", handle_remove_annotation_layer)
    dispatcher.register_handler("add_annotation_stroke", handle_add_annotation_stroke)
    dispatcher.register_handler(
        "set_annotation_stroke_property", handle_set_annotation_stroke_property
    )
