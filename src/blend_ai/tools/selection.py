"""MCP tools for selecting part of a mesh.

Every mesh editing handler used to select the whole mesh before acting, so
"bevel the top edge" or "inset the front face" could not be expressed and
sixteen tools quietly did their job to everything.

Selection is not state this server invents. Blender keeps it on the mesh data
as vertex, edge and polygon select flags: it survives leaving edit mode,
survives deselecting the object, and is saved in the .blend. These tools set
it, and the mesh tools read it when asked to.

bpy.ops.mesh.loop_select is deliberately absent. It requires a view3d region
and a click position, so over a socket it always fails.
"""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    ValidationError,
    validate_enum,
    validate_numeric_range,
    validate_object_name,
)

ALLOWED_SELECT_ACTIONS = {"SELECT", "DESELECT", "INVERT", "TOGGLE"}

ALLOWED_ELEMENTS = {"VERTEX", "EDGE", "FACE"}

ALLOWED_AXES = {"X", "Y", "Z"}
ALLOWED_AXIS_SIGNS = {"POS", "NEG", "ALIGN"}

# Blender's own enum for bpy.ops.mesh.select_similar, read from the running
# build. The names are prefixed by element type: FACE_AREA, not AREA.
ALLOWED_SIMILAR_TYPES = {
    "VERT_NORMAL", "VERT_FACES", "VERT_GROUPS", "VERT_EDGES", "VERT_CREASE",
    "EDGE_LENGTH", "EDGE_DIR", "EDGE_FACES", "EDGE_FACE_ANGLE", "EDGE_CREASE",
    "EDGE_BEVEL", "EDGE_SEAM", "EDGE_SHARP", "EDGE_FREESTYLE",
    "FACE_MATERIAL", "FACE_AREA", "FACE_SIDES", "FACE_PERIMETER",
    "FACE_NORMAL", "FACE_COPLANAR", "FACE_SMOOTH", "FACE_FREESTYLE",
}

ALLOWED_SIDE_COMPARISONS = {"LESS", "EQUAL", "GREATER", "NOTEQUAL"}

MAX_SELECTION_INDICES = 10000


