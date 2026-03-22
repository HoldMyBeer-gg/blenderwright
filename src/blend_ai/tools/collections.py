"""MCP tools for Blender collection management."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import validate_object_name, ValidationError


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
    name = validate_object_name(name)
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
    name: str,
    visible: bool,
    viewport: bool = True,
    render: bool = True,
) -> dict[str, Any]:
    """Set collection visibility in viewport and/or render.

    Args:
        name: Name of the collection.
        visible: Whether the collection should be visible.
        viewport: Apply visibility change to viewport. Defaults to True.
        render: Apply visibility change to render. Defaults to True.

    Returns:
        Confirmation dict with visibility state.
    """
    name = validate_object_name(name)

    conn = get_connection()
    response = conn.send_command("set_collection_visibility", {
        "name": name,
        "visible": visible,
        "viewport": viewport,
        "render": render,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def delete_collection(
    name: str,
    delete_objects: bool = False,
) -> dict[str, Any]:
    """Delete a collection.

    Args:
        name: Name of the collection to delete.
        delete_objects: If True, also delete all objects in the collection.
                       If False, objects are unlinked but kept in the scene.

    Returns:
        Confirmation dict.
    """
    name = validate_object_name(name)

    conn = get_connection()
    response = conn.send_command("delete_collection", {
        "name": name,
        "delete_objects": delete_objects,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
