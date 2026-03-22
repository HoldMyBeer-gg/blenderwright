"""MCP tools for Blender geometry nodes operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import validate_object_name, validate_vector, ValidationError


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
    name = validate_object_name(name)

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
