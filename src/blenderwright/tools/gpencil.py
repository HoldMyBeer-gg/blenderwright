"""MCP tools for Blender Annotation operations (Blender 5.x)."""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    coerce_scalar,
    validate_color,
    validate_int,
    validate_object_name,
    validate_new_name,
    validate_enum,
    validate_numeric_range,
    validate_vector,
    ValidationError,
)

MAX_GP_POINTS = 10000

ALLOWED_GP_STROKE_PROPERTIES = {"line_width", "material_index", "display_mode"}


@mcp.tool()
def create_annotation(
    name: str = "",
) -> dict[str, Any]:
    """Create a new annotation data block.

    Annotations are viewport overlays used for drawing marks, notes, and guides.
    Unlike Grease Pencil objects, annotations are not positioned in 3D space.

    Args:
        name: Optional name for the annotation. Auto-generated if empty.

    Returns:
        Dict with the created annotation's name.
    """
    if name:
        name = validate_new_name(name)

    conn = get_connection()
    response = conn.send_command("create_annotation", {
        "name": name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_annotation_layer(annotation_name: str, layer_name: str) -> dict[str, Any]:
    """Add a layer to an annotation.

    Layers organize annotation strokes. Each layer can have its own blend mode,
    opacity, and color.

    Args:
        annotation_name: Name of the annotation data block.
        layer_name: Name for the new layer.

    Returns:
        Confirmation dict with annotation and layer names.
    """
    annotation_name = validate_object_name(annotation_name)
    layer_name = validate_object_name(layer_name)

    conn = get_connection()
    response = conn.send_command("add_annotation_layer", {
        "annotation_name": annotation_name,
        "layer_name": layer_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def remove_annotation_layer(annotation_name: str, layer_name: str) -> dict[str, Any]:
    """Remove a layer from an annotation.

    Args:
        annotation_name: Name of the annotation data block.
        layer_name: Name of the layer to remove.

    Returns:
        Confirmation dict.
    """
    annotation_name = validate_object_name(annotation_name)
    layer_name = validate_object_name(layer_name)

    conn = get_connection()
    response = conn.send_command("remove_annotation_layer", {
        "annotation_name": annotation_name,
        "layer_name": layer_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_annotation_stroke(
    annotation_name: str,
    layer_name: str,
    points: list[list[float]],
    pressure: float = 1.0,
) -> dict[str, Any]:
    """Add a stroke to an annotation layer.

    Creates a new stroke with the given points on the specified layer.
    Note: AnnotationStroke does not support per-point strength/opacity.

    Args:
        annotation_name: Name of the annotation data block.
        layer_name: Name of the layer to add the stroke to.
        points: List of XYZ coordinates, e.g. [[0,0,0], [1,1,0], [2,0,0]].
            Maximum 10000 points.
        pressure: Pen pressure for all points. Range: 0.0-1.0.

    Returns:
        Confirmation dict with point count.
    """
    annotation_name = validate_object_name(annotation_name)
    layer_name = validate_object_name(layer_name)

    if not points or not isinstance(points, list):
        raise ValidationError("points must be a non-empty list of [x, y, z] coordinates")
    if len(points) > MAX_GP_POINTS:
        raise ValidationError(f"points list exceeds maximum of {MAX_GP_POINTS}")

    validated_points = []
    for i, pt in enumerate(points):
        validated_points.append(list(validate_vector(pt, size=3, name=f"points[{i}]")))

    pressure = validate_numeric_range(pressure, min_val=0.0, max_val=1.0, name="pressure")

    conn = get_connection()
    response = conn.send_command("add_annotation_stroke", {
        "annotation_name": annotation_name,
        "layer_name": layer_name,
        "points": validated_points,
        "pressure": pressure,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_annotation_stroke_property(
    annotation_name: str,
    layer_name: str,
    stroke_index: int,
    property: str,
    value: Any,
) -> dict[str, Any]:
    """Set a property on an annotation stroke.

    Args:
        annotation_name: Name of the annotation data block.
        layer_name: Name of the layer containing the stroke.
        stroke_index: Index of the stroke in the layer (0-based).
        property: Property to set. One of: line_width, material_index, display_mode.
        value: The value to set.

    Returns:
        Confirmation dict.
    """
    annotation_name = validate_object_name(annotation_name)
    layer_name = validate_object_name(layer_name)
    stroke_index = validate_numeric_range(stroke_index, min_val=0, name="stroke_index")
    validate_enum(property, ALLOWED_GP_STROKE_PROPERTIES, name="property")
    value = coerce_scalar(value)

    conn = get_connection()
    response = conn.send_command("set_annotation_stroke_property", {
        "annotation_name": annotation_name,
        "layer_name": layer_name,
        "stroke_index": stroke_index,
        "property": property,
        "value": value,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


ALLOWED_LINEART_SOURCES = {"SCENE", "COLLECTION", "OBJECT"}
MAX_GP_COORDINATE = 100000.0
MAX_GP_RADIUS = 10.0
MAX_GP_FRAME = 1_048_574


def _send_gp_command(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _point(p: Any, name: str) -> list[float]:
    validate_vector(p, size=3, name=name)
    return [float(validate_numeric_range(v, min_val=-MAX_GP_COORDINATE,
                                         max_val=MAX_GP_COORDINATE, name=name)) for v in p]


def _rgba(color: Any) -> list[float]:
    values = [float(c) for c in validate_color(color)]
    return values if len(values) == 4 else values + [1.0]


@mcp.tool()
def create_grease_pencil(
    name: str = "Drawing",
    location: list[float] | tuple[float, ...] = (0, 0, 0),
    layer_name: str = "Lines",
) -> dict[str, Any]:
    """Create a Grease Pencil object to draw 2D strokes in 3D space.

    Draw into it with add_gp_stroke; colour strokes with create_gp_material.
    For notes on the viewport use the annotation tools instead.

    Args:
        name: Object name.
        location: Position [x, y, z].
        layer_name: Name of its first layer.

    Returns:
        Dict with the object, layer and frame created.
    """
    return _send_gp_command("create_grease_pencil", {
        "name": validate_new_name(name),
        "location": _point(location, "location"),
        "layer_name": validate_object_name(layer_name),
    })


@mcp.tool()
def create_gp_material(
    name: str,
    color: list[float] | tuple[float, ...] = (0, 0, 0, 1),
) -> dict[str, Any]:
    """Create a Grease Pencil material: the stroke colour.

    Fills are not offered: in Blender 5.2, strokes built from a script do not
    render their fill.

    Args:
        name: Material name.
        color: Stroke RGBA, components 0.0 to 1.0.

    Returns:
        Dict with the material and its colour.
    """
    return _send_gp_command("create_gp_material",
                            {"name": validate_new_name(name), "color": _rgba(color)})


@mcp.tool()
def add_gp_stroke(
    object_name: str,
    points: list[list[float]],
    layer: str = "",
    frame: int = 1,
    radius: float | list[float] = 0.02,
    cyclic: bool = False,
    material: str = "",
) -> dict[str, Any]:
    """Draw one stroke in a Grease Pencil object.

    Points are in the object's local space. cyclic closes the outline.

    Args:
        object_name: Grease Pencil object (from create_grease_pencil).
        points: 2 to 10000 points, each [x, y, z].
        layer: Layer to draw on; empty uses the active layer, a new name
            creates it.
        frame: Keyframe to draw into (drawings per frame make 2D animation).
        radius: Stroke radius in metres, one value or one per point
            (0.0001 to 10). Varying it tapers the line.
        cyclic: Close the stroke back to its first point.
        material: Grease Pencil material (create_gp_material); empty uses the
            object's first material.

    Returns:
        Dict with the layer, frame and stroke count on that frame.
    """
    if not isinstance(points, list) or not 2 <= len(points) <= MAX_GP_POINTS:
        raise ValidationError(f"points must be a list of 2 to {MAX_GP_POINTS} [x, y, z] points")
    clean_points = [_point(p, "point") for p in points]
    if isinstance(radius, list):
        if len(radius) != len(clean_points):
            raise ValidationError("radius list must have one value per point")
        radii = [float(validate_numeric_range(r, min_val=0.0001, max_val=MAX_GP_RADIUS,
                                              name="radius")) for r in radius]
    else:
        r = float(validate_numeric_range(radius, min_val=0.0001, max_val=MAX_GP_RADIUS,
                                         name="radius"))
        radii = [r] * len(clean_points)
    return _send_gp_command("add_gp_stroke", {
        "object_name": validate_object_name(object_name),
        "points": clean_points,
        "layer": validate_object_name(layer) if layer else "",
        "frame": validate_int(frame, -MAX_GP_FRAME, MAX_GP_FRAME, name="frame"),
        "radius": radii,
        "cyclic": bool(cyclic),
        "material": validate_object_name(material) if material else "",
    })


@mcp.tool()
def add_lineart(
    source: str = "SCENE",
    source_name: str = "",
    name: str = "LineArt",
    thickness: float = 0.01,
    color: list[float] | tuple[float, ...] = (0, 0, 0, 1),
    crease_angle: float = 2.443,
    use_intersection: bool = True,
) -> dict[str, Any]:
    """Add Line Art: inked outlines generated from 3D geometry, as seen by the
    active camera. Gives renders a comic, technical or toon look.

    Args:
        source: SCENE (everything), COLLECTION or OBJECT.
        source_name: The collection or object when source is not SCENE.
        name: Name for the Line Art object.
        thickness: Line radius in metres, 0.0001 to 1.0.
        color: Line RGBA, components 0.0 to 1.0.
        crease_angle: Edges sharper than this get lines, radians 0 to 3.1416
            (2.443 is 140 degrees; lower draws more lines).
        use_intersection: Draw lines where objects intersect.

    Returns:
        Dict with the Line Art object and its source.
    """
    source = validate_enum(source, ALLOWED_LINEART_SOURCES, name="source")
    if source != "SCENE" and not source_name:
        raise ValidationError(f"source {source} needs source_name")
    return _send_gp_command("add_lineart", {
        "source": source,
        "source_name": validate_object_name(source_name) if source_name else "",
        "name": validate_new_name(name),
        "thickness": float(validate_numeric_range(thickness, min_val=0.0001, max_val=1.0,
                                                  name="thickness")),
        "color": _rgba(color),
        "crease_angle": float(validate_numeric_range(crease_angle, min_val=0.0,
                                                     max_val=3.1416, name="crease_angle")),
        "use_intersection": bool(use_intersection),
    })
