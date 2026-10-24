"""MCP tools for Blender rendering operations."""

from typing import Any

from blenderwright.connection import BlenderConnection
from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_enum,
    validate_numeric_range,
    validate_file_path,
    validate_output_path,
    default_output_path,
    ValidationError,
    MAX_RENDER_RESOLUTION,
    MAX_RENDER_SAMPLES,
)

# Allowed render engines
# Blender 4.2-4.4 name the EEVEE engine BLENDER_EEVEE_NEXT; 5.x renamed it back
# to BLENDER_EEVEE. Accept both so the tool spans the supported range.
ALLOWED_RENDER_ENGINES = {
    "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES", "BLENDER_WORKBENCH",
}

# Allowed output formats
ALLOWED_OUTPUT_FORMATS = {"PNG", "JPEG", "OPEN_EXR", "TIFF", "BMP"}

# Allowed image extensions for render output
ALLOWED_RENDER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".exr", ".tiff", ".tif", ".bmp"}

# Color management values in Blender 5.2 (dynamic enums, read from a live session)
ALLOWED_VIEW_TRANSFORMS = {
    "Standard", "ACES 1.3", "ACES 2.0", "Khronos PBR Neutral", "AgX",
    "Filmic", "Filmic Log", "False Color", "Raw",
}
ALLOWED_DISPLAY_DEVICES = {
    "sRGB", "Display P3", "Rec.1886", "Rec.2020", "Rec.2100-PQ", "Rec.2100-HLG",
}
# Short look names; Blender prefixes some per view transform ("AgX - Punchy")
ALLOWED_LOOKS = {
    "None", "Punchy", "Greyscale", "Very High Contrast", "High Contrast",
    "Medium High Contrast", "Medium Contrast", "Base Contrast",
    "Medium Low Contrast", "Low Contrast", "Very Low Contrast",
    "Reference Gamut Compression",
}


