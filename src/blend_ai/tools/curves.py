"""MCP tools for Blender curve and text operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
    validate_enum,
    validate_vector,
    validate_numeric_range,
    ValidationError,
)

ALLOWED_CURVE_TYPES = {"BEZIER", "NURBS", "PATH"}
ALLOWED_HANDLE_TYPES = {"AUTO", "VECTOR", "ALIGNED", "FREE"}
ALLOWED_FILL_MODES = {"FULL", "BACK", "FRONT", "HALF", "NONE"}
ALLOWED_TWIST_MODES = {"Z_UP", "MINIMUM", "TANGENT"}
ALLOWED_CURVE_PROPERTIES = {
    "resolution_u",
    "fill_mode",
    "bevel_depth",
    "bevel_resolution",
    "extrude",
    "twist_mode",
    "use_fill_caps",
}


@mcp.tool()
def create_curve(
    type: str = "BEZIER",
    name: str = "",
    location: list[float] | tuple[float, ...] = (0, 0, 0),
) -> dict[str, Any]:
    """Create a new curve object.

    Args:
        type: Curve type - BEZIER, NURBS, or PATH.
        name: Optional name for the curve object.
        location: 3D location as (x, y, z).

    Returns:
        Dict with created curve name and type.
    """
    validate_enum(type, ALLOWED_CURVE_TYPES, name="type")
    location = validate_vector(location, size=3, name="location")
    if name:
        name = validate_object_name(name)

    conn = get_connection()
    response = conn.send_command("create_curve", {
        "type": type,
        "name": name,
        "location": list(location),
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_curve_point(
    curve_name: str,
    location: list[float] | tuple[float, ...] = (0, 0, 0),
    handle_type: str = "AUTO",
) -> dict[str, Any]:
    """Add a control point to an existing curve.

    Args:
        curve_name: Name of the curve object to add a point to.
        location: 3D location for the new point as (x, y, z).
        handle_type: Handle type - AUTO, VECTOR, ALIGNED, or FREE.

    Returns:
        Dict with curve name and new point count.
    """
    curve_name = validate_object_name(curve_name)
    location = validate_vector(location, size=3, name="location")
    validate_enum(handle_type, ALLOWED_HANDLE_TYPES, name="handle_type")

    conn = get_connection()
    response = conn.send_command("add_curve_point", {
        "curve_name": curve_name,
        "location": list(location),
        "handle_type": handle_type,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_curve_property(
    curve_name: str,
    property: str,
    value: Any,
) -> dict[str, Any]:
    """Set a property on a curve object.

    Args:
        curve_name: Name of the curve object.
        property: Property to set - resolution_u, fill_mode, bevel_depth,
                  bevel_resolution, extrude, twist_mode, or use_fill_caps.
        value: Value to set. Type depends on property.

    Returns:
        Confirmation dict with property name and new value.
    """
    curve_name = validate_object_name(curve_name)
    validate_enum(property, ALLOWED_CURVE_PROPERTIES, name="property")

    # Validate specific property values
    if property == "resolution_u":
        validate_numeric_range(value, min_val=1, max_val=1024, name="resolution_u")
    elif property == "fill_mode":
        validate_enum(value, ALLOWED_FILL_MODES, name="fill_mode")
    elif property == "bevel_depth":
        validate_numeric_range(value, min_val=0.0, name="bevel_depth")
    elif property == "bevel_resolution":
        validate_numeric_range(value, min_val=0, max_val=32, name="bevel_resolution")
    elif property == "extrude":
        validate_numeric_range(value, min_val=0.0, name="extrude")
    elif property == "twist_mode":
        validate_enum(value, ALLOWED_TWIST_MODES, name="twist_mode")
    elif property == "use_fill_caps":
        if not isinstance(value, bool):
            raise ValidationError("use_fill_caps must be a boolean")

    conn = get_connection()
    response = conn.send_command("set_curve_property", {
        "curve_name": curve_name,
        "property": property,
        "value": value,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def convert_curve_to_mesh(curve_name: str) -> dict[str, Any]:
    """Convert a curve object to a mesh object.

    Args:
        curve_name: Name of the curve object to convert.

    Returns:
        Dict with the converted object name.
    """
    curve_name = validate_object_name(curve_name)

    conn = get_connection()
    response = conn.send_command("convert_curve_to_mesh", {
        "curve_name": curve_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def create_text(
    text: str,
    name: str = "",
    location: list[float] | tuple[float, ...] = (0, 0, 0),
    size: float = 1.0,
    font: str = "",
) -> dict[str, Any]:
    """Create a 3D text object.

    Args:
        text: The text string to display.
        name: Optional name for the text object.
        location: 3D location as (x, y, z).
        size: Font size.
        font: Optional path to a font file. Uses default Blender font if empty.

    Returns:
        Dict with created text object name.
    """
    if not text or not isinstance(text, str):
        raise ValidationError("text must be a non-empty string")
    if len(text) > 10000:
        raise ValidationError("text must be 10000 characters or fewer")
    location = validate_vector(location, size=3, name="location")
    validate_numeric_range(size, min_val=0.001, max_val=1000.0, name="size")
    if name:
        name = validate_object_name(name)

    conn = get_connection()
    response = conn.send_command("create_text", {
        "text": text,
        "name": name,
        "location": list(location),
        "size": size,
        "font": font,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
