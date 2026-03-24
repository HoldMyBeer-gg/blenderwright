"""MCP tools for Blender materials and shading."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
    validate_color,
    validate_enum,
    validate_numeric_range,
    validate_file_path,
    validate_vector,
    ValidationError,
)

# Allowed Principled BSDF properties
ALLOWED_MATERIAL_PROPERTIES = {
    "metallic",
    "roughness",
    "specular_ior_level",
    "emission_strength",
    "alpha",
    "transmission_weight",
    "ior",
    "coat_weight",
    "coat_roughness",
    "sheen_weight",
    "sheen_roughness",
    "anisotropic",
    "anisotropic_rotation",
    "subsurface_weight",
    "emission_color",
}

# Allowed blend modes
ALLOWED_BLEND_MODES = {"OPAQUE", "CLIP", "HASHED", "BLEND"}

# Allowed image texture extensions
ALLOWED_IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".tga", ".tiff", ".tif",
    ".exr", ".hdr", ".webp",
}

# Allowed shader node types for add_shader_node
ALLOWED_SHADER_NODE_TYPES = {
    # Shader
    "ShaderNodeBsdfPrincipled", "ShaderNodeBsdfDiffuse", "ShaderNodeBsdfGlossy",
    "ShaderNodeBsdfGlass", "ShaderNodeBsdfTransparent", "ShaderNodeBsdfTranslucent",
    "ShaderNodeBsdfAnisotropic", "ShaderNodeBsdfToon", "ShaderNodeBsdfHair",
    "ShaderNodeEmission", "ShaderNodeMixShader", "ShaderNodeAddShader",
    "ShaderNodeSubsurfaceScattering", "ShaderNodeVolumeAbsorption",
    "ShaderNodeVolumePrincipled", "ShaderNodeVolumeScatter",
    # Input
    "ShaderNodeTexCoord", "ShaderNodeObjectInfo", "ShaderNodeValue",
    "ShaderNodeRGB", "ShaderNodeFresnel", "ShaderNodeLayerWeight",
    "ShaderNodeGeometry", "ShaderNodeAttribute", "ShaderNodeCameraData",
    "ShaderNodeLightPath", "ShaderNodeUVMap", "ShaderNodeTangent",
    # Texture
    "ShaderNodeTexImage", "ShaderNodeTexNoise", "ShaderNodeTexVoronoi",
    "ShaderNodeTexWave", "ShaderNodeTexGradient",
    "ShaderNodeTexBrick", "ShaderNodeTexChecker", "ShaderNodeTexEnvironment",
    "ShaderNodeTexMagic", "ShaderNodeTexSky",
    # Color
    "ShaderNodeMix", "ShaderNodeInvert", "ShaderNodeHueSaturation",
    "ShaderNodeBrightContrast", "ShaderNodeGamma", "ShaderNodeRGBCurve",
    # Vector
    "ShaderNodeMapping", "ShaderNodeNormal", "ShaderNodeNormalMap",
    "ShaderNodeBump", "ShaderNodeDisplacement", "ShaderNodeVectorMath",
    "ShaderNodeVectorRotate", "ShaderNodeVectorCurve",
    # Converter
    "ShaderNodeMath", "ShaderNodeValToRGB", "ShaderNodeRGBToBW",
    "ShaderNodeMapRange", "ShaderNodeClamp", "ShaderNodeCombineXYZ",
    "ShaderNodeSeparateXYZ", "ShaderNodeWavelength", "ShaderNodeBlackbody",
    # Output
    "ShaderNodeOutputMaterial", "ShaderNodeOutputWorld",
    # Blender 5.1+ nodes
    "ShaderNodeRaycast",
}


def _send_material_command(command: str, params: dict[str, Any] | None = None) -> Any:
    """Send a material command and handle errors."""
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def create_material(name: str) -> dict[str, Any]:
    """Create a new material with a Principled BSDF shader node.

    Args:
        name: Name for the new material.

    Returns:
        Confirmation dict with the created material name.
    """
    name = validate_object_name(name)
    return _send_material_command("create_material", {"name": name})


@mcp.tool()
def assign_material(object_name: str, material_name: str) -> dict[str, Any]:
    """Assign a material to an object.

    Args:
        object_name: Name of the target object.
        material_name: Name of the material to assign.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    material_name = validate_object_name(material_name)
    return _send_material_command("assign_material", {
        "object_name": object_name,
        "material_name": material_name,
    })


@mcp.tool()
def set_material_color(material_name: str, color: list) -> dict[str, Any]:
    """Set the base color of a material's Principled BSDF node.

    Args:
        material_name: Name of the material.
        color: RGBA color as a list of 4 floats (0.0-1.0). e.g. [1.0, 0.0, 0.0, 1.0] for red.

    Returns:
        Confirmation dict.
    """
    material_name = validate_object_name(material_name)
    color = validate_color(color)
    # Ensure RGBA
    if len(color) == 3:
        color = (*color, 1.0)
    return _send_material_command("set_material_color", {
        "material_name": material_name,
        "color": list(color),
    })


