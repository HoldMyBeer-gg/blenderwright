"""MCP tools for Blender Annotation operations (Blender 5.x)."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
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
        name = validate_object_name(name)

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

    validate_numeric_range(pressure, min_val=0.0, max_val=1.0, name="pressure")

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
    validate_numeric_range(stroke_index, min_val=0, name="stroke_index")
    validate_enum(property, ALLOWED_GP_STROKE_PROPERTIES, name="property")

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
