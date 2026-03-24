"""MCP tool for executing Python code in Blender's sandboxed environment."""

from typing import Any

from blend_ai.server import mcp, get_connection


@mcp.tool()
def execute_blender_code(
    code: str,
) -> dict[str, Any]:
    """Execute Python code inside Blender's sandboxed environment.

    The code runs in a restricted sandbox that blocks dangerous imports
    (os, subprocess, socket, etc.) and dangerous builtins (exec, eval, open).
    Safe Blender imports (bpy, bmesh, mathutils, math, json) are allowed.

    Args:
        code: Python code to execute. bpy is available but must be imported.

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