@mcp.tool()
def set_material_property(material_name: str, property: str, value: Any) -> dict[str, Any]:
    """Set a property on a material's Principled BSDF node.

    Args:
        material_name: Name of the material.
        property: Property to set. One of: metallic, roughness, specular_ior_level,
                  emission_strength, alpha, transmission_weight, ior, coat_weight,
                  coat_roughness, sheen_weight, sheen_roughness, anisotropic,
                  anisotropic_rotation, subsurface_weight, emission_color.
        value: The value to set. Float for most properties, list for color properties.

    Returns:
        Confirmation dict.
    """
    material_name = validate_object_name(material_name)
    validate_enum(property, ALLOWED_MATERIAL_PROPERTIES, name="property")

    # Validate numeric ranges for common properties
    if property in ("metallic", "roughness", "alpha", "transmission_weight",
                     "coat_weight", "coat_roughness", "sheen_weight",
                     "sheen_roughness", "anisotropic", "subsurface_weight",
                     "specular_ior_level"):
        validate_numeric_range(value, min_val=0.0, max_val=1.0, name=property)
    elif property == "ior":
        validate_numeric_range(value, min_val=0.0, max_val=100.0, name="ior")
    elif property == "emission_strength":
        validate_numeric_range(value, min_val=0.0, max_val=1000000.0, name="emission_strength")
    elif property == "anisotropic_rotation":
        validate_numeric_range(value, min_val=0.0, max_val=1.0, name="anisotropic_rotation")
    elif property == "emission_color":
        value = list(validate_color(value))

    return _send_material_command("set_material_property", {
        "material_name": material_name,
        "property": property,
        "value": value,
    })


@mcp.tool()
def create_principled_material(
    name: str,
    color: list = [0.8, 0.8, 0.8, 1.0],
    metallic: float = 0.0,
    roughness: float = 0.5,
    specular: float = 0.5,
    emission_strength: float = 0.0,
    emission_color: list = [1.0, 1.0, 1.0, 1.0],
    alpha: float = 1.0,
    transmission: float = 0.0,
    ior: float = 1.45,
) -> dict[str, Any]:
    """Create a fully configured Principled BSDF material in one call.

    Args:
        name: Name for the new material.
        color: Base color as RGBA list, default [0.8, 0.8, 0.8, 1.0].
        metallic: Metallic value 0.0-1.0, default 0.0.
        roughness: Roughness value 0.0-1.0, default 0.5.
        specular: Specular IOR level 0.0-1.0, default 0.5.
        emission_strength: Emission strength, default 0.0.
        emission_color: Emission color as RGBA list, default [1.0, 1.0, 1.0, 1.0].
        alpha: Alpha value 0.0-1.0, default 1.0.
        transmission: Transmission weight 0.0-1.0, default 0.0.
        ior: Index of refraction, default 1.45.

    Returns:
        Confirmation dict with material name and all set properties.
    """
    name = validate_object_name(name)
    color = list(validate_color(color))
    if len(color) == 3:
        color = color + [1.0]
    emission_color = list(validate_color(emission_color))
    if len(emission_color) == 3:
        emission_color = emission_color + [1.0]
    validate_numeric_range(metallic, min_val=0.0, max_val=1.0, name="metallic")
    validate_numeric_range(roughness, min_val=0.0, max_val=1.0, name="roughness")
    validate_numeric_range(specular, min_val=0.0, max_val=1.0, name="specular")
    validate_numeric_range(emission_strength, min_val=0.0, max_val=1000000.0, name="emission_strength")
    validate_numeric_range(alpha, min_val=0.0, max_val=1.0, name="alpha")
    validate_numeric_range(transmission, min_val=0.0, max_val=1.0, name="transmission")
    validate_numeric_range(ior, min_val=0.0, max_val=100.0, name="ior")

    return _send_material_command("create_principled_material", {
        "name": name,
        "color": color,
        "metallic": metallic,
        "roughness": roughness,
        "specular": specular,
        "emission_strength": emission_strength,
        "emission_color": emission_color,
        "alpha": alpha,
        "transmission": transmission,
        "ior": ior,
    })


@mcp.tool()
def add_texture_node(
    material_name: str,
    image_path: str,
    label: str = "Image Texture",
) -> dict[str, Any]:
    """Add an image texture node to a material and connect it to the Principled BSDF Base Color.

    Args:
        material_name: Name of the material.
        image_path: Absolute path to the image file. Must exist on disk.
        label: Label for the texture node, default "Image Texture".

    Returns:
        Confirmation dict.
    """
    material_name = validate_object_name(material_name)
    image_path = validate_file_path(image_path, allowed_extensions=ALLOWED_IMAGE_EXTENSIONS, must_exist=True)
    label = validate_object_name(label)

    return _send_material_command("add_texture_node", {
        "material_name": material_name,
        "image_path": image_path,
        "label": label,
    })