def _send(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def select_all_geometry(object_name: str, action: str = "SELECT") -> dict[str, Any]:
    """Select, deselect or invert all geometry on a mesh.

    Args:
        object_name: Name of the mesh object.
        action: One of: SELECT, DESELECT, INVERT, TOGGLE.

    Returns:
        Dict with the counts selected afterwards.
    """
    object_name = validate_object_name(object_name)
    action = validate_enum(action, ALLOWED_SELECT_ACTIONS, name="action")
    return _send("select_all_geometry",
                 {"object_name": object_name, "action": action})


@mcp.tool()
def select_by_index(
    object_name: str,
    element: str,
    indices: list[int],
    extend: bool = False,
) -> dict[str, Any]:
    """Select specific vertices, edges or faces by index.

    The deterministic way to select: no operator, no viewport, no guessing.
    analyze_mesh_quality reports sample indices for each defect it finds, so
    this is how to act on them.

    Args:
        object_name: Name of the mesh object.
        element: One of: VERTEX, EDGE, FACE.
        indices: Indices to select. Must be non-negative and within the mesh.
        extend: Add to the current selection instead of replacing it.

    Returns:
        Dict with how many elements were selected and the mesh's totals.
    """
    object_name = validate_object_name(object_name)
    element = validate_enum(element, ALLOWED_ELEMENTS, name="element")

    if not isinstance(indices, (list, tuple)) or not indices:
        raise ValidationError(
            "indices is empty, so this would select nothing and report "
            "success. Pass at least one index."
        )
    if len(indices) > MAX_SELECTION_INDICES:
        raise ValidationError(
            f"indices has {len(indices)} entries, over the {MAX_SELECTION_INDICES} "
            f"limit. Use select_similar or select_by_axis for large selections."
        )
    cleaned = []
    for i, value in enumerate(indices):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(f"indices[{i}] must be an integer, got {value!r}")
        if value < 0:
            raise ValidationError(f"indices[{i}] is negative: {value}")
        cleaned.append(value)

    return _send("select_by_index", {
        "object_name": object_name,
        "element": element,
        "indices": cleaned,
        "extend": bool(extend),
    })


@mcp.tool()
def select_by_axis(
    object_name: str,
    axis: str = "Z",
    sign: str = "POS",
    extend: bool = False,
) -> dict[str, Any]:
    """Select geometry on one side of the object along an axis.

    The usual way to say "the top", "the front" or "the left half".

    Args:
        object_name: Name of the mesh object.
        axis: One of: X, Y, Z.
        sign: POS for the positive side, NEG for the negative side, ALIGN for
            geometry lying in the plane.
        extend: Add to the current selection instead of replacing it.

    Returns:
        Dict with how many elements were selected.
    """
    object_name = validate_object_name(object_name)
    axis = validate_enum(axis, ALLOWED_AXES, name="axis")
    sign = validate_enum(sign, ALLOWED_AXIS_SIGNS, name="sign")
    return _send("select_by_axis", {
        "object_name": object_name,
        "axis": axis,
        "sign": sign,
        "extend": bool(extend),
    })


@mcp.tool()
def select_similar(
    object_name: str,
    type: str = "FACE_AREA",
    threshold: float = 0.0,
) -> dict[str, Any]:
    """Grow the current selection to geometry that resembles it.

    Requires something to already be selected: it compares against that.

    Args:
        object_name: Name of the mesh object.
        type: What to compare. Face options: FACE_MATERIAL, FACE_AREA,
            FACE_SIDES, FACE_PERIMETER, FACE_NORMAL, FACE_COPLANAR,
            FACE_SMOOTH, FACE_FREESTYLE. Edge options: EDGE_LENGTH, EDGE_DIR,
            EDGE_FACES, EDGE_FACE_ANGLE, EDGE_CREASE, EDGE_BEVEL, EDGE_SEAM,
            EDGE_SHARP, EDGE_FREESTYLE. Vertex options: VERT_NORMAL,
            VERT_FACES, VERT_GROUPS, VERT_EDGES, VERT_CREASE.
        threshold: How close a match must be, 0.0 to 1.0.

    Returns:
        Dict with how many elements were selected.
    """
    object_name = validate_object_name(object_name)
    type = validate_enum(type, ALLOWED_SIMILAR_TYPES, name="type")
    threshold = validate_numeric_range(threshold, min_val=0.0, max_val=1.0,
                                       name="threshold")
    return _send("select_similar", {
        "object_name": object_name,
        "type": type,
        "threshold": threshold,
    })


@mcp.tool()
def select_faces_by_sides(
    object_name: str,
    number: int = 4,
    comparison: str = "EQUAL",
    extend: bool = False,
) -> dict[str, Any]:
    """Select faces by how many sides they have.

    The direct way to find ngons (GREATER than 4) or triangles (EQUAL to 3),
    which is what topology cleanup usually needs.

    Args:
        object_name: Name of the mesh object.
        number: Number of sides to compare against. A face has at least 3.
        comparison: One of: LESS, EQUAL, GREATER, NOTEQUAL.
        extend: Add to the current selection instead of replacing it.

    Returns:
        Dict with how many faces were selected.
    """
    object_name = validate_object_name(object_name)
    comparison = validate_enum(comparison, ALLOWED_SIDE_COMPARISONS,
                               name="comparison")
    number = validate_numeric_range(number, min_val=3, max_val=1000, name="number")
    return _send("select_faces_by_sides", {
        "object_name": object_name,
        "number": int(number),
        "comparison": comparison,
        "extend": bool(extend),
    })


@mcp.tool()
def get_selection(object_name: str) -> dict[str, Any]:
    """Report what is currently selected on a mesh.

    Without this a caller cannot see the result of its own selection, and the
    mesh tools that act on the current selection would be operating blind.

    Args:
        object_name: Name of the mesh object.

    Returns:
        Dict with selected and total counts per element type, and the first
        50 selected indices of each, so a caller can confirm before acting.
    """
    object_name = validate_object_name(object_name)
    return _send("get_selection", {"object_name": object_name})
