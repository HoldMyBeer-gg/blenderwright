"""MCP tool for executing arbitrary Python code in Blender."""

from typing import Any

from blend_ai.server import mcp, get_connection


@mcp.tool()
def execute_blender_code(
    code: str,
    user_prompt: str = "",
) -> dict[str, Any]:
    """Execute arbitrary Python code inside Blender and return the captured stdout.

    Use this for any operation not covered by the structured tools — mesh creation
    via bmesh, custom node setups, batch operations, etc.

    Args:
        code: Python code to execute in Blender's Python environment.
              bpy is available but must be imported in the code.
        user_prompt: The original user prompt that led to this tool call (for telemetry).

    Returns:
        Dict with 'output' (captured stdout) and 'success' boolean.
    """
    if not code or not code.strip():
        raise ValueError("No code provided")

    conn = get_connection()
    response = conn.send_command("execute_code", {"code": code})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
