"""MCP tools for Blender viewport operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import validate_object_name, validate_enum

# Allowed viewport shading modes
ALLOWED_SHADING_MODES = {"WIREFRAME", "SOLID", "MATERIAL", "RENDERED"}

# Allowed viewport overlay properties
ALLOWED_OVERLAYS = {
    "show_wireframes",
    "show_face_orientation",
    "show_floor",
    "show_axis_x",
    "show_axis_y",
    "show_axis_z",
    "show_cursor",
    "show_object_origins",
    "show_relationship_lines",
    "show_stats",
}


@mcp.tool()
def set_viewport_shading(
    mode: str,
) -> dict[str, Any]:
    """Set the viewport shading mode.

    Args:
        mode: Shading mode. One of: WIREFRAME, SOLID, MATERIAL, RENDERED.

    Returns:
        Confirmation dict with the new shading mode.
    """
    validate_enum(mode, ALLOWED_SHADING_MODES, name="mode")

    conn = get_connection()
    response = conn.send_command("set_viewport_shading", {
        "mode": mode,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_viewport_overlay(
    overlay: str,
    enabled: bool,
) -> dict[str, Any]:
    """Toggle a viewport overlay setting.

    Args:
        overlay: Overlay property name. One of: show_wireframes, show_face_orientation,
                 show_floor, show_axis_x, show_axis_y, show_axis_z, show_cursor,
                 show_object_origins, show_relationship_lines, show_stats.
        enabled: Whether the overlay should be enabled.

    Returns:
        Confirmation dict with the overlay name and state.
    """
    validate_enum(overlay, ALLOWED_OVERLAYS, name="overlay")

    conn = get_connection()
    response = conn.send_command("set_viewport_overlay", {
        "overlay": overlay,
        "enabled": enabled,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def focus_on_object(
    object_name: str,
) -> dict[str, Any]:
    """Frame/focus the viewport on a specific object.

    Selects the object and uses View Selected to center the viewport on it.

    Args:
        object_name: Name of the object to focus on.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("focus_on_object", {
        "object_name": object_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
