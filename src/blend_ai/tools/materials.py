"""MCP tools for Blender materials and shading."""

import re
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

# Node-level properties that may be set via set_shader_node_property.
# These are the enum/bool/float attributes that live on the node itself
# rather than on one of its input sockets.
ALLOWED_SHADER_NODE_PROPERTIES = {
    # Math / Mix / Map Range
    "operation", "use_clamp", "blend_type", "data_type", "clamp",
    "clamp_factor", "clamp_result", "interpolation_type", "factor_mode",
    # Noise / Voronoi / Wave / Gradient / Brick / Musgrave
    "noise_dimensions", "noise_type", "normalize",
    "voronoi_dimensions", "feature", "distance",
    "wave_type", "wave_profile", "bands_direction", "rings_direction",
    "gradient_type", "offset", "offset_frequency", "squash", "squash_frequency",
    "turbulence_depth",
    # Image / environment texture
    "interpolation", "projection", "extension",
    # Vector / mapping / normal
    "vector_type", "rotation_type", "invert", "space", "uv_map",
    "convert_from", "convert_to", "mode", "component", "axis",
    # Attribute / UV / object info
    "attribute_name", "attribute_type", "from_instancer",
    # Shader distributions
    "distribution", "subsurface_method",
    # Colour ramp element interpolation lives on the ramp, see the ramp tools.
}

# Maximum length and permitted charset for string property values. Blender
# enum identifiers and datablock names never need anything outside this set,
# so anything else is rejected rather than forwarded.
MAX_PROPERTY_VALUE_LENGTH = 64
SAFE_PROPERTY_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9_. -]+$")

ALLOWED_COLOR_RAMP_INTERPOLATIONS = {
    "EASE", "CARDINAL", "LINEAR", "B_SPLINE", "CONSTANT",
}
ALLOWED_COLOR_RAMP_COLOR_MODES = {"RGB", "HSV", "HSL"}

# Procedural patterns that native shader nodes reproduce.
# Notably absent: runes. Stamping discrete glyphs at random positions is not
# expressible in the shader graph and needs a raster path instead.
PROCEDURAL_PATTERNS = {
    "gradient", "noise", "cloud", "voronoi", "veins", "scales",
    "stripes", "wood", "marble", "weave", "plasma", "fire", "sparks",
}

PROCEDURAL_PATTERN_DESCRIPTIONS = {
    "gradient": "Smooth linear ramp. Base for skies, fades, and masks.",
    "noise": "Fractal noise. General-purpose surface variation and grunge.",
    "cloud": "Soft billowing noise. Skies, smoke, vapour.",
    "voronoi": "Cellular chunks. Stone, cracked plates, organic cells.",
    "veins": "Voronoi distance-to-edge. Cracks, leaf veins, dry riverbeds.",
    "scales": "Offset cellular grid. Reptile scales, fish, armour plating.",
    "stripes": "Hard or soft banding. Fabric, warning markings, ribbing.",
    "wood": "Distorted rings. Timber grain, tree cross-sections.",
    "marble": "Turbulent banding. Marble, swirled stone, oil-on-water.",
    "weave": "Crossed waves. Woven cloth, baskets, mesh.",
    "plasma": "Layered noise into a wide colour sweep. Energy, magic, heat.",
    "fire": "Vertically-masked noise into a heat ramp. Flame, lava, embers.",
    "sparks": "Sparse bright points. Embers, glints, star fields.",
}

# Patterns that need real pixels because they place discrete marks. Kept
# disjoint from PROCEDURAL_PATTERNS: anything a shader node can express
# belongs there instead, where it stays resolution-independent.
RASTER_PATTERNS = {"runes"}

MAX_RASTER_SIZE = 2048
MAX_RASTER_COUNT = 512

# Blender's Noise Texture caps Detail at 15.
MAX_PROCEDURAL_DETAIL = 15.0
MAX_PROCEDURAL_SCALE = 10000.0
# A colour ramp holds at most 32 stops.
MAX_PROCEDURAL_COLORS = 32


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


