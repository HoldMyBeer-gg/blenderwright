"""MCP tools for mesh modeling operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
    validate_enum,
    validate_numeric_range,
    ValidationError,
)

# Allowed modifier types
ALLOWED_MODIFIER_TYPES = {
    "SUBSURF", "MIRROR", "ARRAY", "BEVEL", "BOOLEAN", "SOLIDIFY",
    "DECIMATE", "REMESH", "WIREFRAME", "SHRINKWRAP", "SMOOTH",
    "EDGE_SPLIT", "TRIANGULATE", "WEIGHTED_NORMAL", "SIMPLE_DEFORM",
    "LATTICE", "CURVE", "CAST", "WAVE", "DISPLACE", "SCREW", "SKIN",
    "MASK", "WELD", "CORRECTIVE_SMOOTH", "LAPLACIAN_SMOOTH",
    "SURFACE_DEFORM", "MESH_DEFORM", "HOOK",
}

# Allowed boolean operations
ALLOWED_BOOLEAN_OPS = {"UNION", "DIFFERENCE", "INTERSECT"}

# Allowed separate types
ALLOWED_SEPARATE_TYPES = {"SELECTED", "MATERIAL", "LOOSE"}

# Allowed profile shapes for bridge
ALLOWED_PROFILE_SHAPES = {"SMOOTH", "SPHERE", "ROOT", "INVERSE_SQUARE", "SHARP", "LINEAR"}


@mcp.tool()
def add_modifier(object_name: str, modifier_type: str, name: str = "") -> dict[str, Any]:
    """Add a modifier to a mesh object (non-destructive workflow).

    TIP: For BOOLEAN type, consider using booltool_auto_union/difference/intersect/slice
    instead — they apply the boolean immediately and handle cutter cleanup automatically.
    Only use add_modifier with BOOLEAN when you want a non-destructive modifier stack.

    Args:
        object_name: Name of the object to add the modifier to.
        modifier_type: Type of modifier. Must be one of: SUBSURF, MIRROR, ARRAY, BEVEL,
            BOOLEAN, SOLIDIFY, DECIMATE, REMESH, WIREFRAME, SHRINKWRAP, SMOOTH,
            EDGE_SPLIT, TRIANGULATE, WEIGHTED_NORMAL, SIMPLE_DEFORM, LATTICE, CURVE,
            CAST, WAVE, DISPLACE, SCREW, SKIN, MASK, WELD, CORRECTIVE_SMOOTH,
            LAPLACIAN_SMOOTH, SURFACE_DEFORM, MESH_DEFORM, HOOK.
        name: Optional custom name for the modifier.

    Returns:
        Confirmation dict with modifier details.
    """
    object_name = validate_object_name(object_name)
    validate_enum(modifier_type, ALLOWED_MODIFIER_TYPES, name="modifier_type")
    if name:
        name = validate_object_name(name)

    conn = get_connection()
    response = conn.send_command("add_modifier", {
        "object_name": object_name,
        "modifier_type": modifier_type,
        "name": name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def remove_modifier(object_name: str, modifier_name: str) -> dict[str, Any]:
    """Remove a modifier from an object.

    Args:
        object_name: Name of the object.
        modifier_name: Name of the modifier to remove.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    modifier_name = validate_object_name(modifier_name)

    conn = get_connection()
    response = conn.send_command("remove_modifier", {
        "object_name": object_name,
        "modifier_name": modifier_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def apply_modifier(object_name: str, modifier_name: str) -> dict[str, Any]:
    """Apply a modifier to an object, making its effect permanent.

    Args:
        object_name: Name of the object.
        modifier_name: Name of the modifier to apply.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    modifier_name = validate_object_name(modifier_name)

    conn = get_connection()
    response = conn.send_command("apply_modifier", {
        "object_name": object_name,
        "modifier_name": modifier_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_modifier_property(
    object_name: str, modifier_name: str, property: str, value: Any
) -> dict[str, Any]:
    """Set a property on a modifier (e.g., levels, count, offset, angle).

    Args:
        object_name: Name of the object.
        modifier_name: Name of the modifier.
        property: The modifier property to set (e.g., 'levels', 'count', 'width',
            'segments', 'angle', 'offset', 'ratio', 'iterations').
        value: The value to set.

    Returns:
        Confirmation dict with updated property.
    """
    object_name = validate_object_name(object_name)
    modifier_name = validate_object_name(modifier_name)
    if not property or not isinstance(property, str):
        raise ValidationError("property must be a non-empty string")

    conn = get_connection()
    response = conn.send_command("set_modifier_property", {
        "object_name": object_name,
        "modifier_name": modifier_name,
        "property": property,
        "value": value,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def boolean_operation(
    object_name: str, target_name: str, operation: str = "DIFFERENCE"
) -> dict[str, Any]:
    """Perform a boolean operation between two objects using a modifier.

    NOTE: For destructive booleans, prefer the booltool_auto_* tools instead
    (booltool_auto_union, booltool_auto_difference, booltool_auto_intersect,
    booltool_auto_slice). They handle selection and cutter cleanup automatically.
    Use this tool only when you need a non-destructive boolean modifier workflow.

    Args:
        object_name: Name of the object to apply the boolean to.
        target_name: Name of the target/cutter object.
        operation: Boolean operation type. One of: UNION, DIFFERENCE, INTERSECT.

    Returns:
        Confirmation dict with operation details.
    """
    object_name = validate_object_name(object_name)
    target_name = validate_object_name(target_name)
    validate_enum(operation, ALLOWED_BOOLEAN_OPS, name="operation")

    conn = get_connection()
    response = conn.send_command("boolean_operation", {
        "object_name": object_name,
        "target_name": target_name,
        "operation": operation,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def subdivide_mesh(object_name: str, cuts: int = 1) -> dict[str, Any]:
    """Subdivide a mesh.

    Args:
        object_name: Name of the mesh object to subdivide.
        cuts: Number of cuts per edge. Range: 1-100.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(cuts, min_val=1, max_val=100, name="cuts")

    conn = get_connection()
    response = conn.send_command("subdivide_mesh", {
        "object_name": object_name,
        "cuts": cuts,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def extrude_faces(object_name: str, offset: float = 1.0) -> dict[str, Any]:
    """Extrude all faces of a mesh along their normals.

    Args:
        object_name: Name of the mesh object.
        offset: Extrusion distance along face normals.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("extrude_faces", {
        "object_name": object_name,
        "offset": offset,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def bevel_edges(object_name: str, width: float = 0.1, segments: int = 1) -> dict[str, Any]:
    """Bevel all edges of a mesh.

    Args:
        object_name: Name of the mesh object.
        width: Bevel width.
        segments: Number of bevel segments. Range: 1-100.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(width, min_val=0.0, name="width")
    validate_numeric_range(segments, min_val=1, max_val=100, name="segments")

    conn = get_connection()
    response = conn.send_command("bevel_edges", {
        "object_name": object_name,
        "width": width,
        "segments": segments,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def loop_cut(object_name: str, cuts: int = 1) -> dict[str, Any]:
    """Add loop cuts to a mesh object.

    Args:
        object_name: Name of the mesh object.
        cuts: Number of loop cuts. Range: 1-100.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(cuts, min_val=1, max_val=100, name="cuts")

    conn = get_connection()
    response = conn.send_command("loop_cut", {
        "object_name": object_name,
        "cuts": cuts,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_smooth_shading(object_name: str, smooth: bool = True) -> dict[str, Any]:
    """Set smooth or flat shading on an object.

    TIP: For production use, prefer shade_auto_smooth which provides angle-based
    auto-smooth shading — it gives better results on hard-surface models by only
    smoothing faces within the angle threshold.

    Args:
        object_name: Name of the mesh object.
        smooth: True for smooth shading, False for flat shading.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("set_smooth_shading", {
        "object_name": object_name,
        "smooth": smooth,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def merge_vertices(object_name: str, threshold: float = 0.0001) -> dict[str, Any]:
    """Merge vertices by distance.

    Args:
        object_name: Name of the mesh object.
        threshold: Maximum distance between vertices to merge. Range: 0.0-10.0.

    Returns:
        Confirmation dict with number of removed vertices.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(threshold, min_val=0.0, max_val=10.0, name="threshold")

    conn = get_connection()
    response = conn.send_command("merge_vertices", {
        "object_name": object_name,
        "threshold": threshold,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def separate_mesh(object_name: str, type: str = "SELECTED") -> dict[str, Any]:
    """Separate a mesh into parts.

    Args:
        object_name: Name of the mesh object.
        type: Separation method. One of: SELECTED, MATERIAL, LOOSE.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_enum(type, ALLOWED_SEPARATE_TYPES, name="type")

    conn = get_connection()
    response = conn.send_command("separate_mesh", {
        "object_name": object_name,
        "type": type,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def bridge_edge_loops(
    object_name: str, segments: int = 1, profile_shape_factor: float = 0.0
) -> dict[str, Any]:
    """Bridge two edge loops to create connecting geometry.

    Select two edge loops on a mesh before calling this. The operation creates
    faces connecting the two loops, useful for connecting separate mesh parts,
    creating holes between surfaces, or building tube-like geometry.

    Args:
        object_name: Name of the mesh object with selected edge loops.
        segments: Number of segments in the bridge. Range: 1-1000.
        profile_shape_factor: Shape of the bridge profile. Range: -1.0 to 1.0.
            0.0 is straight, positive values bulge outward, negative inward.

    Returns:
        Confirmation dict with bridge details.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(segments, min_val=1, max_val=1000, name="segments")
    validate_numeric_range(
        profile_shape_factor, min_val=-1.0, max_val=1.0, name="profile_shape_factor"
    )

    conn = get_connection()
    response = conn.send_command("bridge_edge_loops", {
        "object_name": object_name,
        "segments": segments,
        "profile_shape_factor": profile_shape_factor,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
