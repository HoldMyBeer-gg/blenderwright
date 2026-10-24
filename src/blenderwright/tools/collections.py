"""MCP tools for Blender collection management."""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_new_name,
    validate_numeric_range,
    validate_object_name,
    validate_vector,
    ValidationError,
)

MAX_TRANSFORM = 1_000_000.0


@mcp.tool()
def create_collection(
    name: str,
    parent: str = "",
) -> dict[str, Any]:
    """Create a new collection, optionally nested under a parent collection.

    Args:
        name: Name for the new collection.
        parent: Optional name of parent collection to nest under.
                Empty string uses the scene's root collection.

    Returns:
        Dict with the created collection's name and parent.
    """
    name = validate_new_name(name)
    if parent:
        parent = validate_object_name(parent)

    conn = get_connection()
    response = conn.send_command("create_collection", {
        "name": name,
        "parent": parent,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def move_to_collection(
    object_names: list[str],
    collection_name: str,
) -> dict[str, Any]:
    """Move objects to a collection, unlinking them from their current collections.

    Args:
        object_names: List of object names to move.
        collection_name: Name of the destination collection.

    Returns:
        Dict with the moved objects and destination collection.
    """
    if not object_names:
        raise ValidationError("object_names must not be empty")
    validated_names = [validate_object_name(n) for n in object_names]
    collection_name = validate_object_name(collection_name)

    conn = get_connection()
    response = conn.send_command("move_to_collection", {
        "object_names": validated_names,
        "collection_name": collection_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_collection_visibility(
    collection_name: str,
    visible: bool,
    viewport: bool = True,
    render: bool = True,
) -> dict[str, Any]:
    """Set collection visibility in viewport and/or render.

    Args:
        collection_name: Name of the collection.
        visible: Whether the collection should be visible.
        viewport: Apply visibility change to viewport. Defaults to True.
        render: Apply visibility change to render. Defaults to True.

    Returns:
        Confirmation dict with visibility state.
    """
    collection_name = validate_object_name(collection_name)

    conn = get_connection()
    response = conn.send_command("set_collection_visibility", {
        "name": collection_name,
        "visible": visible,
        "viewport": viewport,
        "render": render,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def delete_collection(
    collection_name: str,
    delete_objects: bool = False,
) -> dict[str, Any]:
    """Delete a collection.

    Args:
        collection_name: Name of the collection to delete.
        delete_objects: If True, also delete all objects in the collection.
                       If False, objects are unlinked but kept in the scene.

    Returns:
        Confirmation dict.
    """
    collection_name = validate_object_name(collection_name)

    conn = get_connection()
    response = conn.send_command("delete_collection", {
        "name": collection_name,
        "delete_objects": delete_objects,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _send_collection_command(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _transform(vec: Any, name: str, nonzero: bool = False) -> list[float]:
    validate_vector(vec, size=3, name=name)
    out = [float(validate_numeric_range(v, min_val=-MAX_TRANSFORM, max_val=MAX_TRANSFORM,
                                        name=name)) for v in vec]
    if nonzero and not all(out):
        raise ValidationError(f"{name} components must not be zero")
    return out


@mcp.tool()
def create_collection_instance(
    collection_name: str,
    name: str = "",
    location: list[float] | tuple[float, ...] = (0, 0, 0),
    rotation: list[float] | tuple[float, ...] = (0, 0, 0),
    scale: list[float] | tuple[float, ...] = (1, 1, 1),
) -> dict[str, Any]:
    """Place a collection as a lightweight instance (an empty that shows it).

    Instances share the collection's data, so a hundred trees cost little
    more than one, and editing the collection updates every copy. Works with
    local and linked collections.

    Args:
        collection_name: Collection to instance.
        name: Name for the instance object; empty uses the collection name.
        location: World position [x, y, z].
        rotation: Euler rotation [x, y, z] in radians.
        scale: Scale [x, y, z]; components must not be zero.

    Returns:
        Dict with the instance object's name and its collection.
    """
    return _send_collection_command("create_collection_instance", {
        "collection_name": validate_object_name(collection_name),
        "name": validate_new_name(name) if name else "",
        "location": _transform(location, "location"),
        "rotation": _transform(rotation, "rotation"),
        "scale": _transform(scale, "scale", nonzero=True),
    })


@mcp.tool()
def make_instances_real(object_name: str, keep_hierarchy: bool = False) -> dict[str, Any]:
    """Turn a collection instance into real, separately editable objects.

    Args:
        object_name: The instance object (from create_collection_instance or
            a linked collection).
        keep_hierarchy: Keep the instanced objects' parent links.

    Returns:
        Dict with the names of the new objects.
    """
    return _send_collection_command("make_instances_real", {
        "object_name": validate_object_name(object_name),
        "keep_hierarchy": bool(keep_hierarchy),
    })
