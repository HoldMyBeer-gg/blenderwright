"""MCP tools for Blender object transforms."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
    validate_enum,
    validate_vector,
    validate_numeric_range,
)

# Allowed rotation modes
ALLOWED_ROTATION_MODES = {"EULER", "QUATERNION"}

# Allowed origin types
ALLOWED_ORIGIN_TYPES = {
    "GEOMETRY",
    "CURSOR",
    "CENTER_OF_MASS",
    "CENTER_OF_VOLUME",
}


@mcp.tool()
def set_location(name: str, location: list[float] | tuple[float, ...]) -> dict[str, Any]:
    """Set the position of an object.

    Args:
        name: Name of the object.
        location: XYZ position as a 3-element list/tuple.

    Returns:
        Dict with the object name and new location.
    """
    name = validate_object_name(name)
    location = validate_vector(location, size=3, name="location")

    conn = get_connection()
    response = conn.send_command("set_location", {"name": name, "location": list(location)})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_rotation(
    name: str,
    rotation: list[float] | tuple[float, ...],
    mode: str = "EULER",
) -> dict[str, Any]:
    """Set the rotation of an object.

    Args:
        name: Name of the object.
        rotation: Rotation values. For EULER mode, XYZ angles in radians (3 elements).
                  For QUATERNION mode, WXYZ values (4 elements).
        mode: Rotation mode, either EULER or QUATERNION. Defaults to EULER.

    Returns:
        Dict with the object name and new rotation.
    """
    name = validate_object_name(name)
    mode = validate_enum(mode, ALLOWED_ROTATION_MODES, name="mode")

    if mode == "EULER":
        rotation = validate_vector(rotation, size=3, name="rotation")
    else:
        rotation = validate_vector(rotation, size=4, name="rotation")

    conn = get_connection()
    response = conn.send_command("set_rotation", {
        "name": name,
        "rotation": list(rotation),
        "mode": mode,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_scale(name: str, scale: list[float] | tuple[float, ...]) -> dict[str, Any]:
    """Set the scale of an object.

    Args:
        name: Name of the object.
        scale: XYZ scale as a 3-element list/tuple.

    Returns:
        Dict with the object name and new scale.
    """
    name = validate_object_name(name)
    scale = validate_vector(scale, size=3, name="scale")

    conn = get_connection()
    response = conn.send_command("set_scale", {"name": name, "scale": list(scale)})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def apply_transforms(
    name: str,
    location: bool = True,
    rotation: bool = True,
    scale: bool = True,
) -> dict[str, Any]:
    """Apply (freeze) transforms on an object, making current transforms the new basis.

    Args:
        name: Name of the object.
        location: Apply location transform. Defaults to True.
        rotation: Apply rotation transform. Defaults to True.
        scale: Apply scale transform. Defaults to True.

    Returns:
        Confirmation dict.
    """
    name = validate_object_name(name)

    conn = get_connection()
    response = conn.send_command("apply_transforms", {
        "name": name,
        "location": location,
        "rotation": rotation,
        "scale": scale,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_origin(name: str, type: str = "GEOMETRY") -> dict[str, Any]:
    """Set the origin point of an object.

    Args:
        name: Name of the object.
        type: Origin type. One of: GEOMETRY (origin to geometry center),
              CURSOR (origin to 3D cursor), CENTER_OF_MASS (origin to center of mass),
              CENTER_OF_VOLUME (origin to center of volume). Defaults to GEOMETRY.

    Returns:
        Confirmation dict with new origin location.
    """
    name = validate_object_name(name)
    type = validate_enum(type, ALLOWED_ORIGIN_TYPES, name="type")

    conn = get_connection()
    response = conn.send_command("set_origin", {"name": name, "type": type})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def snap_to_grid(name: str, grid_size: float = 1.0) -> dict[str, Any]:
    """Snap an object's location to the nearest grid point.

    Args:
        name: Name of the object.
        grid_size: Size of the grid cells. Defaults to 1.0.

    Returns:
        Dict with the object name and snapped location.
    """
    name = validate_object_name(name)
    validate_numeric_range(grid_size, min_val=0.001, max_val=1000.0, name="grid_size")

    conn = get_connection()
    response = conn.send_command("snap_to_grid", {"name": name, "grid_size": grid_size})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
