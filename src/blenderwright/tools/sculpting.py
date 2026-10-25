"""MCP tools for Blender sculpting operations."""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.tools.deform import _validate_indices
from blenderwright.validators import (
    validate_object_name,
    validate_enum,
    validate_int,
    validate_numeric_range,
    ValidationError,
)

ALLOWED_BRUSH_TYPES = {
    "DRAW", "CLAY", "CLAY_STRIPS", "INFLATE", "GRAB", "SMOOTH",
    "FLATTEN", "FILL", "SCRAPE", "PINCH", "CREASE", "BLOB", "MASK",
    "MULTIRES_DISPLACEMENT_SMEAR",
}
ALLOWED_BRUSH_PROPERTIES = {"size", "strength", "auto_smooth_factor", "use_frontface", "stroke_method"}
ALLOWED_REMESH_MODES = {"VOXEL", "SHARP", "SMOOTH", "BLOCKS"}
ALLOWED_DYNTOPO_DETAIL_MODES = {"RELATIVE", "CONSTANT", "BRUSH", "MANUAL"}
ALLOWED_FACE_SET_MODES = {"LOOSE_PARTS", "MATERIALS", "ASSIGN", "CLEAR"}
MAX_FACE_SET = 2_147_483_647


@mcp.tool()
def enter_sculpt_mode(object_name: str) -> dict[str, Any]:
    """Enter sculpt mode for a mesh object.

    Args:
        object_name: Name of the mesh object to sculpt.

    Returns:
        Confirmation dict with object name and mode.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("enter_sculpt_mode", {"object_name": object_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def exit_sculpt_mode() -> dict[str, Any]:
    """Exit sculpt mode and return to object mode.

    Returns:
        Confirmation dict with current mode.
    """
    conn = get_connection()
    response = conn.send_command("exit_sculpt_mode")
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_sculpt_brush(brush_type: str) -> dict[str, Any]:
    """Set the active sculpt brush.

    Args:
        brush_type: Brush type - DRAW, CLAY, CLAY_STRIPS, INFLATE, GRAB, SMOOTH,
                    FLATTEN, FILL, SCRAPE, PINCH, CREASE, BLOB, MASK,
                    MULTIRES_DISPLACEMENT_SMEAR.

    Returns:
        Confirmation dict with active brush type.
    """
    validate_enum(brush_type, ALLOWED_BRUSH_TYPES, name="brush_type")

    conn = get_connection()
    response = conn.send_command("set_sculpt_brush", {"brush_type": brush_type})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_brush_property(property: str, value: Any) -> dict[str, Any]:
    """Set a property on the active sculpt brush.

    Args:
        property: Property to set - size, strength, auto_smooth_factor, or use_frontface.
        value: Value to set. size is int (1-500), strength is float (0.0-1.0),
               auto_smooth_factor is float (0.0-1.0), use_frontface is bool.

    Returns:
        Confirmation dict with property name and new value.
    """
    validate_enum(property, ALLOWED_BRUSH_PROPERTIES, name="property")

    if property == "size":
        value = validate_numeric_range(value, min_val=1, max_val=500, name="size")
    elif property == "strength":
        value = validate_numeric_range(value, min_val=0.0, max_val=1.0, name="strength")
    elif property == "auto_smooth_factor":
        value = validate_numeric_range(value, min_val=0.0, max_val=1.0, name="auto_smooth_factor")
    elif property == "use_frontface":
        if not isinstance(value, bool):
            raise ValidationError("use_frontface must be a boolean")
    elif property == "stroke_method":
        ALLOWED_STROKE_METHODS = {
            "DOTS", "DRAG_DOT", "SPACE", "AIRBRUSH",
            "ANCHORED", "LINE", "CURVE",
        }
        validate_enum(value, ALLOWED_STROKE_METHODS, name="stroke_method")

    conn = get_connection()
    response = conn.send_command("set_brush_property", {
        "property": property,
        "value": value,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def remesh(
    object_name: str,
    voxel_size: float = 0.1,
    mode: str = "VOXEL",
) -> dict[str, Any]:
    """Remesh an object to create a clean topology.

    Args:
        object_name: Name of the mesh object to remesh.
        voxel_size: Voxel size for remeshing (smaller = more detail). Only used in VOXEL mode.
        mode: Remesh mode - VOXEL, SHARP, SMOOTH, or BLOCKS.

    Returns:
        Dict with object name and new vertex count.
    """
    object_name = validate_object_name(object_name)
    voxel_size = validate_numeric_range(voxel_size, min_val=0.001, max_val=10.0, name="voxel_size")
    validate_enum(mode, ALLOWED_REMESH_MODES, name="mode")

    conn = get_connection()
    response = conn.send_command("remesh", {
        "object_name": object_name,
        "voxel_size": voxel_size,
        "mode": mode,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_multires_modifier(
    object_name: str,
    levels: int = 2,
) -> dict[str, Any]:
    """Add a Multiresolution modifier for sculpting detail.

    Args:
        object_name: Name of the mesh object.
        levels: Number of subdivision levels to add (1-6).

    Returns:
        Dict with object name and modifier info.
    """
    object_name = validate_object_name(object_name)
    levels = validate_numeric_range(levels, min_val=1, max_val=6, name="levels")

    conn = get_connection()
    response = conn.send_command("add_multires_modifier", {
        "object_name": object_name,
        "levels": int(levels),
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_sculpt_symmetry(
    use_x: bool = True, use_y: bool = False, use_z: bool = False
) -> dict[str, Any]:
    """Set sculpt symmetry axes.

    Enables symmetrical sculpting across the specified axes. X-axis symmetry
    is the most common for character modeling.

    Args:
        use_x: Enable X-axis symmetry. Defaults to True.
        use_y: Enable Y-axis symmetry. Defaults to False.
        use_z: Enable Z-axis symmetry. Defaults to False.

    Returns:
        Confirmation dict with symmetry settings.
    """
    conn = get_connection()
    response = conn.send_command("set_sculpt_symmetry", {
        "use_x": use_x,
        "use_y": use_y,
        "use_z": use_z,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def enable_dyntopo(
    object_name: str,
    detail_size: float = 12.0,
    detail_mode: str = "RELATIVE",
) -> dict[str, Any]:
    """Enable dynamic topology (dyntopo) for adaptive sculpting resolution.

    Dyntopo adds and removes mesh detail dynamically as you sculpt,
    allowing unlimited detail where needed without uniform subdivision.

    Args:
        object_name: Name of the mesh object (must be in sculpt mode or will enter it).
        detail_size: Detail level (smaller = more detail). Range: 0.1-500.0.
        detail_mode: Detail mode. One of: RELATIVE, CONSTANT, BRUSH, MANUAL.

    Returns:
        Confirmation dict with dyntopo settings.
    """
    object_name = validate_object_name(object_name)
    detail_size = validate_numeric_range(detail_size, min_val=0.1, max_val=500.0, name="detail_size")
    validate_enum(detail_mode, ALLOWED_DYNTOPO_DETAIL_MODES, name="detail_mode")

    conn = get_connection()
    response = conn.send_command("enable_dyntopo", {
        "object_name": object_name,
        "detail_size": detail_size,
        "detail_mode": detail_mode,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _send_sculpt(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_sculpt_mask(
    object_name: str,
    value: float = 1.0,
    vertex_indices: list[int] | None = None,
    vertex_group: str | None = None,
    invert: bool = False,
    clear: bool = False,
) -> dict[str, Any]:
    """Mask part of a mesh so sculpt brushes and filters leave it alone.

    1.0 is fully protected, 0.0 is free to sculpt. Works in any mode.

    Args:
        object_name: Mesh object.
        value: Mask strength, 0.0 to 1.0.
        vertex_indices: Vertices to set; the rest keep their mask. Omit (and
            vertex_group) to set the whole mesh.
        vertex_group: Mask from a vertex group: each member gets value times
            its weight, other vertices are unmasked.
        invert: Flip the current mask (other arguments ignored).
        clear: Remove the mask entirely.

    Returns:
        Dict with how many vertices are masked (above 0) and the vertex count.
    """
    if not isinstance(invert, bool) or not isinstance(clear, bool):
        raise ValidationError("invert and clear must be true or false")
    params: dict[str, Any] = {"object_name": validate_object_name(object_name)}
    if invert or clear:
        if invert and clear:
            raise ValidationError("Use invert or clear, not both")
        if vertex_indices is not None or vertex_group is not None:
            raise ValidationError("invert and clear act on the whole mask; "
                                  "leave vertex_indices and vertex_group out")
        params["invert" if invert else "clear"] = True
        return _send_sculpt("set_sculpt_mask", params)
    if vertex_indices is not None and vertex_group is not None:
        raise ValidationError("Give vertex_indices or vertex_group, not both")
    params["value"] = float(validate_numeric_range(value, min_val=0.0, max_val=1.0,
                                                   name="value"))
    if vertex_indices is not None:
        params["vertex_indices"] = _validate_indices(vertex_indices)
    if vertex_group is not None:
        params["vertex_group"] = validate_object_name(vertex_group)
    return _send_sculpt("set_sculpt_mask", params)


@mcp.tool()
def set_face_sets(
    object_name: str,
    mode: str,
    face_indices: list[int] | None = None,
    face_set: int = 1,
) -> dict[str, Any]:
    """Split a mesh into face sets: colored regions for sculpting one part at a time.

    In sculpt mode, face sets can be hidden or isolated, and brushes and
    automasking can stay within one set.

    Args:
        object_name: Mesh object.
        mode: LOOSE_PARTS (one set per separate piece), MATERIALS (one set per
            material slot), ASSIGN (face_indices into face_set), CLEAR.
        face_indices: ASSIGN only: the faces to change.
        face_set: ASSIGN only: set number, 1 or more.

    Returns:
        Dict with the number of distinct face sets.
    """
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "mode": validate_enum(mode, ALLOWED_FACE_SET_MODES, name="mode"),
    }
    if mode == "ASSIGN":
        if face_indices is None:
            raise ValidationError("ASSIGN needs face_indices")
        params["face_indices"] = _validate_indices(face_indices)
        params["face_set"] = validate_int(face_set, 1, MAX_FACE_SET, name="face_set")
    return _send_sculpt("set_face_sets", params)
