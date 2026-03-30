"""MCP tools for Blender scene management."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import validate_object_name, validate_enum, validate_numeric_range

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

# Extension catalog with keyword matching for proactive suggestions
EXTENSION_CATALOG = {
    "bool_tool": {
        "name": "Bool Tool",
        "description": "Boolean operations (union, difference, intersect) with automatic cleanup",
        "keywords": ["boolean", "union", "difference", "intersect", "cut", "subtract", "combine", "bool"],
    },
    "looptools": {
        "name": "LoopTools",
        "description": "Advanced loop editing (relax, space, circle, curve, flatten)",
        "keywords": ["loop", "edge loop", "relax", "circle", "curve", "flatten", "space", "ring"],
    },
    "node_wrangler": {
        "name": "Node Wrangler",
        "description": "Shader and geometry node editing shortcuts (lazy connect, preview, switch)",
        "keywords": ["shader", "node", "material", "texture", "geometry nodes", "compositor", "nodes"],
    },
}


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


@mcp.tool()
def suggest_extensions(task_description: str = "") -> dict[str, Any]:
    """Suggest helpful Blender extensions for a planned task.

    Analyzes the task description and recommends free Blender extensions
    that could improve the workflow. Already-installed extensions are excluded.

    Args:
        task_description: Description of the planned task. If empty, returns
            all extensions not currently installed.

    Returns:
        Dict with 'suggestions' list of recommended extensions and
        'installed' list of already-installed extension IDs.
    """
    conn = get_connection()
    response = conn.send_command("get_installed_extensions")
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    installed = response.get("result", {}).get("installed", [])

    task_lower = task_description.lower()
    suggestions = []
    for ext_id, info in EXTENSION_CATALOG.items():
        if ext_id in installed:
            continue
        if not task_description:
            suggestions.append({
                "extension_id": ext_id,
                "name": info["name"],
                "description": info["description"],
            })
        elif any(kw in task_lower for kw in info["keywords"]):
            suggestions.append({
                "extension_id": ext_id,
                "name": info["name"],
                "description": info["description"],
            })

    return {"suggestions": suggestions, "installed": installed}
