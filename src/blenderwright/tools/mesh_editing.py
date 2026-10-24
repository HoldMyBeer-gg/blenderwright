"""MCP tools for edit-mode mesh operations (faces, edges, vertices, normals)."""

import math
from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_enum,
    ValidationError,
    validate_object_name,
    validate_numeric_range,
    validate_vector,
)



# Whether a mesh tool acts on everything or only on what the caller selected.
# Selection lives on the mesh data, so "CURRENT" reads state Blender already
# keeps; see the select_* tools in blenderwright.tools.selection.
ALLOWED_SELECTION_MODES = {"ALL", "CURRENT"}

ALLOWED_SYMMETRIZE_DIRECTIONS = {
    "NEGATIVE_X", "POSITIVE_X", "NEGATIVE_Y", "POSITIVE_Y", "NEGATIVE_Z", "POSITIVE_Z",
}
ALLOWED_LOOP_OPERATIONS = {"CIRCLE", "SPACE", "FLATTEN"}
MAX_COORDINATE = 1_000_000.0

@mcp.tool()
def inset_faces(
    object_name: str, thickness: float = 0.1, depth: float = 0.0,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Inset all faces of a mesh, creating a border/frame around each face.

    Core hard-surface modeling operation for adding detail, panel lines, or
    preparing faces for extrusion.

    On a closed mesh, selection="ALL" does nothing: a region with no boundary
    has nothing to inset from, and Blender reports success having changed
    nothing. Measured on a default cube in 5.1, the vertex, edge and face
    counts are identical afterwards. Select the faces you mean and pass
    selection="CURRENT".

    Args:
        object_name: Name of the mesh object.
        thickness: Inset thickness (border width). Range: 0.0-10.0.
        depth: Inset depth (positive=outward, negative=inward). Range: -10.0 to 10.0.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")
    thickness = validate_numeric_range(thickness, min_val=0.0, max_val=10.0,
                                       name="thickness")
    if thickness == 0:
        raise ValidationError(
            "thickness of 0 inserts faces on top of the originals and "
            "reports success, leaving a non-manifold mesh."
        )
    depth = validate_numeric_range(depth, min_val=-10.0, max_val=10.0, name="depth")

    conn = get_connection()
    response = conn.send_command("inset_faces", {
        "selection": selection,
        "object_name": object_name,
        "thickness": thickness,
        "depth": depth,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def fill_faces(object_name: str,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Fill selected edges with a face.

    Creates faces from a closed edge loop. Useful for closing gaps in meshes
    or capping open ends.

    Args:
        object_name: Name of the mesh object.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")

    conn = get_connection()
    response = conn.send_command("fill_faces", {
        "selection": selection,"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def grid_fill(
    object_name: str, span: int = 1, offset: int = 0,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Fill a closed edge loop with a grid of quads.

    Creates a clean quad grid between edge loops. Better than fill_faces
    for maintaining good topology.

    Args:
        object_name: Name of the mesh object.
        span: Number of grid columns. Range: 1-1000.
        offset: Offset for the grid alignment. Range: 0-1000.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")
    span = validate_numeric_range(span, min_val=1, max_val=1000, name="span")
    offset = validate_numeric_range(offset, min_val=0, max_val=1000, name="offset")

    conn = get_connection()
    response = conn.send_command("grid_fill", {
        "selection": selection,
        "object_name": object_name,
        "span": span,
        "offset": offset,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def mark_seam(object_name: str, clear: bool = False,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Mark or clear UV seams on all edges of a mesh.

    UV seams guide the UV unwrapping process. Edges marked as seams define
    where the mesh is "cut" when unwrapped to 2D.

    Args:
        object_name: Name of the mesh object.
        clear: If True, clear seams instead of marking them.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")

    conn = get_connection()
    response = conn.send_command("mark_seam", {
        "selection": selection,
        "object_name": object_name,
        "clear": clear,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def mark_sharp(object_name: str, clear: bool = False,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Mark or clear sharp edges on a mesh.

    Sharp edges control auto-smooth shading. Edges marked as sharp will have
    a hard edge in the shading even with smooth shading enabled.

    Args:
        object_name: Name of the mesh object.
        clear: If True, clear sharp marks instead of setting them.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")

    conn = get_connection()
    response = conn.send_command("mark_sharp", {
        "selection": selection,
        "object_name": object_name,
        "clear": clear,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def recalculate_normals(object_name: str, inside: bool = False,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Recalculate face normals to be consistent (all pointing outward or inward).

    Fixes meshes with flipped or inconsistent normals that cause shading artifacts.

    Args:
        object_name: Name of the mesh object.
        inside: If True, normals point inward instead of outward.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")

    conn = get_connection()
    response = conn.send_command("recalculate_normals", {
        "selection": selection,
        "object_name": object_name,
        "inside": inside,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def flip_normals(object_name: str,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Flip the direction of all face normals on a mesh.

    Reverses inside/outside of all faces. Use recalculate_normals instead
    if normals are inconsistent rather than uniformly wrong.

    Args:
        object_name: Name of the mesh object.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")

    conn = get_connection()
    response = conn.send_command("flip_normals", {
        "selection": selection,"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def quads_to_tris(object_name: str,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Convert all quad faces to triangles.

    Useful for game engine export or when triangulated geometry is required.

    Args:
        object_name: Name of the mesh object.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")

    conn = get_connection()
    response = conn.send_command("quads_to_tris", {
        "selection": selection,"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def tris_to_quads(object_name: str,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Convert adjacent triangle pairs to quad faces where possible.

    Improves topology for subdivision and deformation. Not all triangles
    can be merged: only adjacent pairs with compatible angles.

    Args:
        object_name: Name of the mesh object.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")

    conn = get_connection()
    response = conn.send_command("tris_to_quads", {
        "selection": selection,"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def dissolve_faces(object_name: str,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Dissolve all faces, merging them into surrounding geometry.

    Removes faces while keeping the surrounding mesh structure intact.
    Cleaner than deleting faces which leaves holes.

    Args:
        object_name: Name of the mesh object.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")

    conn = get_connection()
    response = conn.send_command("dissolve_faces", {
        "selection": selection,"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def dissolve_edges(object_name: str,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Dissolve all edges, merging adjacent faces.

    Simplifies topology by removing unnecessary edge loops while
    preserving the overall shape.

    Args:
        object_name: Name of the mesh object.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")

    conn = get_connection()
    response = conn.send_command("dissolve_edges", {
        "selection": selection,"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def dissolve_verts(object_name: str,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Dissolve all vertices, merging connected edges and faces.

    Removes vertices while preserving surrounding geometry.

    Args:
        object_name: Name of the mesh object.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")

    conn = get_connection()
    response = conn.send_command("dissolve_verts", {
        "selection": selection,"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def knife_project(object_name: str, cutter_name: str,
) -> dict[str, Any]:
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
    selection: str = "ALL",
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

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")
    angle = validate_numeric_range(angle, min_val=-math.tau, max_val=math.tau, name="angle")
    steps = validate_numeric_range(steps, min_val=1, max_val=1000, name="steps")
    axis = validate_vector(axis, size=3, name="axis")
    if not any(axis):
        raise ValidationError(
            "axis has zero length, so there is no direction to spin "
            "around. The operator runs and produces nothing."
        )
    center = validate_vector(center, size=3, name="center")

    conn = get_connection()
    response = conn.send_command("spin_mesh", {
        "selection": selection,
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
def set_edge_crease(object_name: str, value: float = 1.0,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Set edge crease value on all edges for subdivision surface control.

    Crease values control how sharp edges remain when a Subdivision Surface
    modifier is applied. 0 = fully smooth, 1 = fully sharp.

    Args:
        object_name: Name of the mesh object.
        value: Crease value. Range: -1.0 to 1.0.

        selection: "ALL" to act on the whole mesh, or "CURRENT" to act only
            on what is already selected. Use the select_* tools to choose
            first. Defaults to "ALL".

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    selection = validate_enum(selection, ALLOWED_SELECTION_MODES,
                              name="selection")
    value = validate_numeric_range(value, min_val=-1.0, max_val=1.0, name="value")

    conn = get_connection()
    response = conn.send_command("set_edge_crease", {
        "selection": selection,
        "object_name": object_name,
        "value": value,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def select_linked(object_name: str) -> dict[str, Any]:
    """Grow the current mesh selection to everything connected to it.

    Expands selection to include all connected vertices, edges, and faces.
    Useful for isolating mesh islands or selecting connected components.
    Needs a starting selection: set one with select_by_index or
    select_by_axis first. Works inside one mesh; to select whole objects
    use select_objects.

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


def _send_mesh_command(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _finite_vector(vec: Any, name: str) -> list[float]:
    validate_vector(vec, size=3, name=name)
    return [float(validate_numeric_range(v, min_val=-MAX_COORDINATE, max_val=MAX_COORDINATE,
                                         name=name)) for v in vec]


@mcp.tool()
def symmetrize_mesh(
    object_name: str,
    direction: str = "NEGATIVE_X",
    threshold: float = 0.0001,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Make a mesh symmetrical by copying one half onto the other.

    Fixes a model that drifted out of symmetry, or builds the second half of
    a half-modelled object. Works in the object's local axes.

    Args:
        object_name: Mesh object.
        direction: Which half is copied where. NEGATIVE_X copies the -X side
            onto +X; POSITIVE_X the reverse; likewise for Y and Z.
        threshold: Distance within which vertices on the centre line merge,
            0.0 to 1.0.
        selection: "ALL" for the whole mesh, or "CURRENT" for the part already
            selected with the select_* tools.

    Returns:
        Dict with the direction and the vertex count afterwards.
    """
    return _send_mesh_command("symmetrize_mesh", {
        "object_name": validate_object_name(object_name),
        "direction": validate_enum(direction, ALLOWED_SYMMETRIZE_DIRECTIONS, name="direction"),
        "threshold": validate_numeric_range(threshold, min_val=0.0, max_val=1.0,
                                            name="threshold"),
        "selection": validate_enum(selection, ALLOWED_SELECTION_MODES, name="selection"),
    })


@mcp.tool()
def bisect_mesh(
    object_name: str,
    plane_point: list[float] | tuple[float, ...] = (0, 0, 0),
    plane_normal: list[float] | tuple[float, ...] = (0, 0, 1),
    clear_inner: bool = False,
    clear_outer: bool = False,
    fill: bool = False,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Slice a mesh with a plane, optionally deleting one side and capping the cut.

    Cuts a new edge loop where the plane crosses, which is also a clean way
    to halve a model before adding a Mirror modifier.

    Args:
        object_name: Mesh object.
        plane_point: A point on the cutting plane, in world space.
        plane_normal: The plane's direction, in world space; it need not be
            unit length but must not be zero. [0, 0, 1] is a horizontal cut.
        clear_inner: Delete everything behind the plane (against the normal).
        clear_outer: Delete everything in front of the plane (along the normal).
        fill: Cap the cut with a face. Only useful when one side is cleared.
        selection: "ALL" for the whole mesh, or "CURRENT" for the part already
            selected.

    Returns:
        Dict with the vertex count afterwards.
    """
    point = _finite_vector(plane_point, "plane_point")
    normal = _finite_vector(plane_normal, "plane_normal")
    if not any(normal):
        raise ValidationError("plane_normal has zero length, so the plane has no direction")
    if clear_inner and clear_outer:
        raise ValidationError("clear_inner and clear_outer together would delete everything")
    return _send_mesh_command("bisect_mesh", {
        "object_name": validate_object_name(object_name),
        "plane_point": point,
        "plane_normal": normal,
        "clear_inner": bool(clear_inner),
        "clear_outer": bool(clear_outer),
        "fill": bool(fill),
        "selection": validate_enum(selection, ALLOWED_SELECTION_MODES, name="selection"),
    })


@mcp.tool()
def loop_tools(
    object_name: str,
    operation: str,
    factor: float = 1.0,
    radius: float | None = None,
    selection: str = "CURRENT",
) -> dict[str, Any]:
    """Reshape selected loops: make them round, even or flat.

    Blender 5.2's built-in versions of the LoopTools add-on. Select a loop or
    region first with the select_* tools.

    Args:
        object_name: Mesh object.
        operation: CIRCLE (shape the selection into a circle: round holes
            for bolts and pipes), SPACE (space vertices evenly along the loop),
            or FLATTEN (press the selection onto a best-fit plane).
        factor: How far to move toward the result, 0.0 to 1.0.
        radius: CIRCLE only: a fixed radius instead of the best fit, above 0.
        selection: "CURRENT" (default) for what is selected, or "ALL".

    Returns:
        Dict with the operation and the object.
    """
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "operation": validate_enum(operation, ALLOWED_LOOP_OPERATIONS, name="operation"),
        "factor": validate_numeric_range(factor, min_val=0.0, max_val=1.0, name="factor"),
        "selection": validate_enum(selection, ALLOWED_SELECTION_MODES, name="selection"),
    }
    if radius is not None:
        if operation != "CIRCLE":
            raise ValidationError("radius only applies to the CIRCLE operation")
        params["radius"] = validate_numeric_range(radius, min_val=1e-6, max_val=MAX_COORDINATE,
                                                  name="radius")
    return _send_mesh_command("loop_tools", params)
