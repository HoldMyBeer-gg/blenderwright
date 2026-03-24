"""MCP tools for Blender mesh quality analysis."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import validate_object_name


@mcp.tool()
def analyze_mesh_quality(object_name: str) -> dict[str, Any]:
    """Analyze mesh topology quality and return a structured defect report.

    Checks for non-manifold edges, loose vertices, zero-area faces,
    duplicate vertices, and wire edges. Returns counts and sample indices
    (capped at 50 per category) for each defect type.

    Args:
        object_name: Name of the mesh object to analyze.

    Returns:
        Dict with vertex/edge/face counts, defect counts and sample indices,
        and an issues_found boolean.
    """
    object_name = validate_object_name(object_name)
    conn = get_connection()
    response = conn.send_command("analyze_mesh_quality", {"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
