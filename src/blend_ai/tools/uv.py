"""MCP tools for Blender UV mapping operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
    validate_enum,
    validate_numeric_range,
    ValidationError,
)

ALLOWED_UNWRAP_METHODS = {"ANGLE_BASED", "CONFORMAL", "SLIM"}
ALLOWED_PROJECTIONS = {"CUBE", "CYLINDER", "SPHERE"}


@mcp.tool()
def smart_uv_project(
    object_name: str,
    angle_limit: float = 66.0,
    island_margin: float = 0.0,
    area_weight: float = 0.0,
) -> dict[str, Any]:
    """Apply Smart UV Project to a mesh object.

    Automatically unwraps the mesh using angle-based projection.

    Args:
        object_name: Name of the mesh object.
        angle_limit: Angle limit in degrees for splitting faces (0.0-89.0).
        island_margin: Margin between UV islands (0.0-1.0).
        area_weight: Weight given to face area for island arrangement (0.0-1.0).

    Returns:
        Confirmation dict with object name and UV map info.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(angle_limit, min_val=0.0, max_val=89.0, name="angle_limit")
    validate_numeric_range(island_margin, min_val=0.0, max_val=1.0, name="island_margin")
    validate_numeric_range(area_weight, min_val=0.0, max_val=1.0, name="area_weight")

    conn = get_connection()
    response = conn.send_command("smart_uv_project", {
        "object_name": object_name,
        "angle_limit": angle_limit,
        "island_margin": island_margin,
        "area_weight": area_weight,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def uv_unwrap(
    object_name: str,
    method: str = "ANGLE_BASED",
) -> dict[str, Any]:
    """Unwrap a mesh object's UVs using standard unwrap.

    Requires seams to be marked for best results.

    Args:
        object_name: Name of the mesh object.
        method: Unwrap method - ANGLE_BASED or CONFORMAL.

    Returns:
        Confirmation dict with object name.
    """
    object_name = validate_object_name(object_name)
    validate_enum(method, ALLOWED_UNWRAP_METHODS, name="method")

    conn = get_connection()
    response = conn.send_command("uv_unwrap", {
        "object_name": object_name,
        "method": method,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_uv_projection(
    object_name: str,
    projection: str,
) -> dict[str, Any]:
    """Apply a projection-based UV mapping to a mesh object.

    Args:
        object_name: Name of the mesh object.
        projection: Projection type - CUBE, CYLINDER, or SPHERE.

    Returns:
        Confirmation dict with object name and projection type.
    """
    object_name = validate_object_name(object_name)
    validate_enum(projection, ALLOWED_PROJECTIONS, name="projection")

    conn = get_connection()
    response = conn.send_command("set_uv_projection", {
        "object_name": object_name,
        "projection": projection,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def pack_uv_islands(
    object_name: str,
    margin: float = 0.001,
) -> dict[str, Any]:
    """Pack UV islands to fit efficiently within the UV space.

    Args:
        object_name: Name of the mesh object.
        margin: Margin between packed islands (0.0-1.0).

    Returns:
        Confirmation dict with object name.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(margin, min_val=0.0, max_val=1.0, name="margin")

    conn = get_connection()
    response = conn.send_command("pack_uv_islands", {
        "object_name": object_name,
        "margin": margin,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
