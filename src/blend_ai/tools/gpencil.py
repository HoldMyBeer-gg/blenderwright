"""MCP tools for Grease Pencil operations."""

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
def create_gpencil_object(
    name: str = "",
    location: list[float] | tuple[float, ...] = (0, 0, 0),
) -> dict[str, Any]:
    """Create a new Grease Pencil object.

    Args:
        name: Optional name for the GP object. Auto-generated if empty.
        location: XYZ position as a 3-element list/tuple. Defaults to origin.

    Returns:
        Dict with the created object's name and location.
    """
    if name:
        name = validate_object_name(name)
    location = validate_vector(location, size=3, name="location")

    conn = get_connection()
    response = conn.send_command("create_gpencil_object", {
        "name": name,
        "location": list(location),
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_gpencil_layer(object_name: str, layer_name: str) -> dict[str, Any]:
    """Add a layer to a Grease Pencil object.

    Layers organize GP strokes. Each layer can have its own blend mode,
    opacity, and color.

    Args:
        object_name: Name of the Grease Pencil object.
        layer_name: Name for the new layer.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    layer_name = validate_object_name(layer_name)

    conn = get_connection()
    response = conn.send_command("add_gpencil_layer", {
        "object_name": object_name,
        "layer_name": layer_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def remove_gpencil_layer(object_name: str, layer_name: str) -> dict[str, Any]:
    """Remove a layer from a Grease Pencil object.

    Args:
        object_name: Name of the Grease Pencil object.
        layer_name: Name of the layer to remove.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    layer_name = validate_object_name(layer_name)

    conn = get_connection()
    response = conn.send_command("remove_gpencil_layer", {
        "object_name": object_name,
        "layer_name": layer_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_gpencil_stroke(
    object_name: str,
    layer_name: str,
    points: list[list[float]],
    pressure: float = 1.0,
    strength: float = 1.0,
) -> dict[str, Any]:
    """Add a stroke to a Grease Pencil layer.

    Creates a new stroke with the given points on the specified layer.

    Args:
        object_name: Name of the Grease Pencil object.
        layer_name: Name of the layer to add the stroke to.
        points: List of XYZ coordinates, e.g. [[0,0,0], [1,1,0], [2,0,0]].
            Maximum 10000 points.
        pressure: Pen pressure for all points. Range: 0.0-1.0.
        strength: Stroke strength/opacity for all points. Range: 0.0-1.0.

    Returns:
        Confirmation dict with point count.
    """
    object_name = validate_object_name(object_name)
    layer_name = validate_object_name(layer_name)

    if not points or not isinstance(points, list):
        raise ValidationError("points must be a non-empty list of [x, y, z] coordinates")
    if len(points) > MAX_GP_POINTS:
        raise ValidationError(f"points list exceeds maximum of {MAX_GP_POINTS}")

    validated_points = []
    for i, pt in enumerate(points):
        validated_points.append(list(validate_vector(pt, size=3, name=f"points[{i}]")))

    validate_numeric_range(pressure, min_val=0.0, max_val=1.0, name="pressure")
    validate_numeric_range(strength, min_val=0.0, max_val=1.0, name="strength")

    conn = get_connection()
    response = conn.send_command("add_gpencil_stroke", {
        "object_name": object_name,
        "layer_name": layer_name,
        "points": validated_points,
        "pressure": pressure,
        "strength": strength,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_gpencil_stroke_property(
    object_name: str,
    layer_name: str,
    stroke_index: int,
    property: str,
    value: Any,
) -> dict[str, Any]:
    """Set a property on a Grease Pencil stroke.

    Args:
        object_name: Name of the Grease Pencil object.
        layer_name: Name of the layer containing the stroke.
        stroke_index: Index of the stroke in the layer (0-based).
        property: Property to set. One of: line_width, material_index, display_mode.
        value: The value to set.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    layer_name = validate_object_name(layer_name)
    validate_numeric_range(stroke_index, min_val=0, name="stroke_index")
    validate_enum(property, ALLOWED_GP_STROKE_PROPERTIES, name="property")

    conn = get_connection()
    response = conn.send_command("set_gpencil_stroke_property", {
        "object_name": object_name,
        "layer_name": layer_name,
        "stroke_index": stroke_index,
        "property": property,
        "value": value,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
