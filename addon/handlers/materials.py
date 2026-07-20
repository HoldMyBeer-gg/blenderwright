"""Blender handlers for material and shading operations."""

import bpy
from .. import dispatcher


def _get_material(name: str):
    """Get a material by name or raise."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        raise ValueError(f"Material '{name}' not found")
    return mat


def _get_principled_bsdf(mat):
    """Get the Principled BSDF node from a material's node tree."""
    if not mat.use_nodes or mat.node_tree is None:
        raise ValueError(f"Material '{mat.name}' does not use nodes")
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            return node
    raise ValueError(f"Material '{mat.name}' has no Principled BSDF node")


def handle_create_material(params: dict) -> dict:
    """Create a new material with Principled BSDF."""
    try:
        name = params["name"]
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        # Blender automatically adds Principled BSDF when use_nodes is set
        return {"name": mat.name, "created": True}
    except Exception as e:
        raise RuntimeError(f"Failed to create material: {e}")


def handle_assign_material(params: dict) -> dict:
    """Assign a material to an object."""
    try:
        obj_name = params["object_name"]
        mat_name = params["material_name"]

        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            raise ValueError(f"Object '{obj_name}' not found")

        mat = _get_material(mat_name)

        if obj.data is None or not hasattr(obj.data, "materials"):
            raise ValueError(f"Object '{obj_name}' does not support materials")

        # Check if material is already assigned
        for i, slot_mat in enumerate(obj.data.materials):
            if slot_mat and slot_mat.name == mat_name:
                obj.active_material_index = i
                return {"object": obj.name, "material": mat.name, "action": "already_assigned", "slot": i}

        obj.data.materials.append(mat)
        obj.active_material_index = len(obj.data.materials) - 1
        return {"object": obj.name, "material": mat.name, "action": "assigned", "slot": len(obj.data.materials) - 1}
    except Exception as e:
        raise RuntimeError(f"Failed to assign material: {e}")


def handle_set_material_color(params: dict) -> dict:
    """Set the base color on a Principled BSDF node."""
    try:
        mat_name = params["material_name"]
        color = params["color"]

        mat = _get_material(mat_name)
        bsdf = _get_principled_bsdf(mat)

        bsdf.inputs["Base Color"].default_value = tuple(color)
        return {"material": mat.name, "color": list(color)}
    except Exception as e:
        raise RuntimeError(f"Failed to set material color: {e}")


# Mapping from our property names to Principled BSDF input names
_PROPERTY_TO_INPUT = {
    "metallic": "Metallic",
    "roughness": "Roughness",
    "specular_ior_level": "Specular IOR Level",
    "emission_strength": "Emission Strength",
    "alpha": "Alpha",
    "transmission_weight": "Transmission Weight",
    "ior": "IOR",
    "coat_weight": "Coat Weight",
    "coat_roughness": "Coat Roughness",
    "sheen_weight": "Sheen Weight",
    "sheen_roughness": "Sheen Roughness",
    "anisotropic": "Anisotropic",
    "anisotropic_rotation": "Anisotropic Rotation",
    "subsurface_weight": "Subsurface Weight",
    "emission_color": "Emission Color",
}


def handle_set_material_property(params: dict) -> dict:
    """Set a property on the Principled BSDF node."""
    try:
        mat_name = params["material_name"]
        prop = params["property"]
        value = params["value"]

        mat = _get_material(mat_name)
        bsdf = _get_principled_bsdf(mat)

        input_name = _PROPERTY_TO_INPUT.get(prop)
        if input_name is None:
            raise ValueError(f"Unknown material property: '{prop}'")

        if input_name not in bsdf.inputs:
            raise ValueError(f"Principled BSDF does not have input '{input_name}'")

        if isinstance(value, (list, tuple)):
            bsdf.inputs[input_name].default_value = tuple(value)
        else:
            bsdf.inputs[input_name].default_value = value

        return {"material": mat.name, "property": prop, "value": value}
    except Exception as e:
        raise RuntimeError(f"Failed to set material property: {e}")


