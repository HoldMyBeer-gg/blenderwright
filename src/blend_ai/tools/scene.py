"""MCP tools for Blender scene management."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import validate_object_name, validate_enum, validate_numeric_range, ValidationError

# Allowed scene properties that can be set
ALLOWED_SCENE_PROPERTIES = {
    "frame_start",
    "frame_end",
    "frame_current",
    "frame_step",
    "fps",
    "unit_system",
    "render_engine",
    "use_gravity",
    "gravity",
}

# Allowed unit systems
ALLOWED_UNIT_SYSTEMS = {"NONE", "METRIC", "IMPERIAL"}

# Allowed render engines
ALLOWED_RENDER_ENGINES = {"BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"}


@mcp.tool()
def get_scene_info() -> dict[str, Any]:
    """Get full scene information including object tree, hierarchy, counts, frame range, fps, and render engine.

    Returns a dict with scene name, object list with hierarchy, object type counts,
    frame range (start, end, current), fps, and active render engine.
    """
    conn = get_connection()
    response = conn.send_command("get_scene_info")
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_scene_property(property: str, value: Any) -> dict[str, Any]:
    """Set a scene property such as frame_start, frame_end, frame_current, fps, unit_system, or render_engine.

    Args:
        property: The scene property to set. Must be one of: frame_start, frame_end,
                  frame_current, frame_step, fps, unit_system, render_engine, use_gravity, gravity.
        value: The value to set the property to. Type depends on the property.

    Returns:
        Confirmation dict with the property name and new value.
    """
    validate_enum(property, ALLOWED_SCENE_PROPERTIES, name="property")

    # Validate specific property values
    if property in ("frame_start", "frame_end", "frame_current", "frame_step"):
        validate_numeric_range(value, min_val=0, max_val=1048574, name=property)
    elif property == "fps":
        validate_numeric_range(value, min_val=1, max_val=240, name="fps")
    elif property == "unit_system":
        validate_enum(value, ALLOWED_UNIT_SYSTEMS, name="unit_system")
    elif property == "render_engine":
        validate_enum(value, ALLOWED_RENDER_ENGINES, name="render_engine")

    conn = get_connection()
    response = conn.send_command("set_scene_property", {"property": property, "value": value})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def list_scenes() -> list[dict[str, Any]]:
    """List all scenes in the current Blender file.

    Returns a list of dicts, each containing the scene name and object count.
    """
    conn = get_connection()
    response = conn.send_command("list_scenes")
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def create_scene(name: str) -> dict[str, Any]:
    """Create a new scene.

    Args:
        name: Name for the new scene.

    Returns:
        Confirmation dict with the created scene name.
    """
    name = validate_object_name(name)
    conn = get_connection()
    response = conn.send_command("create_scene", {"name": name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def delete_scene(name: str) -> dict[str, Any]:
    """Delete a scene by name.

    Args:
        name: Name of the scene to delete. Cannot delete the last remaining scene.

    Returns:
        Confirmation dict.
    """
    name = validate_object_name(name)
    conn = get_connection()
    response = conn.send_command("delete_scene", {"name": name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