@mcp.tool()
def set_material_blend_mode(material_name: str, mode: str) -> dict[str, Any]:
    """Set the blend mode of a material (EEVEE).

    Args:
        material_name: Name of the material.
        mode: Blend mode. One of: OPAQUE, CLIP, HASHED, BLEND.

    Returns:
        Confirmation dict.
    """
    material_name = validate_object_name(material_name)
    validate_enum(mode, ALLOWED_BLEND_MODES, name="mode")

    return _send_material_command("set_material_blend_mode", {
        "material_name": material_name,
        "mode": mode,
    })


@mcp.tool()
def list_materials() -> list[dict[str, Any]]:
    """List all materials in the current Blender file.

    Returns:
        List of dicts with material name and user count.
    """
    return _send_material_command("list_materials")


@mcp.tool()
def delete_material(material_name: str) -> dict[str, Any]:
    """Delete a material by name.

    Args:
        material_name: Name of the material to delete.

    Returns:
        Confirmation dict.
    """
    material_name = validate_object_name(material_name)
    return _send_material_command("delete_material", {"material_name": material_name})


@mcp.tool()
def duplicate_material(material_name: str, new_name: str) -> dict[str, Any]:
    """Duplicate a material with a new name.

    Args:
        material_name: Name of the material to duplicate.
        new_name: Name for the duplicated material.

    Returns:
        Confirmation dict with the new material name.
    """
    material_name = validate_object_name(material_name)
    new_name = validate_object_name(new_name)
    return _send_material_command("duplicate_material", {
        "material_name": material_name,
        "new_name": new_name,
    })


def _validate_socket_name(name: object) -> None:
    """Validate that a socket name is a non-empty string."""
    if not isinstance(name, str) or len(name) == 0:
        raise ValidationError("socket name must be a non-empty string")


@mcp.tool()
def add_shader_node(
    material_name: str,
    node_type: str,
    location: list = [0, 0],
) -> dict[str, Any]:
    """Add a shader node to a material's node tree.

    Args:
        material_name: Name of the material.
        node_type: Blender shader node type (e.g. ShaderNodeBsdfPrincipled).
        location: Node location as [x, y], default [0, 0].

    Returns:
        Dict with material, node_name, and node_type.
    """
    material_name = validate_object_name(material_name)
    validate_enum(node_type, ALLOWED_SHADER_NODE_TYPES, name="node_type")
    location = validate_vector(location, size=2, name="location")

    return _send_material_command("add_shader_node", {
        "material_name": material_name,
        "node_type": node_type,
        "location": location,
    })


@mcp.tool()
def connect_shader_nodes(
    material_name: str,
    from_node: str,
    from_socket: str,
    to_node: str,
    to_socket: str,
) -> dict[str, Any]:
    """Connect two shader nodes in a material's node tree.

    Args:
        material_name: Name of the material.
        from_node: Name of the source node.
        from_socket: Name of the output socket on the source node.
        to_node: Name of the destination node.
        to_socket: Name of the input socket on the destination node.

    Returns:
        Confirmation dict.
    """
    material_name = validate_object_name(material_name)
    from_node = validate_object_name(from_node)
    to_node = validate_object_name(to_node)
    _validate_socket_name(from_socket)
    _validate_socket_name(to_socket)

    return _send_material_command("connect_shader_nodes", {
        "material_name": material_name,
        "from_node": from_node,
        "from_socket": from_socket,
        "to_node": to_node,
        "to_socket": to_socket,
    })


@mcp.tool()
def disconnect_shader_nodes(
    material_name: str,
    node_name: str,
    socket_name: str,
    is_input: bool = True,
) -> dict[str, Any]:
    """Disconnect all links from a specific socket on a shader node.

    Args:
        material_name: Name of the material.
        node_name: Name of the node.
        socket_name: Name of the socket to disconnect.
        is_input: If True, disconnect an input socket; otherwise an output socket.

    Returns:
        Confirmation dict.
    """
    material_name = validate_object_name(material_name)
    node_name = validate_object_name(node_name)
    _validate_socket_name(socket_name)

    return _send_material_command("disconnect_shader_nodes", {
        "material_name": material_name,
        "node_name": node_name,
        "socket_name": socket_name,
        "is_input": is_input,
    })


@mcp.tool()
def remove_shader_node(material_name: str, node_name: str) -> dict[str, Any]:
    """Remove a shader node from a material's node tree.

    Args:
        material_name: Name of the material.
        node_name: Name of the node to remove.

    Returns:
        Confirmation dict.
    """
    material_name = validate_object_name(material_name)
    node_name = validate_object_name(node_name)

    return _send_material_command("remove_shader_node", {
        "material_name": material_name,
        "node_name": node_name,
    })


@mcp.tool()
def get_node_tree(material_name: str) -> dict[str, Any]:
    """Get the full node tree of a material (all nodes and links).

    Args:
        material_name: Name of the material.

    Returns:
        Dict with nodes list and links list.
    """
    material_name = validate_object_name(material_name)
    return _send_material_command("get_node_tree", {
        "material_name": material_name,
    })
