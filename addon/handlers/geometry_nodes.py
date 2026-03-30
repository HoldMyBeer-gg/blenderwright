"""Blender addon handlers for geometry nodes commands."""

import bpy
from .. import dispatcher


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
                break

        if input_id is None:
            raise ValueError(
                f"Input '{input_name}' not found on modifier '{modifier_name}'"
            )

        # Set the value using the modifier's indexed access
        modifier[input_id] = value

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
                # Try to get current value
                try:
                    val = modifier[item.identifier]
                    # Convert to serializable type
                    if hasattr(val, '__iter__') and not isinstance(val, str):
                        input_info["value"] = list(val)
                    else:
                        input_info["value"] = val
                except (KeyError, TypeError):
                    input_info["value"] = None
                inputs.append(input_info)

        return inputs
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to list geometry node inputs: {e}")


def register():
    """Register geometry nodes handlers with the dispatcher."""
    dispatcher.register_handler("create_geometry_nodes", handle_create_geometry_nodes)
    dispatcher.register_handler("add_geometry_node", handle_add_geometry_node)
    dispatcher.register_handler("connect_geometry_nodes", handle_connect_geometry_nodes)
    dispatcher.register_handler("set_geometry_node_input", handle_set_geometry_node_input)
    dispatcher.register_handler("list_geometry_node_inputs", handle_list_geometry_node_inputs)
