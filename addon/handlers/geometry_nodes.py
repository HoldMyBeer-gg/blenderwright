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
        known = _known_node_types()
        if node_type not in known:
            raise ValueError(_unknown_node_message(node_type, known))

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


INTERFACE_SOCKETS = {
    "GEOMETRY": "NodeSocketGeometry", "FLOAT": "NodeSocketFloat", "INT": "NodeSocketInt",
    "BOOLEAN": "NodeSocketBool", "VECTOR": "NodeSocketVector", "COLOR": "NodeSocketColor",
    "ROTATION": "NodeSocketRotation", "STRING": "NodeSocketString",
    "OBJECT": "NodeSocketObject", "COLLECTION": "NodeSocketCollection",
    "MATERIAL": "NodeSocketMaterial",
}
NODE_SETTING_TYPES = {"BOOLEAN", "INT", "FLOAT", "ENUM", "STRING"}


NODE_PREFIXES = ("GeometryNode", "FunctionNode", "ShaderNode")


def _unknown_node_message(node_type, known):
    """Name the closest real node types: GeometryNodeCube -> GeometryNodeMeshCube."""
    import difflib

    prefix = next((p for p in NODE_PREFIXES if node_type.startswith(p)), "")
    tail = node_type[len(prefix):].lower()
    near = {n for n in known if tail and tail in n.lower()}
    near.update(difflib.get_close_matches(node_type, known, n=5, cutoff=0.75))
    ranked = sorted(near, key=lambda n: (len(n), n))[:5]
    hint = f" Did you mean: {', '.join(ranked)}?" if ranked else ""
    return f"Unknown node type '{node_type}'.{hint}"


def _known_node_types():
    """Node classes this Blender has, by name. 5.2 creates bpy.types classes
    lazily, so __subclasses__() is empty and refused every node."""
    base_names = NODE_PREFIXES
    bases = tuple(getattr(bpy.types, b) for b in base_names)
    known = set()
    for name in dir(bpy.types):
        if name.startswith(base_names) and name not in base_names:
            cls = getattr(bpy.types, name, None)
            if isinstance(cls, type) and issubclass(cls, bases):
                known.add(name)
    return known


def _base_node_props():
    """Properties every node has (name, location, label...): not node settings."""
    return set(bpy.types.Node.bl_rna.properties.keys())


def _data_block(socket_type, name, what):
    collection = getattr(bpy.data, ID_SOCKETS[socket_type])
    found = collection.get(name) if isinstance(name, str) else None
    if found is None:
        raise ValueError(f"{what} needs an existing {ID_SOCKETS[socket_type][:-1]}; "
                         f"'{name}' not found")
    return found


def _find_socket(node, sockets, ref, side):
    if isinstance(ref, str) and ref.isdigit():
        ref = int(ref)
    if isinstance(ref, int):
        if ref >= len(sockets):
            raise ValueError(f"'{node.name}' has {len(sockets)} {side}s; index {ref} is past them")
        return sockets[ref]
    for want_enabled in (True, False):
        for sock in sockets:
            if (sock.name == ref or sock.identifier == ref) and (sock.enabled or not want_enabled):
                return sock
    names = ", ".join(sock.name for sock in sockets if sock.enabled)
    raise ValueError(f"'{node.name}' has no {side} '{ref}'. {side.capitalize()}s: {names}")


def _apply_node_settings(node, settings):
    base = _base_node_props()
    props = node.bl_rna.properties
    for key, value in settings.items():
        rna = props.get(key)
        if rna is None or key in base or rna.is_readonly or rna.type not in NODE_SETTING_TYPES:
            own = sorted(k for k, p in props.items() if k not in base and not p.is_readonly
                         and p.type in NODE_SETTING_TYPES)
            raise ValueError(f"'{key}' is not a setting of {node.bl_idname}. "
                             f"Settings: {', '.join(own) or 'none'}")
        try:
            setattr(node, key, value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"{node.name}: cannot set {key} to {value!r}: {e}") from None


def _set_socket_value(node, sock, value):
    if sock.bl_idname in ID_SOCKETS:
        value = _data_block(sock.bl_idname, value, f"'{node.name}' input '{sock.name}'")
    else:
        value = _from_text(value, sock.bl_idname)
    try:
        sock.default_value = value
    except (TypeError, ValueError, AttributeError) as e:
        raise ValueError(f"'{node.name}' input '{sock.name}' cannot take {value!r}: {e}") from None


def _add_interface(group, items, in_out):
    for item in items:
        socket_type = INTERFACE_SOCKETS[item["type"]]
        sock = group.interface.new_socket(name=item["name"], in_out=in_out,
                                          socket_type=socket_type)
        if "default" in item:
            value = item["default"]
            if socket_type in ID_SOCKETS:
                value = _data_block(socket_type, value, f"Group input '{item['name']}'")
            sock.default_value = value
        if "min" in item:
            sock.min_value = item["min"]
        if "max" in item:
            sock.max_value = item["max"]


