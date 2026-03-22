"""MCP tools for Blender Bool Tool addon operations.

Uses the bundled Bool Tool addon (object_boolean_tools) which provides
auto boolean operations that handle cutter cleanup automatically.
"""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import validate_object_name


@mcp.tool()
def booltool_auto_union(object_name: str, target_name: str) -> dict[str, Any]:
    """Auto boolean union: merge two mesh objects into one.

    The target object is consumed and joined into the main object.
    This is useful for permanently joining meshes so parts don't
    float away from their bodies.

    Requires the Bool Tool addon (bundled with Blender, enabled automatically).

    Args:
        object_name: Name of the main object to keep.
        target_name: Name of the object to merge into the main object.

    Returns:
        Confirmation dict with operation details.
    """
    object_name = validate_object_name(object_name)
    target_name = validate_object_name(target_name)

    conn = get_connection()
    response = conn.send_command("booltool_auto_union", {
        "object_name": object_name,
        "target_name": target_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def booltool_auto_difference(object_name: str, target_name: str) -> dict[str, Any]:
    """Auto boolean difference: subtract the target object from the main object.

    The target object is used as a cutter and removed after the operation.

    Requires the Bool Tool addon (bundled with Blender, enabled automatically).

    Args:
        object_name: Name of the object to cut from.
        target_name: Name of the cutter object (will be removed).

    Returns:
        Confirmation dict with operation details.
    """
    object_name = validate_object_name(object_name)
    target_name = validate_object_name(target_name)

    conn = get_connection()
    response = conn.send_command("booltool_auto_difference", {
        "object_name": object_name,
        "target_name": target_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def booltool_auto_intersect(object_name: str, target_name: str) -> dict[str, Any]:
    """Auto boolean intersect: keep only the overlapping volume of two objects.

    The target object is removed after the operation.

    Requires the Bool Tool addon (bundled with Blender, enabled automatically).

    Args:
        object_name: Name of the main object.
        target_name: Name of the intersecting object (will be removed).

    Returns:
        Confirmation dict with operation details.
    """
    object_name = validate_object_name(object_name)
    target_name = validate_object_name(target_name)

    conn = get_connection()
    response = conn.send_command("booltool_auto_intersect", {
        "object_name": object_name,
        "target_name": target_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def booltool_auto_slice(object_name: str, target_name: str) -> dict[str, Any]:
    """Auto boolean slice: split the main object using the target as a cutter.

    Creates two separate pieces from the intersection. The target object
    is removed after the operation.

    Requires the Bool Tool addon (bundled with Blender, enabled automatically).

    Args:
        object_name: Name of the object to slice.
        target_name: Name of the cutter object (will be removed).

    Returns:
        Confirmation dict with operation details.
    """
    object_name = validate_object_name(object_name)
    target_name = validate_object_name(target_name)

    conn = get_connection()
    response = conn.send_command("booltool_auto_slice", {
        "object_name": object_name,
        "target_name": target_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
