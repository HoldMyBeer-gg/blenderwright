"""MCP tools for boolean operations with Bool Tool support.

Uses the Bool Tool extension if installed, otherwise falls back to
native boolean modifier workflow. Warnings are surfaced to the client
when falling back.
"""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import validate_object_name


def _send_booltool_command(command: str, object_name: str, target_name: str) -> dict[str, Any]:
    """Send a booltool command and surface any warnings."""
    object_name = validate_object_name(object_name)
    target_name = validate_object_name(target_name)

    conn = get_connection()
    response = conn.send_command(command, {
        "object_name": object_name,
        "target_name": target_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")

    result = response.get("result")

    # Surface warnings from the handler so the MCP client sees them
    if isinstance(result, dict) and result.get("warning"):
        result["_warning"] = result["warning"]

    return result


@mcp.tool()
def booltool_auto_union(object_name: str, target_name: str) -> dict[str, Any]:
    """Auto boolean union: merge two mesh objects into one.

    The target object is consumed and joined into the main object.
    This is useful for permanently joining meshes so parts don't
    float away from their bodies.

    Uses Bool Tool extension if installed, otherwise falls back to native
    boolean modifier (a warning will be included in the response).

    Args:
        object_name: Name of the main object to keep.
        target_name: Name of the object to merge into the main object.

    Returns:
        Confirmation dict with operation details. May include a 'warning'
        field if Bool Tool is not available and native fallback was used.
    """
    return _send_booltool_command("booltool_auto_union", object_name, target_name)


@mcp.tool()
def booltool_auto_difference(object_name: str, target_name: str) -> dict[str, Any]:
    """Auto boolean difference: subtract the target object from the main object.

    The target object is used as a cutter and removed after the operation.

    Uses Bool Tool extension if installed, otherwise falls back to native
    boolean modifier (a warning will be included in the response).

    Args:
        object_name: Name of the object to cut from.
        target_name: Name of the cutter object (will be removed).

    Returns:
        Confirmation dict with operation details. May include a 'warning'
        field if Bool Tool is not available and native fallback was used.
    """
    return _send_booltool_command("booltool_auto_difference", object_name, target_name)


@mcp.tool()
def booltool_auto_intersect(object_name: str, target_name: str) -> dict[str, Any]:
    """Auto boolean intersect: keep only the overlapping volume of two objects.

    The target object is removed after the operation.

    Uses Bool Tool extension if installed, otherwise falls back to native
    boolean modifier (a warning will be included in the response).

    Args:
        object_name: Name of the main object.
        target_name: Name of the intersecting object (will be removed).

    Returns:
        Confirmation dict with operation details. May include a 'warning'
        field if Bool Tool is not available and native fallback was used.
    """
    return _send_booltool_command("booltool_auto_intersect", object_name, target_name)


@mcp.tool()
def booltool_auto_slice(object_name: str, target_name: str) -> dict[str, Any]:
    """Auto boolean slice: split the main object using the target as a cutter.

    Creates two separate pieces from the intersection. The target object
    is removed after the operation.

    Uses Bool Tool extension if installed, otherwise falls back to native
    boolean modifier (a warning will be included in the response).

    Args:
        object_name: Name of the object to slice.
        target_name: Name of the cutter object (will be removed).

    Returns:
        Confirmation dict with operation details. May include a 'warning'
        field if Bool Tool is not available and native fallback was used.
    """
    return _send_booltool_command("booltool_auto_slice", object_name, target_name)
