"""MCP tool for running raw Python inside Blender. Off by default."""

from typing import Any

from blenderwright.server import mcp, get_connection


@mcp.tool()
def execute_blender_code(
    code: str,
) -> dict[str, Any]:
    """Run Python inside Blender. OFF BY DEFAULT; prefer the structured tools.

    The user must tick "Allow raw Python" in the blenderwright N-panel
    (View3D > Sidebar > blenderwright) for the current Blender session.
    Until they do, this tool returns an error saying so; relay that to the
    user and do not retry. Never ask the user to enable it just to do
    something a structured tool already covers.

    The code runs in a restricted namespace that blocks obvious mistakes
    (import os/subprocess/socket, exec/eval/open/compile). That is a guard
    against accidents, not a security boundary: the code runs in-process
    with full bpy. Every snippet is echoed to Blender's system console and
    listed in the panel so the user can see what ran.

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