def _fill_group(group, spec):
    _add_interface(group, [{"name": "Geometry", "type": "GEOMETRY"}] + spec["inputs"], "INPUT")
    _add_interface(group, [{"name": "Geometry", "type": "GEOMETRY"}] + spec["outputs"], "OUTPUT")
    group_in = group.nodes.new("NodeGroupInput")
    group_in.location = (-400, 0)
    group_out = group.nodes.new("NodeGroupOutput")
    group_out.location = (400, 0)
    nodes = {"Group Input": group_in, "Group Output": group_out}

    known = _known_node_types()
    for entry in spec["nodes"]:
        if entry["type"] not in known:
            raise ValueError(_unknown_node_message(entry["type"], known))
        node = group.nodes.new(type=entry["type"])
        node.name = entry["name"]
        node.location = tuple(entry.get("location", (0, 0)))
        _apply_node_settings(node, entry.get("settings", {}))  # may change which sockets exist
        nodes[entry["name"]] = node

    # Zones get their sockets from pairing, so pair before any value or link
    for entry in spec["nodes"]:
        if "pair_with" in entry:
            node = nodes[entry["name"]]
            if not hasattr(node, "pair_with_output"):
                raise ValueError(f"'{node.name}' is not a zone input node; only simulation, "
                                 f"repeat and for-each zone inputs pair")
            if not node.pair_with_output(nodes[entry["pair_with"]]):
                raise ValueError(f"'{node.name}' cannot pair with '{entry['pair_with']}': "
                                 f"use the matching zone output node")

    for entry in spec["nodes"]:
        node = nodes[entry["name"]]
        for ref, value in entry.get("inputs", {}).items():
            _set_socket_value(node, _find_socket(node, node.inputs, ref, "input"), value)

    links = spec["links"]
    if not any(link[2] == "Group Output" for link in links):
        links = [["Group Input", "Geometry", "Group Output", "Geometry"]] + links
    for from_name, from_ref, to_name, to_ref in links:
        source, target = nodes[from_name], nodes[to_name]
        group.links.new(_find_socket(source, source.outputs, from_ref, "output"),
                        _find_socket(target, target.inputs, to_ref, "input"))
    return len(nodes), len(links)


def handle_build_geometry_nodes(params):
    """Build into a fresh group; swap it onto the modifier only if every step worked."""
    obj = bpy.data.objects.get(params.get("object_name"))
    if obj is None:
        raise ValueError(f"Object '{params.get('object_name')}' not found")
    if not hasattr(obj, "modifiers"):
        raise ValueError(f"Object '{obj.name}' cannot take modifiers")
    name = params.get("modifier_name", "GeometryNodes")
    group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")
    try:
        node_count, link_count = _fill_group(group, params["spec"])
    except Exception:
        bpy.data.node_groups.remove(group)
        raise
    modifier = obj.modifiers.get(name)
    if modifier is None:
        modifier = obj.modifiers.new(name=name, type="NODES")
    elif modifier.type != "NODES":
        bpy.data.node_groups.remove(group)
        raise ValueError(f"Modifier '{name}' is not a geometry nodes modifier")
    modifier.node_group = group
    return {"object": obj.name, "modifier": modifier.name, "node_group": group.name,
            "nodes": node_count, "links": link_count}


def _plain(value):
    if hasattr(value, "name") and not isinstance(value, str):
        return value.name
    if hasattr(value, "__len__") and not isinstance(value, str):
        return [round(v, 4) if isinstance(v, float) else v for v in value]
    return round(value, 4) if isinstance(value, float) else value


def handle_get_geometry_node_tree(params):
    obj = bpy.data.objects.get(params.get("object_name"))
    if obj is None:
        raise ValueError(f"Object '{params.get('object_name')}' not found")
    modifier = obj.modifiers.get(params.get("modifier_name"))
    if modifier is None or modifier.type != "NODES" or modifier.node_group is None:
        raise ValueError(f"'{obj.name}' has no geometry nodes modifier "
                         f"'{params.get('modifier_name')}'")
    group = modifier.node_group
    base = _base_node_props()
    interface = [{"name": i.name, "in_out": i.in_out,
                  "type": next((k for k, v in INTERFACE_SOCKETS.items() if v == i.socket_type),
                               i.socket_type)}
                 for i in group.interface.items_tree if i.item_type == "SOCKET"]
    nodes = []
    for node in group.nodes:
        settings = {k: _plain(getattr(node, k)) for k, p in node.bl_rna.properties.items()
                    if k not in base and not p.is_readonly and p.type in NODE_SETTING_TYPES}
        inputs = {sock.identifier: _plain(sock.default_value) for sock in node.inputs
                  if sock.enabled and not sock.is_linked and hasattr(sock, "default_value")}
        nodes.append({"name": node.name, "type": node.bl_idname,
                      "location": [round(v) for v in node.location],
                      "settings": settings, "inputs": inputs})
    links = [[lk.from_node.name, lk.from_socket.identifier, lk.to_node.name,
              lk.to_socket.identifier] for lk in group.links]
    return {"node_group": group.name, "interface": interface, "nodes": nodes, "links": links}


def register():
    """Register geometry nodes handlers with the dispatcher."""
    dispatcher.register_handler("create_geometry_nodes", handle_create_geometry_nodes)
    dispatcher.register_handler("add_geometry_node", handle_add_geometry_node)
    dispatcher.register_handler("build_geometry_nodes", handle_build_geometry_nodes)
    dispatcher.register_handler("get_geometry_node_tree", handle_get_geometry_node_tree)
    dispatcher.register_handler("connect_geometry_nodes", handle_connect_geometry_nodes)
    dispatcher.register_handler("set_geometry_node_input", handle_set_geometry_node_input)
    dispatcher.register_handler("list_geometry_node_inputs", handle_list_geometry_node_inputs)
    dispatcher.register_handler("add_essentials_modifier", handle_add_essentials_modifier)
