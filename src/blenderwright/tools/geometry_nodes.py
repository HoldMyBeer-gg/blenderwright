"""MCP tools for Blender geometry nodes operations."""

from typing import Any

import re

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_enum,
    validate_new_name,
    validate_object_name,
    validate_socket_settings,
    validate_vector,
    ValidationError,
)


_NODE_TYPE_PATTERN = re.compile(r"^(Geometry|Function|Shader)Node[A-Z][A-Za-z0-9]*$")

# Node-group modifiers bundled in Blender 5.2's Essentials library
ALLOWED_ESSENTIALS_MODIFIERS = {
    "array", "scatter_on_surface", "instance_on_elements", "randomize_transforms",
    "curve_to_tube", "geometry_input", "smooth_by_angle", "capture_rest_geometry",
}


@mcp.tool()
def create_geometry_nodes(
    object_name: str,
    name: str = "GeometryNodes",
) -> dict[str, Any]:
    """Create a Geometry Nodes modifier on an object.

    Args:
        object_name: Name of the object to add the modifier to.
        name: Name for the geometry nodes modifier. Defaults to "GeometryNodes".

    Returns:
        Dict with modifier name and node group name.
    """
    object_name = validate_object_name(object_name)
    name = validate_new_name(name)

    conn = get_connection()
    response = conn.send_command("create_geometry_nodes", {
        "object_name": object_name,
        "name": name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_geometry_node(
    modifier_name: str,
    node_type: str,
    location: list[float] | tuple[float, ...] = (0, 0),
) -> dict[str, Any]:
    """Add a node to a geometry nodes modifier's node group.

    Args:
        modifier_name: Name of the geometry nodes modifier (used to find the node group).
        node_type: Blender node type identifier, e.g. GeometryNodeMeshCube,
                   GeometryNodeSetPosition, GeometryNodeTransform,
                   ShaderNodeMath, GeometryNodeJoinGeometry, etc.
        location: XY position for the node in the node editor. Defaults to (0, 0).

    Returns:
        Dict with the created node's name and type.
    """
    modifier_name = validate_object_name(modifier_name)
    # The addon makes the real decision by asking bpy.types, which cannot go
    # stale across Blender versions. This only rejects shapes that could never
    # be a node identifier, so an obvious typo costs no round trip.
    if not isinstance(node_type, str) or not _NODE_TYPE_PATTERN.match(node_type):
        raise ValidationError(
            f"node_type {node_type!r} is not a Blender node identifier. They "
            f"look like GeometryNodeMeshCube or FunctionNodeInputVector: a "
            f"GeometryNode, FunctionNode or ShaderNode prefix followed by the "
            f"node name in CamelCase, no spaces."
        )
    if not node_type or not isinstance(node_type, str):
        raise ValidationError("node_type must be a non-empty string")
    location = validate_vector(location, size=2, name="location")

    conn = get_connection()
    response = conn.send_command("add_geometry_node", {
        "modifier_name": modifier_name,
        "node_type": node_type,
        "location": list(location),
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def connect_geometry_nodes(
    modifier_name: str,
    from_node: str,
    from_socket: int,
    to_node: str,
    to_socket: int,
) -> dict[str, Any]:
    """Connect two nodes in a geometry nodes modifier's node group.

    Args:
        modifier_name: Name of the geometry nodes modifier.
        from_node: Name of the source node.
        from_socket: Index of the output socket on the source node.
        to_node: Name of the destination node.
        to_socket: Index of the input socket on the destination node.

    Returns:
        Confirmation dict with connection details.
    """
    modifier_name = validate_object_name(modifier_name)
    if not from_node or not isinstance(from_node, str):
        raise ValidationError("from_node must be a non-empty string")
    if not to_node or not isinstance(to_node, str):
        raise ValidationError("to_node must be a non-empty string")
    if not isinstance(from_socket, int) or from_socket < 0:
        raise ValidationError("from_socket must be a non-negative integer")
    if not isinstance(to_socket, int) or to_socket < 0:
        raise ValidationError("to_socket must be a non-negative integer")

    conn = get_connection()
    response = conn.send_command("connect_geometry_nodes", {
        "modifier_name": modifier_name,
        "from_node": from_node,
        "from_socket": from_socket,
        "to_node": to_node,
        "to_socket": to_socket,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_geometry_node_input(
    object_name: str,
    modifier_name: str,
    input_name: str,
    value: Any,
) -> dict[str, Any]:
    """Set an input value on a geometry nodes modifier.

    Args:
        object_name: Name of the object with the modifier.
        modifier_name: Name of the geometry nodes modifier.
        input_name: Name of the input socket to set (as shown in the modifier panel).
        value: The value to set. Type depends on the input (float, int, vector, etc.).

    Returns:
        Confirmation dict with the input name and new value.
    """
    object_name = validate_object_name(object_name)
    modifier_name = validate_object_name(modifier_name)
    if not input_name or not isinstance(input_name, str):
        raise ValidationError("input_name must be a non-empty string")

    conn = get_connection()
    response = conn.send_command("set_geometry_node_input", {
        "object_name": object_name,
        "modifier_name": modifier_name,
        "input_name": input_name,
        "value": value,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def list_geometry_node_inputs(
    object_name: str,
    modifier_name: str,
) -> list[dict[str, Any]]:
    """List all available inputs on a geometry nodes modifier.

    Args:
        object_name: Name of the object with the modifier.
        modifier_name: Name of the geometry nodes modifier.

    Returns:
        List of dicts with input name, type, and current value.
    """
    object_name = validate_object_name(object_name)
    modifier_name = validate_object_name(modifier_name)

    conn = get_connection()
    response = conn.send_command("list_geometry_node_inputs", {
        "object_name": object_name,
        "modifier_name": modifier_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_essentials_modifier(
    object_name: str,
    modifier: str,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add one of Blender's ready-made node modifiers, with its inputs set.

    These are full node setups that would take dozens of add_geometry_node
    calls. Change inputs later with set_geometry_node_input.

    Args:
        object_name: Object to add the modifier to.
        modifier: One of:
            array (Shape Line/Circle/Curve, Count, Distance, Offset, Rotation,
                Scale: a richer Array than the classic modifier),
            scatter_on_surface (scatter an Object or Collection over a mesh:
                Object, Density Method Density/Amount, Amount, Density,
                Minimum Distance, Seed, Realize Instances),
            instance_on_elements (Instance On Points/Edges/Faces, Object,
                Collection, Align Rotation, Scale),
            randomize_transforms (jitter instances: Offset, Rotation, Scale,
                Seed),
            curve_to_tube (turn a curve into a pipe with caps and UVs: Scale,
                Profile Resolution, Caps, Shade Smooth),
            geometry_input (bring in another Object or Collection: Input
                Type, Object, Collection, As Instance, Replace Original),
            smooth_by_angle (Angle in radians, Ignore Sharpness),
            capture_rest_geometry (store rest positions for later effects).
        settings: Input name to value, e.g. {"Object": "Rock", "Amount": 200}.
            Object and Collection inputs take the name of an existing one;
            menus take the option name as shown in Blender.

    Returns:
        Dict with the modifier name and every input with its value.
    """
    params = {
        "object_name": validate_object_name(object_name),
        "modifier": validate_enum(modifier, ALLOWED_ESSENTIALS_MODIFIERS, name="modifier"),
        "settings": validate_socket_settings(settings or {}),
    }
    conn = get_connection()
    response = conn.send_command("add_essentials_modifier", params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
