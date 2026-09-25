"""MCP tools for Blender rendering operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_enum,
    validate_numeric_range,
    validate_file_path,
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
def render_image(filepath: str = "/tmp/render.png") -> dict[str, Any]:  # nosec B108
    """Render the current scene to an image file.

    Args:
        filepath: Output file path for the rendered image. Must be an absolute path
            with a valid image extension (.png, .jpg, .exr, .tiff, .bmp).

    Returns:
        Confirmation dict with the output file path.
    """
    filepath = validate_file_path(filepath, allowed_extensions=ALLOWED_RENDER_EXTENSIONS)

    conn = get_connection()
    response = conn.send_command("render_image", {"filepath": filepath})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def render_animation(filepath: str = "/tmp/render_", format: str = "PNG") -> dict[str, Any]:  # nosec B108
    """Render the animation sequence to image files.

    Args:
        filepath: Output file path prefix for the rendered frames. Each frame will be
            saved with a frame number suffix.
        format: Output format. One of: PNG, JPEG, OPEN_EXR, TIFF, BMP.

    Returns:
        Confirmation dict with output details.
    """
    validate_enum(format, ALLOWED_OUTPUT_FORMATS, name="format")
    if not filepath or not isinstance(filepath, str):
        raise ValidationError("filepath must be a non-empty string")
    # Blender resolves a relative path against the .blend, so frames landed
    # somewhere the caller never named. No extension check: this is a prefix.
    filepath = validate_file_path(filepath, allowed_extensions=None)
    # Validate no null bytes
    if "\x00" in filepath:
        raise ValidationError("filepath contains null bytes")

    conn = get_connection()
    response = conn.send_command("render_animation", {
        "filepath": filepath,
        "format": format,
    })
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