def _validate_socket_ref(socket: object) -> str | int:
    """Validate a socket reference: either a name or a zero-based index.

    Index form exists because socket names are not unique — a Math node has
    two inputs both named 'Value', and only the index can tell them apart.
    """
    if isinstance(socket, bool):
        raise ValidationError("socket must be a name or a non-negative index")
    if isinstance(socket, int):
        if socket < 0:
            raise ValidationError("socket index must be >= 0")
        return socket
    if isinstance(socket, str) and len(socket) > 0:
        return socket
    raise ValidationError("socket must be a non-empty name or a non-negative index")


def _validate_socket_value(value: object) -> Any:
    """Validate a socket default value: number, boolean, or 2-4 component vector."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)):
        if len(value) not in (2, 3, 4):
            raise ValidationError(
                "vector/color value must have 2, 3, or 4 components"
            )
        for i, component in enumerate(value):
            if isinstance(component, bool) or not isinstance(component, (int, float)):
                raise ValidationError(f"value component {i} must be a number")
        return list(value)
    raise ValidationError(
        "value must be a number, boolean, or a 2-4 component list of numbers"
    )


def _validate_property_value(value: object) -> Any:
    """Validate a node property value: string (charset-limited), number, or boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        if not 1 <= len(value) <= MAX_PROPERTY_VALUE_LENGTH:
            raise ValidationError(
                f"property value must be 1-{MAX_PROPERTY_VALUE_LENGTH} characters"
            )
        if SAFE_PROPERTY_VALUE_PATTERN.match(value) is None:
            raise ValidationError(
                "property value may only contain letters, digits, spaces, "
                "underscores, dots, and hyphens"
            )
        return value
    raise ValidationError("property value must be a string, number, or boolean")


def _validate_element_index(index: object) -> int:
    """Validate a zero-based colour ramp element index."""
    if isinstance(index, bool) or not isinstance(index, int):
        raise ValidationError("index must be an integer")
    if index < 0:
        raise ValidationError("index must be >= 0")
    return index


def _validate_ramp_color(color: list | tuple) -> list[float]:
    """Validate a ramp colour, padding RGB to RGBA so the wire format is uniform."""
    validated = validate_color(color)
    if len(validated) == 3:
        validated = (*validated, 1.0)
    return list(validated)


@mcp.tool()
def set_shader_node_input(
    material_name: str,
    node_name: str,
    socket: str | int,
    value: float | bool | list,
) -> dict[str, Any]:
    """Set the default value of an unconnected input socket on a shader node.

    This is how you dial in a procedural texture: Noise 'Scale' and 'Detail',
    Mapping 'Scale' and 'Rotation', a Principled BSDF 'Roughness', and so on.
    A socket that has a link into it ignores its default value, so disconnect
    it first if you want the default to take effect.

    Args:
        material_name: Name of the material.
        node_name: Name of the node.
        socket: Socket name, or a zero-based index. Use the index when names
            are ambiguous — a Math node has two inputs both called 'Value'.
        value: A number, a boolean, or a 2-4 component list for vectors and
            colors (colors are RGBA).

    Returns:
        Dict with the node, socket, and the value that was applied.
    """
    material_name = validate_object_name(material_name)
    node_name = validate_object_name(node_name)
    socket = _validate_socket_ref(socket)
    value = _validate_socket_value(value)

    return _send_material_command("set_shader_node_input", {
        "material_name": material_name,
        "node_name": node_name,
        "socket": socket,
        "value": value,
    })


@mcp.tool()
def set_shader_node_property(
    material_name: str,
    node_name: str,
    property: str,
    value: str | float | bool,
) -> dict[str, Any]:
    """Set a node-level property (not a socket) on a shader node.

    These are the dropdowns and checkboxes on the node body rather than its
    input sockets: Math 'operation', Mix 'blend_type', Voronoi 'feature'
    (use 'DISTANCE_TO_EDGE' for vein and crack patterns), Wave 'wave_type'
    and 'bands_direction', Noise 'noise_dimensions'.

    Args:
        material_name: Name of the material.
        node_name: Name of the node.
        property: Property name. Must be one of the allowed node properties.
        value: String enum identifier, number, or boolean.

    Returns:
        Dict with the node, property, and the value that was applied.
    """
    material_name = validate_object_name(material_name)
    node_name = validate_object_name(node_name)
    validate_enum(property, ALLOWED_SHADER_NODE_PROPERTIES, name="property")
    value = _validate_property_value(value)

    return _send_material_command("set_shader_node_property", {
        "material_name": material_name,
        "node_name": node_name,
        "property": property,
        "value": value,
    })


