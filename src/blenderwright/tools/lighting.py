"""MCP tools for Blender lighting operations."""

import math
from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_object_name,
    validate_new_name,
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

# HDRIs bundled with Blender 5.2 (datafiles/studiolights/world)
ALLOWED_BUILTIN_HDRIS = {
    "city", "courtyard", "forest", "interior", "night", "studio", "sunrise", "sunset",
}
ALLOWED_SKY_TYPES = {"MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "PREETHAM", "HOSEK_WILKIE"}


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
        name = validate_new_name(name)
    location = list(validate_vector(location, size=3, name="location"))
    energy = validate_numeric_range(energy, min_val=0.0, max_val=10000000.0, name="energy")
    color = list(validate_color(color))[:3]

    return _send_light_command("create_light", {
        "type": type,
        "name": name,
        "location": location,
        "energy": energy,
        "color": color,
    })


@mcp.tool()
def set_light_property(object_name: str, property: str, value: Any) -> dict[str, Any]:
    """Set a property on a light object.

    Args:
        object_name: Name of the light object.
        property: Property to set. One of: energy, color, shadow_soft_size, spot_size,
                  spot_blend, area_size, area_size_y, use_shadow, angle,
                  specular_factor, diffuse_factor, volume_factor.
        value: The value to set. Type depends on the property.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_enum(property, ALLOWED_LIGHT_PROPERTIES, name="property")

    # Validate specific properties
    if property == "energy":
        value = validate_numeric_range(value, min_val=0.0, max_val=10000000.0, name="energy")
    elif property == "color":
        value = list(validate_color(value))[:3]
    elif property in ("shadow_soft_size", "area_size", "area_size_y"):
        value = validate_numeric_range(value, min_val=0.0, max_val=1000.0, name=property)
    elif property == "spot_size":
        value = validate_numeric_range(value, min_val=0.0, max_val=math.pi, name="spot_size")
    elif property == "spot_blend":
        value = validate_numeric_range(value, min_val=0.0, max_val=1.0, name="spot_blend")
    elif property == "angle":
        value = validate_numeric_range(value, min_val=0.0, max_val=math.pi, name="angle")
    elif property in ("specular_factor", "diffuse_factor", "volume_factor"):
        value = validate_numeric_range(value, min_val=0.0, max_val=1.0, name=property)
    elif property == "use_shadow":
        if not isinstance(value, bool):
            raise ValidationError("use_shadow must be a boolean")

    return _send_light_command("set_light_property", {
        "name": object_name,
        "property": property,
        "value": value,
    })


@mcp.tool()
def set_world_background(
    color: list | None = None,
    hdri_path: str | None = None,
    builtin_hdri: str | None = None,
    strength: float = 1.0,
    rotation: float = 0.0,
) -> dict[str, Any]:
    """Set the world background to a solid colour or an HDRI environment.

    An HDRI lights the whole scene and gives metal and glass something to
    reflect; without one, metals look dull. Give exactly one of color,
    hdri_path or builtin_hdri.

    Args:
        color: RGB colour [r, g, b] for a plain background.
        hdri_path: Absolute path to an HDRI image (.hdr, .exr, ...).
        builtin_hdri: One of the HDRIs that ship with Blender: city,
            courtyard, forest, interior, night, studio, sunrise, sunset.
        strength: Background strength, 0 to 1000, default 1.0.
        rotation: HDRI turn around the vertical axis in radians, to move
            where the light comes from. -6.283 to 6.283.

    Returns:
        Confirmation dict.
    """
    sources = [x is not None for x in (color, hdri_path, builtin_hdri)]
    if not any(sources):
        raise ValidationError("Must provide either 'color', 'hdri_path' or 'builtin_hdri'")
    if sum(sources) > 1:
        raise ValidationError("Give only one of 'color', 'hdri_path' and 'builtin_hdri'")

    strength = validate_numeric_range(strength, min_val=0.0, max_val=1000.0, name="strength")

    params: dict[str, Any] = {"strength": strength}
    if color is not None:
        params["color"] = list(validate_color(color))[:3]
        if rotation:
            raise ValidationError("rotation only applies to an HDRI background")
    if hdri_path is not None:
        params["hdri_path"] = validate_file_path(hdri_path, allowed_extensions=ALLOWED_HDRI_EXTENSIONS, must_exist=True)
    if builtin_hdri is not None:
        params["builtin_hdri"] = validate_enum(builtin_hdri, ALLOWED_BUILTIN_HDRIS,
                                               name="builtin_hdri")
    if rotation:
        params["rotation"] = validate_numeric_range(rotation, min_val=-math.tau,
                                                    max_val=math.tau, name="rotation")

    return _send_light_command("set_world_background", params)


@mcp.tool()
def set_world_sky(
    sky_type: str = "MULTIPLE_SCATTERING",
    sun_elevation: float = 0.2618,
    sun_rotation: float = 0.0,
    sun_intensity: float = 1.0,
    sun_disc: bool = True,
    altitude: float = 100.0,
    air_density: float = 1.0,
    aerosol_density: float = 1.0,
    ozone_density: float = 1.0,
    strength: float = 1.0,
) -> dict[str, Any]:
    """Light the scene with a physically based procedural sky and sun.

    Realistic daylight for any time of day with no image file. Low sun
    elevation gives golden hour; negative gives dusk. Pair with AgX colour
    management (set_color_management) for natural results.

    Args:
        sky_type: MULTIPLE_SCATTERING (most realistic, new in 5.0),
            SINGLE_SCATTERING, PREETHAM or HOSEK_WILKIE.
        sun_elevation: Sun height above the horizon in radians, -1.571 to
            1.571. 0.26 (15 degrees) is mid-morning; 0.05 golden hour.
        sun_rotation: Sun direction around the vertical axis in radians.
        sun_intensity: Sun brightness multiplier, 0 to 1000.
        sun_disc: Show the sun itself in the sky.
        altitude: Viewer height in metres, 0 to 100000.
        air_density: Air molecules, 0 to 10. Higher is bluer.
        aerosol_density: Dust and haze, 0 to 10. Higher is hazier and warmer.
        ozone_density: Ozone, 0 to 10. Affects the blue at dusk.
        strength: Overall sky brightness, 0 to 1000.

    Returns:
        Dict with the sky settings applied.
    """
    def ranged(value, lo, hi, name):
        return validate_numeric_range(value, min_val=lo, max_val=hi, name=name)

    return _send_light_command("set_world_sky", {
        "sky_type": validate_enum(sky_type, ALLOWED_SKY_TYPES, name="sky_type"),
        "sun_elevation": ranged(sun_elevation, -math.pi / 2, math.pi / 2, "sun_elevation"),
        "sun_rotation": ranged(sun_rotation, -math.tau, math.tau, "sun_rotation"),
        "sun_intensity": ranged(sun_intensity, 0.0, 1000.0, "sun_intensity"),
        "sun_disc": bool(sun_disc),
        "altitude": ranged(altitude, 0.0, 100000.0, "altitude"),
        "air_density": ranged(air_density, 0.0, 10.0, "air_density"),
        "aerosol_density": ranged(aerosol_density, 0.0, 10.0, "aerosol_density"),
        "ozone_density": ranged(ozone_density, 0.0, 10.0, "ozone_density"),
        "strength": ranged(strength, 0.0, 1000.0, "strength"),
    })


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
    intensity = validate_numeric_range(intensity, min_val=0.0, max_val=10000000.0, name="intensity")

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
def delete_light(object_name: str) -> dict[str, Any]:
    """Delete a light object from the scene.

    Args:
        object_name: Name of the light object to delete.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    return _send_light_command("delete_light", {"name": object_name})


@mcp.tool()
def set_shadow_settings(
    object_name: str,
    use_shadow: bool = True,
    shadow_soft_size: float = 0.25,
) -> dict[str, Any]:
    """Configure shadow settings for a light.

    Args:
        object_name: Name of the light object.
        use_shadow: Whether to enable shadows, default True.
        shadow_soft_size: Soft shadow radius, default 0.25.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    if not isinstance(use_shadow, bool):
        raise ValidationError("use_shadow must be a boolean")
    shadow_soft_size = validate_numeric_range(shadow_soft_size, min_val=0.0, max_val=100.0, name="shadow_soft_size")

    return _send_light_command("set_shadow_settings", {
        "name": object_name,
        "use_shadow": use_shadow,
        "shadow_soft_size": shadow_soft_size,
    })