def handle_create_principled_material(params: dict) -> dict:
    """Create a fully configured Principled BSDF material."""
    try:
        name = params["name"]
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True

        bsdf = _get_principled_bsdf(mat)

        bsdf.inputs["Base Color"].default_value = tuple(params.get("color", [0.8, 0.8, 0.8, 1.0]))
        bsdf.inputs["Metallic"].default_value = params.get("metallic", 0.0)
        bsdf.inputs["Roughness"].default_value = params.get("roughness", 0.5)
        bsdf.inputs["Specular IOR Level"].default_value = params.get("specular", 0.5)
        bsdf.inputs["Emission Strength"].default_value = params.get("emission_strength", 0.0)
        bsdf.inputs["Emission Color"].default_value = tuple(params.get("emission_color", [1.0, 1.0, 1.0, 1.0]))
        bsdf.inputs["Alpha"].default_value = params.get("alpha", 1.0)
        bsdf.inputs["Transmission Weight"].default_value = params.get("transmission", 0.0)
        bsdf.inputs["IOR"].default_value = params.get("ior", 1.45)

        return {
            "name": mat.name,
            "created": True,
            "color": params.get("color", [0.8, 0.8, 0.8, 1.0]),
            "metallic": params.get("metallic", 0.0),
            "roughness": params.get("roughness", 0.5),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to create principled material: {e}")


def handle_add_texture_node(params: dict) -> dict:
    """Add an image texture node and connect to Principled BSDF Base Color."""
    try:
        mat_name = params["material_name"]
        image_path = params["image_path"]
        label = params.get("label", "Image Texture")

        mat = _get_material(mat_name)
        if not mat.use_nodes or mat.node_tree is None:
            raise ValueError(f"Material '{mat_name}' does not use nodes")

        bsdf = _get_principled_bsdf(mat)
        tree = mat.node_tree

        # Create image texture node
        tex_node = tree.nodes.new(type='ShaderNodeTexImage')
        tex_node.label = label
        tex_node.location = (bsdf.location[0] - 300, bsdf.location[1])

        # Load the image
        img = bpy.data.images.load(image_path, check_existing=True)
        tex_node.image = img

        # Connect Color output to Base Color input
        tree.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

        return {
            "material": mat.name,
            "texture_node": tex_node.name,
            "image": img.name,
            "image_path": image_path,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to add texture node: {e}")


def handle_set_material_blend_mode(params: dict) -> dict:
    """Set the blend mode of a material."""
    try:
        mat_name = params["material_name"]
        mode = params["mode"]

        mat = _get_material(mat_name)
        mat.blend_method = mode

        return {"material": mat.name, "blend_mode": mode}
    except Exception as e:
        raise RuntimeError(f"Failed to set blend mode: {e}")


def handle_list_materials(params: dict) -> list:
    """List all materials."""
    try:
        result = []
        for mat in bpy.data.materials:
            info = {
                "name": mat.name,
                "users": mat.users,
                "use_nodes": mat.use_nodes,
            }
            if mat.use_nodes and mat.node_tree:
                for node in mat.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        info["has_principled_bsdf"] = True
                        break
            result.append(info)
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to list materials: {e}")


def handle_delete_material(params: dict) -> dict:
    """Delete a material."""
    try:
        mat_name = params["material_name"]
        mat = _get_material(mat_name)
        bpy.data.materials.remove(mat)
        return {"deleted": mat_name}
    except Exception as e:
        raise RuntimeError(f"Failed to delete material: {e}")


def handle_duplicate_material(params: dict) -> dict:
    """Duplicate a material."""
    try:
        mat_name = params["material_name"]
        new_name = params["new_name"]

        mat = _get_material(mat_name)
        new_mat = mat.copy()
        new_mat.name = new_name
        if mat.node_tree:
            new_mat.node_tree = mat.node_tree.copy()

        return {"original": mat.name, "duplicate": new_mat.name}
    except Exception as e:
        raise RuntimeError(f"Failed to duplicate material: {e}")


def _get_node_tree(mat):
    """Get the node tree from a material or raise."""
    if not mat.use_nodes or mat.node_tree is None:
        raise ValueError(f"Material '{mat.name}' does not use nodes")
    return mat.node_tree


def handle_add_shader_node(params: dict) -> dict:
    """Add a shader node to a material's node tree."""
    try:
        mat_name = params["material_name"]
        node_type = params["node_type"]
        location = params.get("location", (0, 0))

        mat = _get_material(mat_name)
        tree = _get_node_tree(mat)

        node = tree.nodes.new(type=node_type)
        node.location = tuple(location)

        return {
            "material": mat.name,
            "node_name": node.name,
            "node_type": node_type,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to add shader node: {e}")


def handle_connect_shader_nodes(params: dict) -> dict:
    """Connect two shader nodes via their sockets."""
    try:
        mat_name = params["material_name"]
        from_node_name = params["from_node"]
        from_socket_name = params["from_socket"]
        to_node_name = params["to_node"]
        to_socket_name = params["to_socket"]

        mat = _get_material(mat_name)
        tree = _get_node_tree(mat)

        from_node = tree.nodes.get(from_node_name)
        if from_node is None:
            raise ValueError(f"Node '{from_node_name}' not found")

        to_node = tree.nodes.get(to_node_name)
        if to_node is None:
            raise ValueError(f"Node '{to_node_name}' not found")

        from_socket = from_node.outputs.get(from_socket_name)
        if from_socket is None:
            raise ValueError(f"Output socket '{from_socket_name}' not found on node '{from_node_name}'")

        to_socket = to_node.inputs.get(to_socket_name)
        if to_socket is None:
            raise ValueError(f"Input socket '{to_socket_name}' not found on node '{to_node_name}'")

        tree.links.new(from_socket, to_socket)

        return {
            "material": mat.name,
            "from_node": from_node_name,
            "from_socket": from_socket_name,
            "to_node": to_node_name,
            "to_socket": to_socket_name,
            "connected": True,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to connect shader nodes: {e}")


def handle_disconnect_shader_nodes(params: dict) -> dict:
    """Disconnect all links from a specific socket on a shader node."""
    try:
        mat_name = params["material_name"]
        node_name = params["node_name"]
        socket_name = params["socket_name"]
        is_input = params.get("is_input", True)

        mat = _get_material(mat_name)
        tree = _get_node_tree(mat)

        node = tree.nodes.get(node_name)
        if node is None:
            raise ValueError(f"Node '{node_name}' not found")

        sockets = node.inputs if is_input else node.outputs
        socket = sockets.get(socket_name)
        if socket is None:
            kind = "input" if is_input else "output"
            raise ValueError(f"{kind.capitalize()} socket '{socket_name}' not found on node '{node_name}'")

        removed = 0
        for link in list(tree.links):
            if is_input and link.to_socket == socket:
                tree.links.remove(link)
                removed += 1
            elif not is_input and link.from_socket == socket:
                tree.links.remove(link)
                removed += 1

        return {
            "material": mat.name,
            "node_name": node_name,
            "socket_name": socket_name,
            "is_input": is_input,
            "links_removed": removed,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to disconnect shader nodes: {e}")


def handle_remove_shader_node(params: dict) -> dict:
    """Remove a shader node from a material's node tree."""
    try:
        mat_name = params["material_name"]
        node_name = params["node_name"]

        mat = _get_material(mat_name)
        tree = _get_node_tree(mat)

        node = tree.nodes.get(node_name)
        if node is None:
            raise ValueError(f"Node '{node_name}' not found")

        tree.nodes.remove(node)

        return {
            "material": mat.name,
            "removed": node_name,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to remove shader node: {e}")


def handle_get_node_tree(params: dict) -> dict:
    """Serialize the full node tree of a material."""
    try:
        mat_name = params["material_name"]

        mat = _get_material(mat_name)
        tree = _get_node_tree(mat)

        nodes = []
        for node in tree.nodes:
            nodes.append({
                "name": node.name,
                "type": node.bl_idname,
                "location": [node.location[0], node.location[1]],
                "inputs": [inp.name for inp in node.inputs],
                "outputs": [out.name for out in node.outputs],
            })

        links = []
        for link in tree.links:
            links.append({
                "from_node": link.from_node.name,
                "from_socket": link.from_socket.name,
                "to_node": link.to_node.name,
                "to_socket": link.to_socket.name,
            })

        return {
            "material": mat.name,
            "nodes": nodes,
            "links": links,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to get node tree: {e}")


# Node-level properties that may be written by set_shader_node_property.
# Deliberately duplicated from the MCP tool layer: any local process can open
# the addon's socket, so the allowlist has to be enforced on this side too.
# Without it, setattr() on a caller-supplied name is an arbitrary attribute
# write against a live Blender datablock.
ALLOWED_NODE_PROPERTIES = {
    "operation", "use_clamp", "blend_type", "data_type", "clamp",
    "clamp_factor", "clamp_result", "interpolation_type", "factor_mode",
    "noise_dimensions", "noise_type", "normalize",
    "voronoi_dimensions", "feature", "distance",
    "wave_type", "wave_profile", "bands_direction", "rings_direction",
    "gradient_type", "offset", "offset_frequency", "squash", "squash_frequency",
    "turbulence_depth",
    "interpolation", "projection", "extension",
    "vector_type", "rotation_type", "invert", "space", "uv_map",
    "convert_from", "convert_to", "mode", "component", "axis",
    "attribute_name", "attribute_type", "from_instancer",
    "distribution", "subsurface_method",
}

ALLOWED_RAMP_INTERPOLATIONS = {"EASE", "CARDINAL", "LINEAR", "B_SPLINE", "CONSTANT"}
ALLOWED_RAMP_COLOR_MODES = {"RGB", "HSV", "HSL"}


def _get_node(tree, node_name: str):
    """Get a node from a tree by name or raise."""
    node = tree.nodes.get(node_name)
    if node is None:
        raise ValueError(f"Node '{node_name}' not found")
    return node


def _get_socket(node, socket):
    """Resolve a socket by name or by zero-based index."""
    if isinstance(socket, bool):
        raise ValueError("socket must be a name or a non-negative index")
    if isinstance(socket, int):
        if socket < 0 or socket >= len(node.inputs):
            raise ValueError(
                f"Socket index {socket} out of range on node '{node.name}' "
                f"({len(node.inputs)} inputs)"
            )
        return node.inputs[socket]
    resolved = node.inputs.get(socket)
    if resolved is None:
        raise ValueError(f"Input socket '{socket}' not found on node '{node.name}'")
    return resolved


def _get_ramp(node):
    """Get a node's colour ramp or raise if it has none."""
    ramp = getattr(node, "color_ramp", None)
    if ramp is None:
        raise ValueError(
            f"Node '{node.name}' has no colour ramp "
            f"(expected a ColorRamp / ShaderNodeValToRGB node)"
        )
    return ramp


def _ramp_element(ramp, index: int):
    """Get a ramp element by index or raise."""
    if not isinstance(index, int) or isinstance(index, bool):
        raise ValueError("index must be an integer")
    if index < 0 or index >= len(ramp.elements):
        raise ValueError(
            f"Element index {index} out of range ({len(ramp.elements)} elements)"
        )
    return ramp.elements[index]


def handle_set_shader_node_input(params: dict) -> dict:
    """Set the default value of an input socket on a shader node."""
    try:
        mat = _get_material(params["material_name"])
        tree = _get_node_tree(mat)
        node = _get_node(tree, params["node_name"])
        socket = _get_socket(node, params["socket"])
        value = params["value"]

        if not hasattr(socket, "default_value"):
            raise ValueError(
                f"Socket '{socket.name}' on node '{node.name}' has no default "
                f"value (shader and geometry sockets carry no standalone value)"
            )

        if isinstance(value, (list, tuple)):
            socket.default_value = tuple(value)
        else:
            socket.default_value = value

        return {
            "material": mat.name,
            "node_name": node.name,
            "socket": socket.name,
            "value": value,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to set shader node input: {e}")


def handle_set_shader_node_property(params: dict) -> dict:
    """Set an allowlisted node-level property on a shader node."""
    try:
        prop = params["property"]
        if prop not in ALLOWED_NODE_PROPERTIES:
            raise ValueError(f"Property '{prop}' is not allowed")

        mat = _get_material(params["material_name"])
        tree = _get_node_tree(mat)
        node = _get_node(tree, params["node_name"])

        if not hasattr(node, prop):
            raise ValueError(f"Node '{node.name}' has no property '{prop}'")

        setattr(node, prop, params["value"])

        return {
            "material": mat.name,
            "node_name": node.name,
            "property": prop,
            "value": params["value"],
        }
    except Exception as e:
        raise RuntimeError(f"Failed to set shader node property: {e}")


def handle_add_color_ramp_element(params: dict) -> dict:
    """Add a colour stop to a ColorRamp node."""
    try:
        mat = _get_material(params["material_name"])
        tree = _get_node_tree(mat)
        node = _get_node(tree, params["node_name"])
        ramp = _get_ramp(node)

        element = ramp.elements.new(params["position"])
        element.color = tuple(params["color"])

        index = next(
            (i for i, e in enumerate(ramp.elements) if e == element),
            len(ramp.elements) - 1,
        )

        return {
            "material": mat.name,
            "node_name": node.name,
            "index": index,
            "position": element.position,
            "color": list(element.color),
            "total": len(ramp.elements),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to add colour ramp element: {e}")


def handle_remove_color_ramp_element(params: dict) -> dict:
    """Remove a colour stop from a ColorRamp node."""
    try:
        mat = _get_material(params["material_name"])
        tree = _get_node_tree(mat)
        node = _get_node(tree, params["node_name"])
        ramp = _get_ramp(node)

        if len(ramp.elements) <= 1:
            raise ValueError("A colour ramp must keep at least one element")

        element = _ramp_element(ramp, params["index"])
        ramp.elements.remove(element)

        return {
            "material": mat.name,
            "node_name": node.name,
            "removed": params["index"],
            "remaining": len(ramp.elements),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to remove colour ramp element: {e}")


def handle_set_color_ramp_element(params: dict) -> dict:
    """Move or recolor an existing ColorRamp stop."""
    try:
        mat = _get_material(params["material_name"])
        tree = _get_node_tree(mat)
        node = _get_node(tree, params["node_name"])
        ramp = _get_ramp(node)
        element = _ramp_element(ramp, params["index"])

        if "position" in params:
            element.position = params["position"]
        if "color" in params:
            element.color = tuple(params["color"])

        return {
            "material": mat.name,
            "node_name": node.name,
            "index": params["index"],
            "position": element.position,
            "color": list(element.color),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to set colour ramp element: {e}")


def handle_set_color_ramp_interpolation(params: dict) -> dict:
    """Set the interpolation and optionally the colour mode of a ColorRamp."""
    try:
        interpolation = params["interpolation"]
        if interpolation not in ALLOWED_RAMP_INTERPOLATIONS:
            raise ValueError(f"Interpolation '{interpolation}' is not allowed")

        color_mode = params.get("color_mode")
        if color_mode is not None and color_mode not in ALLOWED_RAMP_COLOR_MODES:
            raise ValueError(f"Colour mode '{color_mode}' is not allowed")

        mat = _get_material(params["material_name"])
        tree = _get_node_tree(mat)
        node = _get_node(tree, params["node_name"])
        ramp = _get_ramp(node)

        ramp.interpolation = interpolation
        if color_mode is not None:
            ramp.color_mode = color_mode

        return {
            "material": mat.name,
            "node_name": node.name,
            "interpolation": ramp.interpolation,
            "color_mode": ramp.color_mode,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to set colour ramp interpolation: {e}")


def handle_get_color_ramp(params: dict) -> dict:
    """Serialize every stop on a ColorRamp node."""
    try:
        mat = _get_material(params["material_name"])
        tree = _get_node_tree(mat)
        node = _get_node(tree, params["node_name"])
        ramp = _get_ramp(node)

        elements = [
            {
                "index": i,
                "position": element.position,
                "color": list(element.color),
            }
            for i, element in enumerate(ramp.elements)
        ]

        return {
            "material": mat.name,
            "node_name": node.name,
            "elements": elements,
            "interpolation": ramp.interpolation,
            "color_mode": ramp.color_mode,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to get colour ramp: {e}")


def register():
    """Register all material handlers with the dispatcher."""
    dispatcher.register_handler("create_material", handle_create_material)
    dispatcher.register_handler("assign_material", handle_assign_material)
    dispatcher.register_handler("set_material_color", handle_set_material_color)
    dispatcher.register_handler("set_material_property", handle_set_material_property)
    dispatcher.register_handler("create_principled_material", handle_create_principled_material)
    dispatcher.register_handler("add_texture_node", handle_add_texture_node)
    dispatcher.register_handler("set_material_blend_mode", handle_set_material_blend_mode)
    dispatcher.register_handler("list_materials", handle_list_materials)
    dispatcher.register_handler("delete_material", handle_delete_material)
    dispatcher.register_handler("duplicate_material", handle_duplicate_material)
    dispatcher.register_handler("add_shader_node", handle_add_shader_node)
    dispatcher.register_handler("connect_shader_nodes", handle_connect_shader_nodes)
    dispatcher.register_handler("disconnect_shader_nodes", handle_disconnect_shader_nodes)
    dispatcher.register_handler("remove_shader_node", handle_remove_shader_node)
    dispatcher.register_handler("get_node_tree", handle_get_node_tree)
    dispatcher.register_handler("set_shader_node_input", handle_set_shader_node_input)
    dispatcher.register_handler("set_shader_node_property", handle_set_shader_node_property)
    dispatcher.register_handler("add_color_ramp_element", handle_add_color_ramp_element)
    dispatcher.register_handler("remove_color_ramp_element", handle_remove_color_ramp_element)
    dispatcher.register_handler("set_color_ramp_element", handle_set_color_ramp_element)
    dispatcher.register_handler("set_color_ramp_interpolation", handle_set_color_ramp_interpolation)
    dispatcher.register_handler("get_color_ramp", handle_get_color_ramp)