@mcp.tool()
def add_color_ramp_element(
    material_name: str,
    node_name: str,
    position: float,
    color: list,
) -> dict[str, Any]:
    """Add a colour stop to a ColorRamp (ShaderNodeValToRGB) node.

    A new ramp starts with two stops, black at 0.0 and white at 1.0. Add
    stops to shape a gradient: fire needs dark red, orange, yellow, white
    bunched toward the top; rust needs a hard break between metal and oxide.

    Args:
        material_name: Name of the material.
        node_name: Name of the ColorRamp node.
        position: Stop position along the ramp, 0.0 to 1.0.
        color: RGB or RGBA color, components 0.0 to 1.0. RGB gains alpha 1.0.

    Returns:
        Dict with the new element's index, position, and color.
    """
    material_name = validate_object_name(material_name)
    node_name = validate_object_name(node_name)
    validate_numeric_range(position, min_val=0.0, max_val=1.0, name="position")
    color = _validate_ramp_color(color)

    return _send_material_command("add_color_ramp_element", {
        "material_name": material_name,
        "node_name": node_name,
        "position": position,
        "color": color,
    })


@mcp.tool()
def remove_color_ramp_element(
    material_name: str,
    node_name: str,
    index: int,
) -> dict[str, Any]:
    """Remove a colour stop from a ColorRamp node.

    Blender requires at least one stop to remain; removing the last one fails.

    Args:
        material_name: Name of the material.
        node_name: Name of the ColorRamp node.
        index: Zero-based index of the stop to remove.

    Returns:
        Dict with the removed index and the remaining element count.
    """
    material_name = validate_object_name(material_name)
    node_name = validate_object_name(node_name)
    index = _validate_element_index(index)

    return _send_material_command("remove_color_ramp_element", {
        "material_name": material_name,
        "node_name": node_name,
        "index": index,
    })


@mcp.tool()
def set_color_ramp_element(
    material_name: str,
    node_name: str,
    index: int,
    position: float | None = None,
    color: list | None = None,
) -> dict[str, Any]:
    """Move or recolor an existing ColorRamp stop.

    At least one of position or color must be given. Moving a stop past a
    neighbour reorders the ramp, so indices may shift after this call — read
    the ramp back with get_color_ramp if you need certainty.

    Args:
        material_name: Name of the material.
        node_name: Name of the ColorRamp node.
        index: Zero-based index of the stop to edit.
        position: New position, 0.0 to 1.0. Omit to leave unchanged.
        color: New RGB or RGBA color. Omit to leave unchanged.

    Returns:
        Dict with the element's resulting position and color.
    """
    material_name = validate_object_name(material_name)
    node_name = validate_object_name(node_name)
    index = _validate_element_index(index)

    if position is None and color is None:
        raise ValidationError("at least one of position or color must be provided")

    params: dict[str, Any] = {
        "material_name": material_name,
        "node_name": node_name,
        "index": index,
    }
    if position is not None:
        validate_numeric_range(position, min_val=0.0, max_val=1.0, name="position")
        params["position"] = position
    if color is not None:
        params["color"] = _validate_ramp_color(color)

    return _send_material_command("set_color_ramp_element", params)


