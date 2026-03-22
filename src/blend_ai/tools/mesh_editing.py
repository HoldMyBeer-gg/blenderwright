"""MCP tools for edit-mode mesh operations (faces, edges, vertices, normals)."""

import math
from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
    validate_numeric_range,
    validate_vector,
)


@mcp.tool()
def inset_faces(
    object_name: str, thickness: float = 0.1, depth: float = 0.0
) -> dict[str, Any]:
    """Inset all faces of a mesh, creating a border/frame around each face.

    Core hard-surface modeling operation for adding detail, panel lines, or
    preparing faces for extrusion.

    Args:
        object_name: Name of the mesh object.
        thickness: Inset thickness (border width). Range: 0.0-10.0.
        depth: Inset depth (positive=outward, negative=inward). Range: -10.0 to 10.0.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(thickness, min_val=0.0, max_val=10.0, name="thickness")
    validate_numeric_range(depth, min_val=-10.0, max_val=10.0, name="depth")

    conn = get_connection()
    response = conn.send_command("inset_faces", {
        "object_name": object_name,
        "thickness": thickness,
        "depth": depth,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def fill_faces(object_name: str) -> dict[str, Any]:
    """Fill selected edges with a face.

    Creates faces from a closed edge loop. Useful for closing gaps in meshes
    or capping open ends.

    Args:
        object_name: Name of the mesh object.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("fill_faces", {"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def grid_fill(
    object_name: str, span: int = 1, offset: int = 0
) -> dict[str, Any]:
    """Fill a closed edge loop with a grid of quads.

    Creates a clean quad grid between edge loops. Better than fill_faces
    for maintaining good topology.

    Args:
        object_name: Name of the mesh object.
        span: Number of grid columns. Range: 1-1000.
        offset: Offset for the grid alignment. Range: 0-1000.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(span, min_val=1, max_val=1000, name="span")
    validate_numeric_range(offset, min_val=0, max_val=1000, name="offset")

    conn = get_connection()
    response = conn.send_command("grid_fill", {
        "object_name": object_name,
        "span": span,
        "offset": offset,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def mark_seam(object_name: str, clear: bool = False) -> dict[str, Any]:
    """Mark or clear UV seams on all edges of a mesh.

    UV seams guide the UV unwrapping process. Edges marked as seams define
    where the mesh is "cut" when unwrapped to 2D.

    Args:
        object_name: Name of the mesh object.
        clear: If True, clear seams instead of marking them.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("mark_seam", {
        "object_name": object_name,
        "clear": clear,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def mark_sharp(object_name: str, clear: bool = False) -> dict[str, Any]:
    """Mark or clear sharp edges on a mesh.

    Sharp edges control auto-smooth shading. Edges marked as sharp will have
    a hard edge in the shading even with smooth shading enabled.

    Args:
        object_name: Name of the mesh object.
        clear: If True, clear sharp marks instead of setting them.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("mark_sharp", {
        "object_name": object_name,
        "clear": clear,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def recalculate_normals(object_name: str, inside: bool = False) -> dict[str, Any]:
    """Recalculate face normals to be consistent (all pointing outward or inward).

    Fixes meshes with flipped or inconsistent normals that cause shading artifacts.

    Args:
        object_name: Name of the mesh object.
        inside: If True, normals point inward instead of outward.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("recalculate_normals", {
        "object_name": object_name,
        "inside": inside,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def flip_normals(object_name: str) -> dict[str, Any]:
    """Flip the direction of all face normals on a mesh.

    Reverses inside/outside of all faces. Use recalculate_normals instead
    if normals are inconsistent rather than uniformly wrong.

    Args:
        object_name: Name of the mesh object.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("flip_normals", {"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def quads_to_tris(object_name: str) -> dict[str, Any]:
    """Convert all quad faces to triangles.

    Useful for game engine export or when triangulated geometry is required.

    Args:
        object_name: Name of the mesh object.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("quads_to_tris", {"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def tris_to_quads(object_name: str) -> dict[str, Any]:
    """Convert adjacent triangle pairs to quad faces where possible.

    Improves topology for subdivision and deformation. Not all triangles
    can be merged — only adjacent pairs with compatible angles.

    Args:
        object_name: Name of the mesh object.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("tris_to_quads", {"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def dissolve_faces(object_name: str) -> dict[str, Any]:
    """Dissolve all faces, merging them into surrounding geometry.

    Removes faces while keeping the surrounding mesh structure intact.
    Cleaner than deleting faces which leaves holes.

    Args:
        object_name: Name of the mesh object.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("dissolve_faces", {"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def dissolve_edges(object_name: str) -> dict[str, Any]:
    """Dissolve all edges, merging adjacent faces.

    Simplifies topology by removing unnecessary edge loops while
    preserving the overall shape.

    Args:
        object_name: Name of the mesh object.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("dissolve_edges", {"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def dissolve_verts(object_name: str) -> dict[str, Any]:
    """Dissolve all vertices, merging connected edges and faces.

    Removes vertices while preserving surrounding geometry.

    Args:
        object_name: Name of the mesh object.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("dissolve_verts", {"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def knife_project(object_name: str, cutter_name: str) -> dict[str, Any]:
    """Project a cutter object's outline onto a mesh to cut it.

    The cutter object (curve or mesh) is projected from the viewport onto
    the target mesh, cutting new edges into it.

    Args:
        object_name: Name of the mesh to cut into.
        cutter_name: Name of the cutter object (curve or mesh) to project.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    cutter_name = validate_object_name(cutter_name)

    conn = get_connection()
    response = conn.send_command("knife_project", {
        "object_name": object_name,
        "cutter_name": cutter_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def spin_mesh(
    object_name: str,
    angle: float = math.tau,
    steps: int = 12,
    axis: list[float] | tuple[float, ...] = (0, 0, 1),
    center: list[float] | tuple[float, ...] = (0, 0, 0),
) -> dict[str, Any]:
    """Spin (lathe) mesh geometry around an axis.

    Creates rotational geometry by duplicating and rotating the selected
    geometry around a center point. Great for creating round shapes like
    vases, columns, or wheels.

    Args:
        object_name: Name of the mesh object.
        angle: Total spin angle in radians. Range: -6.283 to 6.283 (full circle).
        steps: Number of steps in the spin. Range: 1-1000.
        axis: Spin axis as XYZ vector. Defaults to Z-up (0, 0, 1).
        center: Center point for the spin as XYZ. Defaults to origin.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(angle, min_val=-math.tau, max_val=math.tau, name="angle")
    validate_numeric_range(steps, min_val=1, max_val=1000, name="steps")
    axis = validate_vector(axis, size=3, name="axis")
    center = validate_vector(center, size=3, name="center")

    conn = get_connection()
    response = conn.send_command("spin_mesh", {
        "object_name": object_name,
        "angle": angle,
        "steps": steps,
        "axis": axis,
        "center": center,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_edge_crease(object_name: str, value: float = 1.0) -> dict[str, Any]:
    """Set edge crease value on all edges for subdivision surface control.

    Crease values control how sharp edges remain when a Subdivision Surface
    modifier is applied. 0 = fully smooth, 1 = fully sharp.

    Args:
        object_name: Name of the mesh object.
        value: Crease value. Range: -1.0 to 1.0.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(value, min_val=-1.0, max_val=1.0, name="value")

    conn = get_connection()
    response = conn.send_command("set_edge_crease", {
        "object_name": object_name,
        "value": value,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def select_linked(object_name: str) -> dict[str, Any]:
    """Select all geometry linked to the current selection.

    Expands selection to include all connected vertices, edges, and faces.
    Useful for isolating mesh islands or selecting connected components.

    Args:
        object_name: Name of the mesh object.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("select_linked", {"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
