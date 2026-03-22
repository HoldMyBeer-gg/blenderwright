"""MCP tools for Blender object operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
    validate_enum,
    validate_numeric_range,
    validate_vector,
    ValidationError,
)

# Allowed primitive types for object creation
ALLOWED_OBJECT_TYPES = {
    "CUBE",
    "SPHERE",
    "UV_SPHERE",
    "ICO_SPHERE",
    "CYLINDER",
    "CONE",
    "TORUS",
    "PLANE",
    "CIRCLE",
    "MONKEY",
    "EMPTY",
}

# Allowed object type filters
ALLOWED_TYPE_FILTERS = {
    "",
    "MESH",
    "CURVE",
    "SURFACE",
    "META",
    "FONT",
    "ARMATURE",
    "LATTICE",
    "EMPTY",
    "GPENCIL",
    "CAMERA",
    "LIGHT",
    "SPEAKER",
    "LIGHT_PROBE",
    "VOLUME",
}

ALLOWED_ORIGIN_TYPES = {
    "ORIGIN_GEOMETRY", "ORIGIN_CURSOR", "ORIGIN_CENTER_OF_MASS",
    "ORIGIN_CENTER_OF_VOLUME", "GEOMETRY_ORIGIN",
}

ALLOWED_CONVERT_TARGETS = {
    "MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD", "GPENCIL",
}


@mcp.tool()
def create_object(
    type: str,
    name: str = "",
    location: list[float] | tuple[float, ...] = (0, 0, 0),
    rotation: list[float] | tuple[float, ...] = (0, 0, 0),
    scale: list[float] | tuple[float, ...] = (1, 1, 1),
) -> dict[str, Any]:
    """Create a primitive object in the scene.

    Args:
        type: Primitive type. One of: CUBE, SPHERE, UV_SPHERE, ICO_SPHERE, CYLINDER,
              CONE, TORUS, PLANE, CIRCLE, MONKEY, EMPTY.
        name: Optional name for the object. Auto-generated if empty.
        location: XYZ position as a 3-element list/tuple. Defaults to origin.
        rotation: XYZ Euler rotation in radians as a 3-element list/tuple.
        scale: XYZ scale as a 3-element list/tuple. Defaults to (1,1,1).

    Returns:
        Dict with the created object's name, type, and location.
    """
    validate_enum(type, ALLOWED_OBJECT_TYPES, name="type")
    if name:
        name = validate_object_name(name)
    location = validate_vector(location, size=3, name="location")
    rotation = validate_vector(rotation, size=3, name="rotation")
    scale = validate_vector(scale, size=3, name="scale")

    conn = get_connection()
    response = conn.send_command("create_object", {
        "type": type,
        "name": name,
        "location": list(location),
        "rotation": list(rotation),
        "scale": list(scale),
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def delete_object(name: str) -> dict[str, Any]:
    """Delete an object from the scene by name.

    Args:
        name: Name of the object to delete.

    Returns:
        Confirmation dict.
    """
    name = validate_object_name(name)
    conn = get_connection()
    response = conn.send_command("delete_object", {"name": name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def duplicate_object(name: str, linked: bool = False) -> dict[str, Any]:
    """Duplicate an object.

    Args:
        name: Name of the object to duplicate.
        linked: If True, create a linked duplicate (shares mesh data). Defaults to False.

    Returns:
        Dict with the new object's name.
    """
    name = validate_object_name(name)
    conn = get_connection()
    response = conn.send_command("duplicate_object", {"name": name, "linked": linked})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def rename_object(old_name: str, new_name: str) -> dict[str, Any]:
    """Rename an object.

    Args:
        old_name: Current name of the object.
        new_name: New name for the object.

    Returns:
        Dict with old and new names.
    """
    old_name = validate_object_name(old_name)
    new_name = validate_object_name(new_name)
    conn = get_connection()
    response = conn.send_command("rename_object", {"old_name": old_name, "new_name": new_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def select_objects(names: list[str], deselect_others: bool = True) -> dict[str, Any]:
    """Select objects by name.

    Args:
        names: List of object names to select.
        deselect_others: If True, deselect all other objects first. Defaults to True.

    Returns:
        Dict with list of selected object names.
    """
    validated_names = [validate_object_name(n) for n in names]
    conn = get_connection()
    response = conn.send_command("select_objects", {
        "names": validated_names,
        "deselect_others": deselect_others,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def get_object_info(name: str) -> dict[str, Any]:
    """Get detailed information about an object.

    Args:
        name: Name of the object.

    Returns:
        Dict with type, location, rotation, scale, modifiers, materials,
        parent, children, and visibility info.
    """
    name = validate_object_name(name)
    conn = get_connection()
    response = conn.send_command("get_object_info", {"name": name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def list_objects(type_filter: str = "") -> list[dict[str, Any]]:
    """List all objects in the scene, optionally filtered by type.

    Args:
        type_filter: Filter by object type (e.g., MESH, LIGHT, CAMERA, EMPTY).
                     Empty string returns all objects.

    Returns:
        List of dicts with object name, type, and location.
    """
    if type_filter:
        validate_enum(type_filter, ALLOWED_TYPE_FILTERS, name="type_filter")
    conn = get_connection()
    response = conn.send_command("list_objects", {"type_filter": type_filter})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_object_visibility(
    name: str,
    visible: bool,
    viewport: bool = True,
    render: bool = True,
) -> dict[str, Any]:
    """Set object visibility in viewport and/or render.

    Args:
        name: Name of the object.
        visible: Whether the object should be visible.
        viewport: Apply visibility change to viewport. Defaults to True.
        render: Apply visibility change to render. Defaults to True.

    Returns:
        Confirmation dict with visibility state.
    """
    name = validate_object_name(name)
    conn = get_connection()
    response = conn.send_command("set_object_visibility", {
        "name": name,
        "visible": visible,
        "viewport": viewport,
        "render": render,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def parent_objects(child: str, parent: str) -> dict[str, Any]:
    """Set parent-child relationship between two objects.

    Args:
        child: Name of the child object.
        parent: Name of the parent object.

    Returns:
        Confirmation dict.
    """
    child = validate_object_name(child)
    parent = validate_object_name(parent)
    conn = get_connection()
    response = conn.send_command("parent_objects", {"child": child, "parent": parent})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def join_objects(names: list[str]) -> dict[str, Any]:
    """Join multiple mesh objects into one (keeps all geometry as-is).

    This merges objects into a single datablock without modifying geometry.
    The meshes remain separate inside the object (no boolean merge).

    TIP: If you want to truly fuse overlapping meshes into one solid shape,
    use booltool_auto_union instead — it performs a boolean union that merges
    the geometry and removes internal faces.

    Args:
        names: List of object names to join. The first name becomes the active object.

    Returns:
        Dict with the resulting joined object name.
    """
    if len(names) < 2:
        raise ValidationError("At least 2 objects are required to join")
    validated_names = [validate_object_name(n) for n in names]
    conn = get_connection()
    response = conn.send_command("join_objects", {"names": validated_names})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_origin(object_name: str, type: str = "ORIGIN_GEOMETRY") -> dict[str, Any]:
    """Set the origin point of an object.

    Args:
        object_name: Name of the object.
        type: Origin type. One of: ORIGIN_GEOMETRY, ORIGIN_CURSOR,
              ORIGIN_CENTER_OF_MASS, ORIGIN_CENTER_OF_VOLUME, GEOMETRY_ORIGIN.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_enum(type, ALLOWED_ORIGIN_TYPES, name="type")

    conn = get_connection()
    response = conn.send_command("set_origin", {
        "object_name": object_name,
        "type": type,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def convert_object(object_name: str, target: str = "MESH") -> dict[str, Any]:
    """Convert an object to a different type.

    Args:
        object_name: Name of the object to convert.
        target: Target type. One of: MESH, CURVE, SURFACE, META, FONT,
                CURVES, POINTCLOUD, GPENCIL.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_enum(target, ALLOWED_CONVERT_TARGETS, name="target")

    conn = get_connection()
    response = conn.send_command("convert_object", {
        "object_name": object_name,
        "target": target,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def shade_auto_smooth(object_name: str, angle: float = 0.523599) -> dict[str, Any]:
    """Apply angle-based auto-smooth shading to an object.

    Smooths faces only where the angle between adjacent face normals is
    below the given threshold, giving clean results on hard-surface models.

    Args:
        object_name: Name of the mesh object.
        angle: Auto-smooth angle threshold in radians (0.0 to pi). Defaults
               to ~30 degrees (0.523599 rad).

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(angle, min_val=0.0, max_val=3.14159, name="angle")

    conn = get_connection()
    response = conn.send_command("shade_auto_smooth", {
        "object_name": object_name,
        "angle": angle,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def make_single_user(object_name: str, object: bool = True, data: bool = True) -> dict[str, Any]:
    """Make an object's data single-user (unlink shared datablocks).

    Args:
        object_name: Name of the object.
        object: Make the object single-user. Defaults to True.
        data: Make the object data (e.g., mesh) single-user. Defaults to True.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("make_single_user", {
        "object_name": object_name,
        "object": object,
        "data": data,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