@mcp.tool()
def set_color_ramp_interpolation(
    material_name: str,
    node_name: str,
    interpolation: str,
    color_mode: str = "",
) -> dict[str, Any]:
    """Set how a ColorRamp blends between its stops.

    'CONSTANT' gives hard-edged bands with no blending, which is what turns a
    noise or voronoi texture into discrete regions: scale plates, cracked mud,
    stylised cel shading. 'EASE' and 'B_SPLINE' give softer falloff than
    'LINEAR'. Set color_mode to 'HSV' to sweep through hues between two stops
    rather than blending through grey.

    Args:
        material_name: Name of the material.
        node_name: Name of the ColorRamp node.
        interpolation: One of EASE, CARDINAL, LINEAR, B_SPLINE, CONSTANT.
        color_mode: Optional. One of RGB, HSV, HSL. Omit to leave unchanged.

    Returns:
        Dict with the applied interpolation and color mode.
    """
    material_name = validate_object_name(material_name)
    node_name = validate_object_name(node_name)
    validate_enum(
        interpolation, ALLOWED_COLOR_RAMP_INTERPOLATIONS, name="interpolation"
    )

    params: dict[str, Any] = {
        "material_name": material_name,
        "node_name": node_name,
        "interpolation": interpolation,
    }
    if color_mode:
        validate_enum(
            color_mode, ALLOWED_COLOR_RAMP_COLOR_MODES, name="color_mode"
        )
        params["color_mode"] = color_mode

    return _send_material_command("set_color_ramp_interpolation", params)


@mcp.tool()
def get_color_ramp(material_name: str, node_name: str) -> dict[str, Any]:
    """Read every stop on a ColorRamp node.

    Use this before editing to learn the current indices and positions, since
    add and move operations reorder stops.

    Args:
        material_name: Name of the material.
        node_name: Name of the ColorRamp node.

    Returns:
        Dict with elements (index, position, color), interpolation, color_mode.
    """
    material_name = validate_object_name(material_name)
    node_name = validate_object_name(node_name)

    return _send_material_command("get_color_ramp", {
        "material_name": material_name,
        "node_name": node_name,
    })


@mcp.tool()
def create_procedural_material(
    name: str,
    pattern: str,
    scale: float = 5.0,
    detail: float = 2.0,
    distortion: float = 0.0,
    roughness: float = 0.5,
    metallic: float = 0.0,
    colors: list | None = None,
    banded: bool = False,
    connect_to_bsdf: bool = True,
) -> dict[str, Any]:
    """Build a complete procedural texture as a material, in one call.

    Prefer this over hand-wiring texture nodes. It creates the full graph —
    coordinates, mapping, the pattern's texture nodes, a tuned colour ramp,
    and the Principled BSDF — and returns the node names so you can adjust
    anything afterwards with set_shader_node_input or the colour ramp tools.

    Procedural beats image textures here: no files, no UV unwrap needed, and
    it stays sharp at any camera distance.

    Call list_procedural_patterns() to see what each pattern looks like.

    Args:
        name: Name for the new material.
        pattern: One of the supported patterns, e.g. 'fire', 'wood', 'veins'.
        scale: Feature size. Lower is bigger and broader, higher is finer and
            busier. 5.0 is a sensible default; try 1-3 for large forms and
            20+ for fine detail.
        detail: Fractal octaves, 0-15. Higher adds finer sub-detail at the
            cost of render time. Applies to noise, cloud, wood, marble,
            plasma and fire. The cellular patterns (voronoi, veins, scales,
            sparks), stripes, weave and gradient have no detail socket and
            ignore it.
        distortion: Warps the pattern. Small values (0.5-2.0) make wood and
            marble look organic rather than machine-perfect. Applies to
            noise, cloud, stripes, wood, marble, plasma and fire. The
            cellular patterns, weave and gradient ignore it.
        roughness: Surface roughness 0-1 for the Principled BSDF.
        metallic: Metallic 0-1 for the Principled BSDF.
        colors: Optional list of RGB or RGBA colours for the ramp, in order.
            Omit to use the pattern's own tuned palette.
        banded: Use CONSTANT ramp interpolation, giving hard-edged bands
            instead of smooth blending. Turns noise into discrete regions:
            scale plates, cracked mud, cel shading.
        connect_to_bsdf: Wire the result into the Principled BSDF base colour
            so the material renders immediately. Set False to leave the
            pattern subtree unconnected for manual wiring.

    Returns:
        Dict with the material name, the created node names, and
        ignored_params listing any arguments this pattern could not use.
    """
    name = validate_object_name(name)
    validate_enum(pattern, PROCEDURAL_PATTERNS, name="pattern")
    validate_numeric_range(
        scale, min_val=0.0001, max_val=MAX_PROCEDURAL_SCALE, name="scale"
    )
    validate_numeric_range(
        detail, min_val=0.0, max_val=MAX_PROCEDURAL_DETAIL, name="detail"
    )
    validate_numeric_range(distortion, min_val=0.0, max_val=1000.0, name="distortion")
    validate_numeric_range(roughness, min_val=0.0, max_val=1.0, name="roughness")
    validate_numeric_range(metallic, min_val=0.0, max_val=1.0, name="metallic")

    params: dict[str, Any] = {
        "name": name,
        "pattern": pattern,
        "scale": scale,
        "detail": detail,
        "distortion": distortion,
        "roughness": roughness,
        "metallic": metallic,
        "banded": bool(banded),
        "connect_to_bsdf": bool(connect_to_bsdf),
    }

    if colors is not None:
        if not isinstance(colors, (list, tuple)):
            raise ValidationError("colors must be a list of colours")
        if not 1 <= len(colors) <= MAX_PROCEDURAL_COLORS:
            raise ValidationError(
                f"colors must contain 1-{MAX_PROCEDURAL_COLORS} entries"
            )
        params["colors"] = [_validate_ramp_color(c) for c in colors]

    return _send_material_command("create_procedural_material", params)


