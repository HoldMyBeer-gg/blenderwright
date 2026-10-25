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

_SETTING_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
ALLOWED_INTERFACE_TYPES = {
    "GEOMETRY", "FLOAT", "INT", "BOOLEAN", "VECTOR", "COLOR", "ROTATION", "STRING",
    "OBJECT", "COLLECTION", "MATERIAL",
}
GROUP_NODES = {"Group Input", "Group Output"}
MAX_SPEC_NODES = 200
MAX_SPEC_LINKS = 500
MAX_SPEC_SOCKETS = 50
MAX_TEXT = 64
MAX_COORD = 100_000.0

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


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_TEXT \
            or not value.isprintable():
        raise ValidationError(f"{what} must be printable text, 1 to {MAX_TEXT} characters")
    return value


def _plain_value(value: Any, what: str) -> Any:
    """A socket or setting value: bool, finite number, short text, or 2 to 4 numbers."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValidationError(f"{what} must be a finite number")
        return value
    if isinstance(value, str):
        return _text(value, what)
    if isinstance(value, list) and 2 <= len(value) <= 4 and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and v == v
            and abs(v) != float("inf") for v in value):
        return value
    raise ValidationError(f"{what} must be a number, true/false, short text or 2-4 numbers")


def _socket_ref(ref: Any, what: str) -> str | int:
    if isinstance(ref, int) and not isinstance(ref, bool):
        if ref < 0:
            raise ValidationError(f"{what} index must be 0 or more")
        return ref
    return _text(ref, what)


def _interface_items(items: Any, what: str) -> list[dict[str, Any]]:
    if not isinstance(items, list) or len(items) > MAX_SPEC_SOCKETS:
        raise ValidationError(f"{what} must be a list of at most {MAX_SPEC_SOCKETS} sockets")
    clean = []
    for item in items:
        if not isinstance(item, dict) or not set(item) <= {"name", "type", "default",
                                                           "min", "max"}:
            raise ValidationError(f"Each of {what} is {{name, type, default?, min?, max?}}")
        entry = {"name": _text(item.get("name"), f"{what} name"),
                 "type": validate_enum(item.get("type"), ALLOWED_INTERFACE_TYPES,
                                       name=f"{what} type")}
        for key in ("default", "min", "max"):
            if key in item:
                value = _plain_value(item[key], f"{what} {key}")
                if key != "default" and not isinstance(value, (int, float)):
                    raise ValidationError(f"{what} {key} must be a number")
                if key == "default" and isinstance(value, str) and entry["type"] not in (
                        "STRING", "OBJECT", "COLLECTION", "MATERIAL"):
                    raise ValidationError(f"{what} default for {entry['type']} must not be text")
                entry[key] = value
        clean.append(entry)
    return clean


def _validate_spec(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict) or not set(spec) <= {"inputs", "outputs", "nodes", "links"}:
        raise ValidationError("spec is an object with inputs, outputs, nodes and links")
    nodes = spec.get("nodes", [])
    links = spec.get("links", [])
    if not isinstance(nodes, list) or len(nodes) > MAX_SPEC_NODES:
        raise ValidationError(f"nodes must be a list of at most {MAX_SPEC_NODES}")
    if not isinstance(links, list) or len(links) > MAX_SPEC_LINKS:
        raise ValidationError(f"links must be a list of at most {MAX_SPEC_LINKS}")

    clean_nodes, names = [], set(GROUP_NODES)
    for node in nodes:
        if not isinstance(node, dict) or not set(node) <= {"name", "type", "location",
                                                           "settings", "inputs", "pair_with"}:
            raise ValidationError("Each node is {name, type, location?, settings?, inputs?, "
                                  "pair_with?}")
        name = validate_object_name(node.get("name"))
        if name in names:
            raise ValidationError(f"Node name {name!r} is used twice or is reserved")
        names.add(name)
        node_type = node.get("type")
        if not isinstance(node_type, str) or not _NODE_TYPE_PATTERN.match(node_type):
            raise ValidationError(f"Node type {node_type!r} is not a node identifier, "
                                  f"e.g. GeometryNodeMeshGrid or ShaderNodeMath")
        entry: dict[str, Any] = {"name": name, "type": node_type}
        if "pair_with" in node:
            entry["pair_with"] = node["pair_with"]
        if "location" in node:
            entry["location"] = [float(v) for v in validate_vector(node["location"], size=2,
                                                                   name="location")]
            if any(abs(v) > MAX_COORD for v in entry["location"]):
                raise ValidationError("location is out of range")
        settings = node.get("settings", {})
        if not isinstance(settings, dict):
            raise ValidationError("settings must be an object")
        for key, value in settings.items():
            if not isinstance(key, str) or not _SETTING_PATTERN.match(key):
                raise ValidationError(f"Setting {key!r} must be a lowercase name like operation")
            if not isinstance(value, (bool, int, float, str)):
                raise ValidationError(f"Setting {key!r} must be a single value")
            _plain_value(value, f"setting {key}")
        entry["settings"] = dict(settings)
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            raise ValidationError("inputs must be an object of socket to value")
        entry["inputs"] = {}
        for key, value in inputs.items():
            ref = _socket_ref(int(key) if isinstance(key, str) and key.isdigit() else key,
                              "input socket")
            entry["inputs"][str(ref)] = _plain_value(value, f"input {key!r}")
        clean_nodes.append(entry)

    spec_names = {entry["name"] for entry in clean_nodes}
    for entry in clean_nodes:
        partner = entry.get("pair_with")
        if partner is not None and (not isinstance(partner, str) or partner == entry["name"]
                                    or partner not in spec_names):
            raise ValidationError(f"{entry['name']}: pair_with must name the zone's output "
                                  f"node in this spec")

    clean_links = []
    for link in links:
        if not isinstance(link, list) or len(link) != 4:
            raise ValidationError("Each link is [from_node, from_socket, to_node, to_socket]")
        from_node, from_socket, to_node, to_socket = link
        for node_name in (from_node, to_node):
            if node_name not in names:
                raise ValidationError(f"Link refers to unknown node {node_name!r}")
        clean_links.append([from_node, _socket_ref(from_socket, "from_socket"),
                            to_node, _socket_ref(to_socket, "to_socket")])
    return {"inputs": _interface_items(spec.get("inputs", []), "inputs"),
            "outputs": _interface_items(spec.get("outputs", []), "outputs"),
            "nodes": clean_nodes, "links": clean_links}


@mcp.tool()
def build_geometry_nodes(
    object_name: str,
    spec: dict[str, Any],
    modifier_name: str = "GeometryNodes",
) -> dict[str, Any]:
    """Build a whole geometry node graph on an object in one call.

    The graph is built in a new node group and only put on the modifier if
    every step works; on any error nothing changes. The group always gets a
    Geometry input and output, wired through nodes named "Group Input" and
    "Group Output". Read a graph back with get_geometry_node_tree.

    Args:
        object_name: Object to put the graph on (the modifier is created if needed).
        spec: {
            "inputs": [{"name", "type", "default"?, "min"?, "max"?}]  extra group
                inputs, shown on the modifier. type: FLOAT, INT, BOOLEAN, VECTOR,
                COLOR, ROTATION, STRING, OBJECT, COLLECTION, MATERIAL, GEOMETRY.
            "outputs": same shape, extra group outputs.
            "nodes": [{"name", "type", "location"?: [x, y],
                       "pair_with"?: zone output node name, on a zone's input node
                           (GeometryNodeSimulationInput, GeometryNodeRepeatInput,
                           GeometryNodeForeachGeometryElementInput),
                       "settings"?: {"operation": "SINE"},  node options
                       "inputs"?: {"Size X": 4, "Offset": [0, 0, 1]}}]  socket values;
                       a socket is a name, identifier (Value_001) or index;
                       object/collection/material sockets take a name.
            "links": [[from_node, from_socket, to_node, to_socket]]
        }
            Example: a wavy grid
            {"inputs": [{"name": "Size", "type": "FLOAT", "default": 4}],
             "nodes": [{"name": "grid", "type": "GeometryNodeMeshGrid",
                        "inputs": {"Vertices X": 40, "Vertices Y": 40}},
                       {"name": "pos", "type": "GeometryNodeInputPosition"},
                       {"name": "xyz", "type": "ShaderNodeSeparateXYZ"},
                       {"name": "sine", "type": "ShaderNodeMath",
                        "settings": {"operation": "SINE"}},
                       {"name": "up", "type": "ShaderNodeCombineXYZ"},
                       {"name": "move", "type": "GeometryNodeSetPosition"}],
             "links": [["Group Input", "Size", "grid", "Size X"],
                       ["Group Input", "Size", "grid", "Size Y"],
                       ["pos", 0, "xyz", 0], ["xyz", "X", "sine", 0],
                       ["sine", 0, "up", "Z"], ["grid", "Mesh", "move", "Geometry"],
                       ["up", 0, "move", "Offset"],
                       ["move", "Geometry", "Group Output", "Geometry"]]}
        modifier_name: Geometry nodes modifier to use or create.

    Returns:
        Dict with the modifier, the node group, and the node and link counts.
    """
    return _send_gn("build_geometry_nodes", {
        "object_name": validate_object_name(object_name),
        "modifier_name": validate_new_name(modifier_name),
        "spec": _validate_spec(spec),
    })


@mcp.tool()
def get_geometry_node_tree(object_name: str, modifier_name: str) -> dict[str, Any]:
    """Read a geometry nodes modifier's graph: group interface, nodes with their
    settings and unlinked input values, and links.

    Args:
        object_name: Object with the modifier.
        modifier_name: Geometry nodes modifier.

    Returns:
        Dict with interface, nodes and links, in the shape build_geometry_nodes takes.
    """
    return _send_gn("get_geometry_node_tree", {
        "object_name": validate_object_name(object_name),
        "modifier_name": validate_object_name(modifier_name),
    })


def _send_gn(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