@mcp.tool()
def set_render_engine(engine: str) -> dict[str, Any]:
    """Set the render engine.

    Args:
        engine: Render engine to use. One of: BLENDER_EEVEE, CYCLES, BLENDER_WORKBENCH.

    Returns:
        Confirmation dict with the active render engine.
    """
    validate_enum(engine, ALLOWED_RENDER_ENGINES, name="engine")

    conn = get_connection()
    response = conn.send_command("set_render_engine", {"engine": engine})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_render_resolution(
    width: int, height: int, percentage: int = 100
) -> dict[str, Any]:
    """Set the render resolution.

    Args:
        width: Render width in pixels. Range: 1-8192.
        height: Render height in pixels. Range: 1-8192.
        percentage: Resolution percentage scale. Range: 1-100.

    Returns:
        Confirmation dict with the new resolution settings.
    """
    width = validate_numeric_range(width, min_val=1, max_val=MAX_RENDER_RESOLUTION, name="width")
    height = validate_numeric_range(height, min_val=1, max_val=MAX_RENDER_RESOLUTION, name="height")
    percentage = validate_numeric_range(percentage, min_val=1, max_val=100, name="percentage")

    conn = get_connection()
    response = conn.send_command("set_render_resolution", {
        "width": width,
        "height": height,
        "percentage": percentage,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_render_samples(samples: int) -> dict[str, Any]:
    """Set the number of render samples.

    Args:
        samples: Number of samples. Range: 1-10000.

    Returns:
        Confirmation dict with the new sample count.
    """
    samples = validate_numeric_range(samples, min_val=1, max_val=MAX_RENDER_SAMPLES, name="samples")

    conn = get_connection()
    response = conn.send_command("set_render_samples", {"samples": samples})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_output_format(format: str, filepath: str = "") -> dict[str, Any]:
    """Set the render output format and optionally the output file path.

    Args:
        format: Output format. One of: PNG, JPEG, OPEN_EXR, TIFF, BMP.
        filepath: Optional output file path. Must be an absolute path.

    Returns:
        Confirmation dict with the new output settings.
    """
    validate_enum(format, ALLOWED_OUTPUT_FORMATS, name="format")

    params = {"format": format}
    if filepath:
        filepath = validate_file_path(filepath, allowed_extensions=ALLOWED_RENDER_EXTENSIONS)
        params["filepath"] = filepath

    conn = get_connection()
    response = conn.send_command("set_output_format", params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def render_image(filepath: str = "") -> dict[str, Any]:
    """Render the current scene to an image file.

    Args:
        filepath: Output file path for the rendered image. Must be an absolute path
            with a valid image extension (.png, .jpg, .exr, .tiff, .bmp) in a
            directory that exists. Empty means render.png in the system temp
            directory.

    Returns:
        Confirmation dict with the output file path.
    """
    filepath = validate_output_path(filepath or default_output_path("render.png"),
                                    allowed_extensions=ALLOWED_RENDER_EXTENSIONS)

    conn = get_connection()
    response = conn.send_command(
        "render_image", {"filepath": filepath}, timeout=BlenderConnection.RENDER_TIMEOUT
    )
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def render_animation(filepath: str = "", format: str = "PNG") -> dict[str, Any]:
    """Render the animation sequence to image files.

    Args:
        filepath: Output file path prefix for the rendered frames. Each frame will be
            saved with a frame number suffix. The directory must exist. Empty
            means render_ in the system temp directory.
        format: Output format. One of: PNG, JPEG, OPEN_EXR, TIFF, BMP.

    Returns:
        Confirmation dict with output details.
    """
    validate_enum(format, ALLOWED_OUTPUT_FORMATS, name="format")
    if not filepath:
        filepath = default_output_path("render_")
    if not isinstance(filepath, str):
        raise ValidationError("filepath must be a string")
    # Blender resolves a relative path against the .blend, so frames landed
    # somewhere the caller never named. No extension check: this is a prefix.
    filepath = validate_output_path(filepath, allowed_extensions=None, allow_directory=True)
    # Validate no null bytes
    if "\x00" in filepath:
        raise ValidationError("filepath contains null bytes")

    conn = get_connection()
    response = conn.send_command("render_animation", {
        "filepath": filepath,
        "format": format,
    }, timeout=BlenderConnection.ANIMATION_TIMEOUT)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_eevee_light_path(
    direct_intensity: float | None = None,
    indirect_intensity: float | None = None,
) -> dict[str, Any]:
    """Set EEVEE light intensity controls (Blender 5.1+).

    Scales how strongly direct and indirect lighting contribute. Only applies
    when the render engine is EEVEE.

    Args:
        direct_intensity: Multiplier for light arriving straight from a lamp.
            Range 0.0-10.0, 1.0 is unchanged. Leave unset to keep the current
            value.
        indirect_intensity: Multiplier for bounced light. Range 0.0-10.0, 1.0
            is unchanged. Leave unset to keep the current value.

    Returns:
        Dict with both intensities after the change.
    """
    params: dict[str, Any] = {}
    if direct_intensity is not None:
        params["direct_intensity"] = validate_numeric_range(
            direct_intensity, min_val=0.0, max_val=10.0, name="direct_intensity")
    if indirect_intensity is not None:
        params["indirect_intensity"] = validate_numeric_range(
            indirect_intensity, min_val=0.0, max_val=10.0, name="indirect_intensity")

    conn = get_connection()
    response = conn.send_command("set_eevee_light_path", params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_color_management(
    view_transform: str = "",
    look: str = "",
    exposure: float | None = None,
    gamma: float | None = None,
    display_device: str = "",
    white_balance_temperature: float | None = None,
) -> dict[str, Any]:
    """Set how the scene's light becomes final pixel colours.

    AgX (the default) handles bright highlights gracefully; Standard is for
    flat graphics and UI shots; Khronos PBR Neutral keeps product colours
    true. A look adds contrast on top. Leave anything unset to keep it.

    Args:
        view_transform: One of: AgX, Standard, Filmic, Filmic Log,
            Khronos PBR Neutral, ACES 1.3, ACES 2.0, False Color, Raw.
        look: Contrast look, short name. AgX and False Color offer Punchy,
            Greyscale, Base Contrast and Very Low to Very High Contrast; most
            others offer Very Low to Very High Contrast; ACES offers
            Reference Gamut Compression. "None" clears it. Applies to the
            view transform being set, or the current one.
        exposure: Brightness in stops. Range -10.0 to 10.0; 0 is unchanged.
        gamma: Extra gamma. Range 0.0 to 5.0; 1.0 is unchanged.
        display_device: One of: sRGB, Display P3, Rec.1886, Rec.2020,
            Rec.2100-PQ, Rec.2100-HLG.
        white_balance_temperature: Kelvin, 1800 to 100000. Lower warms the
            image, higher cools it. Setting it turns white balance on.

    Returns:
        Dict with the full colour management state after the change.
    """
    params: dict[str, Any] = {}
    if view_transform:
        params["view_transform"] = validate_enum(
            view_transform, ALLOWED_VIEW_TRANSFORMS, name="view_transform")
    if look:
        params["look"] = validate_enum(look, ALLOWED_LOOKS, name="look")
    if exposure is not None:
        params["exposure"] = validate_numeric_range(
            exposure, min_val=-10.0, max_val=10.0, name="exposure")
    if gamma is not None:
        params["gamma"] = validate_numeric_range(gamma, min_val=0.0, max_val=5.0, name="gamma")
    if display_device:
        params["display_device"] = validate_enum(
            display_device, ALLOWED_DISPLAY_DEVICES, name="display_device")
    if white_balance_temperature is not None:
        params["white_balance_temperature"] = float(validate_numeric_range(
            white_balance_temperature, min_val=1800.0, max_val=100000.0,
            name="white_balance_temperature"))

    conn = get_connection()
    response = conn.send_command("set_color_management", params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_film(
    transparent: bool | None = None,
    transparent_glass: bool | None = None,
    filter_width: float | None = None,
) -> dict[str, Any]:
    """Set film options: transparent background and pixel filter.

    Args:
        transparent: Render the world background as transparent, for
            compositing or product cut-outs. Needs PNG or EXR output to keep
            the alpha.
        transparent_glass: Cycles only. Let the background show through glass
            and other transmissive surfaces when transparent is on.
        filter_width: Cycles pixel filter width in pixels, 0.01 to 10.0.
            1.5 is Blender's default; lower is sharper, higher is softer.

    Returns:
        Dict with the film settings after the change.
    """
    params: dict[str, Any] = {}
    if transparent is not None:
        params["transparent"] = bool(transparent)
    if transparent_glass is not None:
        params["transparent_glass"] = bool(transparent_glass)
    if filter_width is not None:
        params["filter_width"] = validate_numeric_range(
            filter_width, min_val=0.01, max_val=10.0, name="filter_width")

    conn = get_connection()
    response = conn.send_command("set_film", params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
