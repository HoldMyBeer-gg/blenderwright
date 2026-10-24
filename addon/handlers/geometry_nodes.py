"""Blender addon handlers for geometry nodes commands."""

import math
import os

import bpy
from .. import dispatcher

# Tool name -> node group in Blender's bundled Essentials library
ESSENTIALS_MODIFIERS = {
    "array": "Array",
    "scatter_on_surface": "Scatter on Surface",
    "instance_on_elements": "Instance on Elements",
    "randomize_transforms": "Randomize Transforms",
    "curve_to_tube": "Curve to Tube",
    "geometry_input": "Geometry Input",
    "smooth_by_angle": "Smooth by Angle",
    "capture_rest_geometry": "Capture Rest Geometry",
}
ESSENTIALS_GN_FILE = os.path.join("nodes", "geometry_nodes_essentials.blend")

# Socket types whose value is a data-block looked up by name
ID_SOCKETS = {
    "NodeSocketObject": "objects",
    "NodeSocketCollection": "collections",
    "NodeSocketMaterial": "materials",
}
TEXT_SOCKETS = {"NodeSocketMenu", "NodeSocketString"} | set(ID_SOCKETS)


def _from_text(value, socket_type: str):
    """Convert a number or boolean sent as text to what the socket holds.

    Only the socket knows whether "5" is the number five or a label, so the
    conversion happens here and a String socket keeps its text.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    try:
        if socket_type.startswith("NodeSocketFloat"):
            number = float(text)
            return number if math.isfinite(number) else value
        if socket_type.startswith("NodeSocketInt"):
            number = float(text)
            return int(number) if math.isfinite(number) else value
    except ValueError:
        return value
    if socket_type.startswith("NodeSocketBool") and text.lower() in ("true", "false"):
        return text.lower() == "true"
    return value


def handle_create_geometry_nodes(params: dict) -> dict:
    """Create a Geometry Nodes modifier on an object."""
    object_name = params.get("object_name")
    name = params.get("name", "GeometryNodes")

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        modifier = obj.modifiers.new(name=name, type='NODES')

        # Create a new node group if one wasn't auto-created
        if modifier.node_group is None:
            node_group = bpy.data.node_groups.new(name=name, type='GeometryNodeTree')
            modifier.node_group = node_group

            # Add default Group Input and Group Output nodes
            input_node = node_group.nodes.new('NodeGroupInput')
            input_node.location = (-200, 0)
            output_node = node_group.nodes.new('NodeGroupOutput')
            output_node.location = (200, 0)

            # Create geometry input/output sockets
            node_group.interface.new_socket(
                name="Geometry",
                in_out='INPUT',
                socket_type='NodeSocketGeometry',
            )
            node_group.interface.new_socket(
                name="Geometry",
                in_out='OUTPUT',
                socket_type='NodeSocketGeometry',
            )

            # Connect input geometry to output geometry
            node_group.links.new(
                input_node.outputs[0],
                output_node.inputs[0],
            )

        return {
            "modifier_name": modifier.name,
            "node_group_name": modifier.node_group.name,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to create geometry nodes on '{object_name}': {e}")


def handle_add_geometry_node(params: dict) -> dict:
    """Add a node to a geometry nodes node group."""
    modifier_name = params.get("modifier_name")
    node_type = params.get("node_type")
    location = params.get("location", [0, 0])

    try:
        # Find the node group by looking through all objects' modifiers
        node_group = None
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == 'NODES' and mod.name == modifier_name and mod.node_group:
                    node_group = mod.node_group
                    break
            if node_group:
                break

        # Also check node groups directly by name
        if node_group is None:
            node_group = bpy.data.node_groups.get(modifier_name)

        if node_group is None:
            raise ValueError(
                f"No geometry nodes modifier or node group named '{modifier_name}' found"
            )

        # Ask this Blender what node classes it has rather than carrying a
        # list that goes stale. nodes.new() on an unknown type raises a bare
        # RuntimeError naming nothing useful, so near misses are offered:
        # GeometryNodeCube for GeometryNodeMeshCube is an easy guess to make.
        known = {c.__name__ for base in ("GeometryNode", "FunctionNode", "ShaderNode")
                 for c in getattr(bpy.types, base).__subclasses__()}
        if node_type not in known:
            lowered = node_type.lower()
            near = sorted(n for n in known
                          if lowered in n.lower() or n.lower() in lowered)
            hint = f" Did you mean: {', '.join(near[:5])}?" if near else ""
            raise ValueError(f"Unknown node type '{node_type}'.{hint}")

        node = node_group.nodes.new(type=node_type)
        node.location = (location[0], location[1])

        return {
            "node_name": node.name,
            "node_type": node.bl_idname,
            "location": list(node.location),
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to add node '{node_type}': {e}")


def handle_connect_geometry_nodes(params: dict) -> dict:
    """Connect two nodes in a geometry nodes node group."""
    modifier_name = params.get("modifier_name")
    from_node_name = params.get("from_node")
    from_socket_idx = params.get("from_socket")
    to_node_name = params.get("to_node")
    to_socket_idx = params.get("to_socket")

    try:
        # Find the node group
        node_group = None
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == 'NODES' and mod.name == modifier_name and mod.node_group:
                    node_group = mod.node_group
                    break
            if node_group:
                break

        if node_group is None:
            node_group = bpy.data.node_groups.get(modifier_name)

        if node_group is None:
            raise ValueError(
                f"No geometry nodes modifier or node group named '{modifier_name}' found"
            )

        from_node = node_group.nodes.get(from_node_name)
        if from_node is None:
            raise ValueError(f"Source node '{from_node_name}' not found")

        to_node = node_group.nodes.get(to_node_name)
        if to_node is None:
            raise ValueError(f"Destination node '{to_node_name}' not found")

        if from_socket_idx >= len(from_node.outputs):
            raise ValueError(
                f"Source socket index {from_socket_idx} out of range "
                f"(node has {len(from_node.outputs)} outputs)"
            )
        if to_socket_idx >= len(to_node.inputs):
            raise ValueError(
                f"Destination socket index {to_socket_idx} out of range "
                f"(node has {len(to_node.inputs)} inputs)"
            )

        link = node_group.links.new(  # noqa: F841
            from_node.outputs[from_socket_idx],
            to_node.inputs[to_socket_idx],
        )

        return {
            "from_node": from_node.name,
            "from_socket": from_socket_idx,
            "to_node": to_node.name,
            "to_socket": to_socket_idx,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to connect nodes: {e}")


def handle_set_geometry_node_input(params: dict) -> dict:
    """Set an input value on a geometry nodes modifier."""
    object_name = params.get("object_name")
    modifier_name = params.get("modifier_name")
    input_name = params.get("input_name")
    value = params.get("value")

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        modifier = obj.modifiers.get(modifier_name)
        if modifier is None or modifier.type != 'NODES':
            raise ValueError(
                f"Geometry nodes modifier '{modifier_name}' not found on '{object_name}'"
            )

        if modifier.node_group is None:
            raise ValueError(f"Modifier '{modifier_name}' has no node group")

        # Find the input identifier by name from the node group interface
        input_id = None
        for item in modifier.node_group.interface.items_tree:
            if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name == input_name:
                input_id = item.identifier
                value = _from_text(value, item.socket_type)
                break

        if input_id is None:
            raise ValueError(
                f"Input '{input_name}' not found on modifier '{modifier_name}'"
            )

        entry = getattr(modifier.properties.inputs, input_id, None)
        if not hasattr(entry, "value"):
            raise ValueError(f"Input '{input_name}' on '{modifier_name}' does not take a value")
        entry.value = value

        return {
            "input_name": input_name,
            "value": value,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set geometry node input: {e}")


def handle_list_geometry_node_inputs(params: dict) -> list:
    """List available inputs on a geometry nodes modifier."""
    object_name = params.get("object_name")
    modifier_name = params.get("modifier_name")

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        modifier = obj.modifiers.get(modifier_name)
        if modifier is None or modifier.type != 'NODES':
            raise ValueError(
                f"Geometry nodes modifier '{modifier_name}' not found on '{object_name}'"
            )

        if modifier.node_group is None:
            raise ValueError(f"Modifier '{modifier_name}' has no node group")

        inputs = []
        for item in modifier.node_group.interface.items_tree:
            if item.item_type == 'SOCKET' and item.in_out == 'INPUT':
                input_info = {
                    "name": item.name,
                    "type": item.socket_type,
                    "identifier": item.identifier,
                }
                # Geometry sockets have an entry but no value
                entry = getattr(modifier.properties.inputs, item.identifier, None)
                val = getattr(entry, "value", None)
                if hasattr(val, '__iter__') and not isinstance(val, str):
                    input_info["value"] = list(val)
                else:
                    input_info["value"] = val
                inputs.append(input_info)

        return inputs
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to list geometry node inputs: {e}")


def _local_gn_group(name):
    group = bpy.data.node_groups.get(name)
    return group if group is not None and group.bl_idname == "GeometryNodeTree" else None


def _essentials_gn_group(name):
    """The named Geometry Nodes group from Blender's bundled Essentials library.

    Every missing modifier group is appended in one go: appending them one at
    a time brings shared dependencies again each time, as ".001" copies.
    """
    existing = _local_gn_group(name)
    if existing is not None:
        return existing
    missing = [n for n in ESSENTIALS_MODIFIERS.values() if _local_gn_group(n) is None]
    path = os.path.join(bpy.utils.system_resource("DATAFILES", path="assets"),
                        ESSENTIALS_GN_FILE)
    with bpy.data.libraries.load(path, link=False) as (_src, dst):
        dst.node_groups = list(missing)  # Blender fills this list in place
    # A name taken by a non-geometry group makes Blender rename the append
    return dict(zip(missing, dst.node_groups))[name]


def _modifier_input_items(group):
    return [i for i in group.interface.items_tree
            if i.item_type == "SOCKET" and i.in_out == "INPUT"]


def _shape_fits(item, value):
    """Whether a value has the right shape for a socket: picks between same-named inputs."""
    if isinstance(value, str):
        return item.socket_type in TEXT_SOCKETS
    if isinstance(value, list):
        return item.socket_type in ("NodeSocketVector", "NodeSocketColor",
                                    "NodeSocketRotation")
    return item.socket_type not in TEXT_SOCKETS and item.socket_type not in (
        "NodeSocketVector", "NodeSocketColor", "NodeSocketRotation")


def _set_modifier_inputs(modifier, settings):
    items = _modifier_input_items(modifier.node_group)
    for name, value in settings.items():
        candidates = [i for i in items if i.name == name]
        if not candidates:
            valid = ", ".join(sorted({i.name for i in items}))
            raise ValueError(f"'{modifier.node_group.name}' has no input '{name}'. "
                             f"Inputs: {valid}")
        item = next((i for i in candidates if _shape_fits(i, value)), candidates[0])
        entry = getattr(modifier.properties.inputs, item.identifier, None)
        if not hasattr(entry, "value"):
            raise ValueError(f"Input '{name}' takes geometry from the modifier stack, "
                             f"not a value")
        if item.socket_type in ID_SOCKETS:
            collection = getattr(bpy.data, ID_SOCKETS[item.socket_type])
            found = collection.get(value) if isinstance(value, str) else None
            if found is None:
                raise ValueError(f"Input '{name}' needs an existing "
                                 f"{ID_SOCKETS[item.socket_type][:-1]}; '{value}' not found")
            value = found
        try:
            entry.value = value
        except (TypeError, ValueError) as e:
            raise ValueError(f"Cannot set '{name}' to {value!r}: {e}") from None


def _modifier_input_values(modifier):
    values = {}
    for item in _modifier_input_items(modifier.node_group):
        entry = getattr(modifier.properties.inputs, item.identifier, None)
        if not hasattr(entry, "value"):
            continue
        value = entry.value
        if hasattr(value, "name") and not isinstance(value, str):
            value = value.name
        elif hasattr(value, "__len__") and not isinstance(value, str):
            value = list(value)
        key = item.name if item.name not in values else f"{item.name} ({item.socket_type[10:]})"
        values[key] = value
    return values


def handle_add_essentials_modifier(params):
    """Add an Essentials node-group modifier and set its inputs by name."""
    group_name = ESSENTIALS_MODIFIERS.get(params.get("modifier"))
    if group_name is None:
        raise ValueError(f"Unknown Essentials modifier: {params.get('modifier')!r}")
    object_name = params.get("object_name")
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object '{object_name}' not found")
    if not hasattr(obj, "modifiers"):
        raise ValueError(f"Object '{object_name}' cannot take modifiers")

    group = _essentials_gn_group(group_name)
    modifier = obj.modifiers.new(name=group.name, type="NODES")
    modifier.node_group = group
    try:
        _set_modifier_inputs(modifier, params.get("settings", {}))
    except Exception:
        obj.modifiers.remove(modifier)
        raise
    return {"object": obj.name, "modifier": modifier.name,
            "inputs": _modifier_input_values(modifier)}


def register():
    """Register geometry nodes handlers with the dispatcher."""
    dispatcher.register_handler("create_geometry_nodes", handle_create_geometry_nodes)
    dispatcher.register_handler("add_geometry_node", handle_add_geometry_node)
    dispatcher.register_handler("connect_geometry_nodes", handle_connect_geometry_nodes)
    dispatcher.register_handler("set_geometry_node_input", handle_set_geometry_node_input)
    dispatcher.register_handler("list_geometry_node_inputs", handle_list_geometry_node_inputs)
    dispatcher.register_handler("add_essentials_modifier", handle_add_essentials_modifier)
