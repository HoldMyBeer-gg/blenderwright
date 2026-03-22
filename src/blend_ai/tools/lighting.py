"""MCP tools for Blender lighting operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
    validate_color,
    validate_enum,
    validate_numeric_range,
    validate_vector,
    validate_file_path,
    ValidationError,
)

# Allowed light types
ALLOWED_LIGHT_TYPES = {"POINT", "SUN", "SPOT", "AREA"}

# Allowed light properties
ALLOWED_LIGHT_PROPERTIES = {
    "energy",
    "color",
    "shadow_soft_size",
    "spot_size",
    "spot_blend",
    "area_size",
    "area_size_y",
    "use_shadow",
    "angle",
    "specular_factor",
    "diffuse_factor",
    "volume_factor",
}

# Allowed light rig types
ALLOWED_RIG_TYPES = {"THREE_POINT", "STUDIO", "RIM", "OUTDOOR"}

# HDRI extensions
ALLOWED_HDRI_EXTENSIONS = {".hdr", ".exr", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def _send_light_command(command: str, params: dict[str, Any] | None = None) -> Any:
    """Send a lighting command and handle errors."""
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def create_light(
    type: str,
    name: str = "",
    location: list = [0, 0, 0],
    energy: float = 1000.0,
    color: list = [1.0, 1.0, 1.0],
) -> dict[str, Any]:
    """Create a new light in the scene.

    Args:
        type: Light type. One of: POINT, SUN, SPOT, AREA.
        name: Optional name for the light.
        location: XYZ location as [x, y, z], default [0, 0, 0].
        energy: Light energy/power, default 1000.
        color: RGB color as [r, g, b], default [1.0, 1.0, 1.0].

    Returns:
        Confirmation dict with light name and properties.
    """
    validate_enum(type, ALLOWED_LIGHT_TYPES, name="type")
    if name:
        name = validate_object_name(name)
    location = list(validate_vector(location, size=3, name="location"))
    validate_numeric_range(energy, min_val=0.0, max_val=10000000.0, name="energy")
    color = list(validate_color(color))[:3]

    return _send_light_command("create_light", {
        "type": type,
        "name": name,
        "location": location,
        "energy": energy,
        "color": color,
    })


@mcp.tool()
def set_light_property(name: str, property: str, value: Any) -> dict[str, Any]:
    """Set a property on a light object.

    Args:
        name: Name of the light object.
        property: Property to set. One of: energy, color, shadow_soft_size, spot_size,
                  spot_blend, area_size, area_size_y, use_shadow, angle,
                  specular_factor, diffuse_factor, volume_factor.
        value: The value to set. Type depends on the property.

    Returns:
        Confirmation dict.
    """
    name = validate_object_name(name)
    validate_enum(property, ALLOWED_LIGHT_PROPERTIES, name="property")

    # Validate specific properties
    if property == "energy":
        validate_numeric_range(value, min_val=0.0, max_val=10000000.0, name="energy")
    elif property == "color":
        value = list(validate_color(value))[:3]
    elif property in ("shadow_soft_size", "area_size", "area_size_y"):
        validate_numeric_range(value, min_val=0.0, max_val=1000.0, name=property)
    elif property == "spot_size":
        validate_numeric_range(value, min_val=0.0, max_val=3.14159, name="spot_size")
    elif property == "spot_blend":
        validate_numeric_range(value, min_val=0.0, max_val=1.0, name="spot_blend")
    elif property == "angle":
        validate_numeric_range(value, min_val=0.0, max_val=3.14159, name="angle")
    elif property in ("specular_factor", "diffuse_factor", "volume_factor"):
        validate_numeric_range(value, min_val=0.0, max_val=1.0, name=property)
    elif property == "use_shadow":
        if not isinstance(value, bool):
            raise ValidationError("use_shadow must be a boolean")

    return _send_light_command("set_light_property", {
        "name": name,
        "property": property,
        "value": value,
    })


@mcp.tool()
def set_world_background(
    color: list | None = None,
    hdri_path: str | None = None,
    strength: float = 1.0,
) -> dict[str, Any]:
    """Set the world background to a solid color or HDRI environment map.

    Args:
        color: RGB color as [r, g, b] for solid background. Mutually exclusive with hdri_path.
        hdri_path: Absolute path to an HDRI image file. Mutually exclusive with color.
        strength: Background strength/intensity, default 1.0.

    Returns:
        Confirmation dict.
    """
    if color is None and hdri_path is None:
        raise ValidationError("Must provide either 'color' or 'hdri_path'")
    if color is not None and hdri_path is not None:
        raise ValidationError("Cannot set both 'color' and 'hdri_path' at the same time")

    validate_numeric_range(strength, min_val=0.0, max_val=1000.0, name="strength")

    params: dict[str, Any] = {"strength": strength}
    if color is not None:
        params["color"] = list(validate_color(color))[:3]
    if hdri_path is not None:
        params["hdri_path"] = validate_file_path(hdri_path, allowed_extensions=ALLOWED_HDRI_EXTENSIONS, must_exist=True)

    return _send_light_command("set_world_background", params)


@mcp.tool()
def create_light_rig(
    type: str,
    target: str = "",
    intensity: float = 1000.0,
) -> dict[str, Any]:
    """Create a pre-built lighting rig (multiple lights arranged for common setups).

    Args:
        type: Rig type. One of: THREE_POINT, STUDIO, RIM, OUTDOOR.
        target: Optional name of the object the rig should point at.
        intensity: Overall intensity of the lights, default 1000.

    Returns:
        Confirmation dict with names of all created lights.
    """
    validate_enum(type, ALLOWED_RIG_TYPES, name="type")
    if target:
        target = validate_object_name(target)
    validate_numeric_range(intensity, min_val=0.0, max_val=10000000.0, name="intensity")

    return _send_light_command("create_light_rig", {
        "type": type,
        "target": target,
        "intensity": intensity,
    })


@mcp.tool()
def list_lights() -> list[dict[str, Any]]:
    """List all light objects in the scene.

    Returns:
        List of dicts with light name, type, energy, color, and location.
    """
    return _send_light_command("list_lights")


@mcp.tool()
def delete_light(name: str) -> dict[str, Any]:
    """Delete a light object from the scene.

    Args:
        name: Name of the light object to delete.

    Returns:
        Confirmation dict.
    """
    name = validate_object_name(name)
    return _send_light_command("delete_light", {"name": name})


@mcp.tool()
def set_shadow_settings(
    name: str,
    use_shadow: bool = True,
    shadow_soft_size: float = 0.25,
) -> dict[str, Any]:
    """Configure shadow settings for a light.

    Args:
        name: Name of the light object.
        use_shadow: Whether to enable shadows, default True.
        shadow_soft_size: Soft shadow radius, default 0.25.

    Returns:
        Confirmation dict.
    """
    name = validate_object_name(name)
    if not isinstance(use_shadow, bool):
        raise ValidationError("use_shadow must be a boolean")
    validate_numeric_range(shadow_soft_size, min_val=0.0, max_val=100.0, name="shadow_soft_size")

    return _send_light_command("set_shadow_settings", {
        "name": name,
        "use_shadow": use_shadow,
        "shadow_soft_size": shadow_soft_size,
    })
