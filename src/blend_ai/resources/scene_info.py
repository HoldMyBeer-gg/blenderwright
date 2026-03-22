"""MCP resources for browsing Blender scene information."""

from blend_ai.server import mcp, get_connection


@mcp.resource("blender://scene")
def get_scene_resource() -> str:
    """Current Blender scene information including objects, hierarchy, and settings."""
    conn = get_connection()
    response = conn.send_command("get_scene_info")
    if response.get("status") == "ok":
        import json
        return json.dumps(response["result"], indent=2)
    return f"Error: {response.get('result', 'Unknown error')}"


@mcp.resource("blender://objects")
def get_objects_resource() -> str:
    """List of all objects in the current Blender scene."""
    conn = get_connection()
    response = conn.send_command("list_objects")
    if response.get("status") == "ok":
        import json
        return json.dumps(response["result"], indent=2)
    return f"Error: {response.get('result', 'Unknown error')}"


@mcp.resource("blender://materials")
def get_materials_resource() -> str:
    """List of all materials in the current Blender file."""
    conn = get_connection()
    response = conn.send_command("list_materials")
    if response.get("status") == "ok":
        import json
        return json.dumps(response["result"], indent=2)
    return f"Error: {response.get('result', 'Unknown error')}"
