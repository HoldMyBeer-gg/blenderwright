"""MCP tools for Blender mesh quality analysis."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    ValidationError,
    validate_numeric_range,
    validate_object_name,
)


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


@mcp.tool()
def repair_mesh(
    object_name: str,
    remove_loose: bool = True,
    dissolve_degenerate: bool = True,
    fill_holes: bool = False,
) -> dict[str, Any]:
    """Repair the defects analyze_mesh_quality reports.

    Pairs with analyze_mesh_quality: run that first, then call this with the
    repairs the report calls for. Removing loose geometry and dissolving
    degenerate faces cannot change a well-formed mesh, so both are on by
    default. Filling holes creates new geometry and is opt-in.

    Args:
        object_name: Name of the mesh object to repair.
        remove_loose: Delete loose vertices and wire edges, the ones reported
            as loose_vertex_count and wire_edge_count.
        dissolve_degenerate: Dissolve zero-area faces and zero-length edges,
            reported as zero_area_face_count.
        fill_holes: Close boundary loops, which reduces non_manifold_edge_count
            but invents geometry to do it.

    Returns:
        Dict with the counts before and after, so the effect is visible.
    """
    object_name = validate_object_name(object_name)
    if not (remove_loose or dissolve_degenerate or fill_holes):
        raise ValidationError(
            "no repair selected, so this would report success having done "
            "nothing. Enable at least one of remove_loose, "
            "dissolve_degenerate or fill_holes."
        )

    conn = get_connection()
    response = conn.send_command("repair_mesh", {
        "object_name": object_name,
        "remove_loose": remove_loose,
        "dissolve_degenerate": dissolve_degenerate,
        "fill_holes": fill_holes,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def decimate_mesh(object_name: str, ratio: float = 0.5) -> dict[str, Any]:
    """Reduce a mesh's polygon count, collapsing edges to hit a target.

    The counterpart to subdivision: an agent that has stacked Subdivision
    modifiers has otherwise no way back down, and a dense mesh slows every
    later operation.

    Args:
        object_name: Name of the mesh object to simplify.
        ratio: Fraction of faces to keep, between 0 and 1. 0.5 halves the
            face count. 1.0 keeps everything and is refused as a no-op.

    Returns:
        Dict with the face count before and after.
    """
    object_name = validate_object_name(object_name)
    ratio = validate_numeric_range(ratio, min_val=0.0, max_val=1.0, name="ratio")
    if ratio <= 0 or ratio >= 1:
        raise ValidationError(
            f"ratio must be between 0 and 1 exclusive, got {ratio}. "
            f"1.0 keeps every face and 0 deletes the mesh."
        )

    conn = get_connection()
    response = conn.send_command("decimate_mesh", {
        "object_name": object_name,
        "ratio": ratio,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
