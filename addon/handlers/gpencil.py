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


LINEART_SOURCES = {"SCENE", "COLLECTION", "OBJECT"}
DEFAULT_INK = "GP Ink"


def _gp_material(name, color):
    mat = bpy.data.materials.new(name)
    bpy.data.materials.create_gpencil_data(mat)
    mat.grease_pencil.color = color
    return mat


def handle_create_grease_pencil(params):
    """A Grease Pencil object with one layer and a drawing on frame 1."""
    name = params.get("name", "Drawing")
    data = bpy.data.grease_pencils.new(name)
    obj = bpy.data.objects.new(name, data)
    obj.location = params.get("location", [0, 0, 0])
    bpy.context.scene.collection.objects.link(obj)
    layer = data.layers.new(params.get("layer_name", "Lines"))
    layer.frames.new(1)
    return {"object": obj.name, "layer": layer.name, "frame": 1}


def handle_create_gp_material(params):
    mat = _gp_material(params["name"], params.get("color", [0, 0, 0, 1]))
    return {"material": mat.name, "color": list(mat.grease_pencil.color)}


def _get_gp_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.type != "GREASEPENCIL":
        raise ValueError(f"'{name}' is not a Grease Pencil object; make one with "
                         f"create_grease_pencil")
    return obj


def _material_index(data, name):
    if not name:
        if len(data.materials) == 0:
            # A stroke without a material does not render; give it black ink
            ink = bpy.data.materials.get(DEFAULT_INK)
            if ink is None or ink.grease_pencil is None:
                ink = _gp_material(DEFAULT_INK, [0.0, 0.0, 0.0, 1.0])
            data.materials.append(ink)
        return 0
    mat = bpy.data.materials.get(name)
    if mat is None:
        raise ValueError(f"Material '{name}' not found")
    if mat.grease_pencil is None:
        raise ValueError(f"'{name}' is not a Grease Pencil material; make one with "
                         f"create_gp_material")
    index = data.materials.find(name)
    if index < 0:
        data.materials.append(mat)
        index = len(data.materials) - 1
    return index


def handle_add_gp_stroke(params):
    """Draw one stroke on a layer's drawing at a frame."""
    obj = _get_gp_object(params["object_name"])
    data = obj.data
    layer_name = params.get("layer", "")
    if layer_name:
        layer = data.layers.get(layer_name) or data.layers.new(layer_name)
    else:
        layer = data.layers.active or (data.layers[0] if len(data.layers) else
                                       data.layers.new("Lines"))
    frame_number = int(params.get("frame", 1))
    frame = next((f for f in layer.frames if f.frame_number == frame_number), None)
    if frame is None:
        frame = layer.frames.new(frame_number)
    material_index = _material_index(data, params.get("material", ""))

    points = params["points"]
    radii = params.get("radius", [0.02] * len(points))
    drawing = frame.drawing
    drawing.add_strokes([len(points)])
    stroke = drawing.strokes[-1]
    for point, co, radius in zip(stroke.points, points, radii):
        point.position = tuple(co)
        point.radius = radius
    stroke.cyclic = bool(params.get("cyclic", False))
    stroke.material_index = material_index
    return {"object": obj.name, "layer": layer.name, "frame": frame_number,
            "points": len(points), "strokes_on_frame": len(drawing.strokes)}


def handle_add_lineart(params):
    """A Grease Pencil object with a Line Art modifier tracing scene geometry."""
    source = params.get("source", "SCENE")
    if source not in LINEART_SOURCES:
        raise ValueError(f"Unknown Line Art source {source!r}")
    source_obj = source_col = None
    if source == "OBJECT":
        source_obj = bpy.data.objects.get(params.get("source_name", ""))
        if source_obj is None:
            raise ValueError(f"Object '{params.get('source_name')}' not found")
    elif source == "COLLECTION":
        source_col = bpy.data.collections.get(params.get("source_name", ""))
        if source_col is None:
            raise ValueError(f"Collection '{params.get('source_name')}' not found")
    if bpy.context.scene.camera is None:
        raise ValueError("Line Art traces what the active camera sees; add a camera first")

    name = params.get("name", "LineArt")
    data = bpy.data.grease_pencils.new(name)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    layer = data.layers.new("Lines")
    layer.use_lights = False  # ink lines keep their colour instead of being shaded
    layer.frames.new(bpy.context.scene.frame_current)
    mat = _gp_material(f"{name} Ink", params.get("color", [0, 0, 0, 1]))
    data.materials.append(mat)

    mod = obj.modifiers.new(name="Line Art", type="LINEART")
    mod.source_type = source
    if source_obj is not None:
        mod.source_object = source_obj
    if source_col is not None:
        mod.source_collection = source_col
    mod.target_layer = layer.name
    mod.target_material = mat
    mod.radius = params.get("thickness", 0.01)
    mod.crease_threshold = params.get("crease_angle", 2.443)
    mod.use_intersection = bool(params.get("use_intersection", True))
    return {"object": obj.name, "source": source,
            "source_name": params.get("source_name") or None}


def register():
    """Register annotation handlers with the dispatcher."""
    dispatcher.register_handler("create_annotation", handle_create_annotation)
    dispatcher.register_handler("add_annotation_layer", handle_add_annotation_layer)
    dispatcher.register_handler("remove_annotation_layer", handle_remove_annotation_layer)
    dispatcher.register_handler("add_annotation_stroke", handle_add_annotation_stroke)
    dispatcher.register_handler(
        "set_annotation_stroke_property", handle_set_annotation_stroke_property
    )
    dispatcher.register_handler("create_grease_pencil", handle_create_grease_pencil)
    dispatcher.register_handler("create_gp_material", handle_create_gp_material)
    dispatcher.register_handler("add_gp_stroke", handle_add_gp_stroke)
    dispatcher.register_handler("add_lineart", handle_add_lineart)