@mcp.tool()
def create_raster_texture(
    name: str,
    pattern: str,
    size: int = 512,
    count: int = 12,
    seed: int = 0,
    foreground: list | None = None,
    background: list | None = None,
) -> dict[str, Any]:
    """Generate an image texture for patterns shader nodes cannot express.

    Use this only for patterns that place discrete marks. Shader nodes
    evaluate a function per point and have no way to say "draw a glyph here,
    then another over there", so runes need real pixels. Everything else
    should go through create_procedural_material, which stays sharp at any
    resolution.

    The image is packed into the blend file. No file is written to disk.

    Args:
        name: Name for the generated image datablock.
        pattern: A raster pattern. Currently 'runes'.
        size: Pixel width and height, up to 2048. Cost grows with the square.
        count: How many marks to stamp. 0 leaves a blank field.
        seed: Change for a different arrangement; the same seed always
            reproduces the same image.
        foreground: RGB or RGBA colour of the marks.
        background: RGB or RGBA colour behind them.

    Returns:
        Dict with the image name, size, and mark count.
    """
    name = validate_object_name(name)
    validate_enum(pattern, RASTER_PATTERNS, name="pattern")

    if isinstance(size, bool) or not isinstance(size, int):
        raise ValidationError("size must be an integer")
    validate_numeric_range(size, min_val=1, max_val=MAX_RASTER_SIZE, name="size")

    if isinstance(count, bool) or not isinstance(count, int):
        raise ValidationError("count must be an integer")
    validate_numeric_range(count, min_val=0, max_val=MAX_RASTER_COUNT, name="count")

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValidationError("seed must be an integer")
    validate_numeric_range(seed, min_val=0, max_val=2**31 - 1, name="seed")

    if foreground is None:
        foreground = [0.4, 0.8, 1.0, 1.0]
    if background is None:
        background = [0.02, 0.01, 0.06, 1.0]

    return _send_material_command("create_raster_texture", {
        "name": name,
        "pattern": pattern,
        "size": size,
        "count": count,
        "seed": seed,
        "foreground": _validate_ramp_color(foreground),
        "background": _validate_ramp_color(background),
    })


@mcp.tool()
def list_procedural_patterns() -> dict[str, Any]:
    """List every procedural pattern with a description of what it looks like.

    Read this before calling create_procedural_material so you pick a pattern
    that matches the surface you are trying to make.

    Returns:
        Dict with the sorted pattern names and a description of each.
    """
    return {
        "patterns": sorted(PROCEDURAL_PATTERNS),
        "descriptions": dict(PROCEDURAL_PATTERN_DESCRIPTIONS),
    }
