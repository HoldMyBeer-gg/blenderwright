"""MCP tools for the Blender compositor (post-processing after render)."""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_enum,
    validate_object_name,
    validate_socket_settings,
    ValidationError,
)

# Built-in compositor nodes and Essentials node-group assets in Blender 5.2
ALLOWED_EFFECTS = {
    "glare", "lens_distortion", "color_balance", "denoise", "blur", "exposure",
    "brightness_contrast", "hue_saturation", "kuwahara", "pixelate", "posterize",
    "anti_aliasing",
    "vignette", "film_grain", "chromatic_aberration", "sepia", "split_toning",
    "sensor_noise", "unsharp_mask", "tune_image",
}

def _send(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def setup_compositor(reset: bool = False) -> dict[str, Any]:
    """Make sure the scene has a compositor: Render Layers into the output.

    add_compositor_effect calls this itself, so it is only needed to start
    over. Effects then stack between the render and the output.

    Args:
        reset: Throw away the current compositor tree and start clean.

    Returns:
        Dict with the tree name and the effect chain, render to output.
    """
    return _send("setup_compositor", {"reset": bool(reset)})


@mcp.tool()
def add_compositor_effect(effect: str, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Add a post-processing effect at the end of the compositor chain.

    Effects apply to every render in order, so add glare before film grain.

    Args:
        effect: One of:
            glare (inputs: Type Bloom/Fog Glow/Streaks/Ghosts/Simple Star/
                Sun Beams, Quality High/Medium/Low, Threshold, Strength, Size,
                Saturation, Tint, Streaks, Streaks Angle),
            lens_distortion (Type Radial/Horizontal, Distortion -1..1,
                Dispersion, Fit),
            color_balance (Type Lift/Gamma/Gain or
                "Offset/Power/Slope (ASC-CDL)" or White Point, Factor, Lift,
                Gamma, Gain as RGBA lists, Temperature, Tint),
            denoise (Prefilter, Quality, HDR), blur (Size [x, y] in pixels,
                Type Gaussian...), exposure (Exposure), brightness_contrast
                (Brightness, Contrast), hue_saturation (Hue, Saturation, Value,
                Factor), kuwahara (painterly), pixelate, posterize,
                anti_aliasing,
            vignette (Factor, Feather, Corner Roundness, Scale [x, y]),
            film_grain (Preset, ISO 50..3200, Animated, Softness),
            chromatic_aberration (Factor, Type, Samples), sepia (Tone,
                Saturation, Contrast), split_toning (Highlights, Shadows as
                RGBA, Balance), sensor_noise (Luminance Noise, Chroma Noise),
            unsharp_mask (Radius, Factor), tune_image (Contrast, Color
            Boost, Clarity, Sharpen).
        settings: Input name to value, e.g. {"Type": "Fog Glow",
            "Strength": 0.6}. Names are the node's input labels.

    Returns:
        Dict with the new node's name (use it to edit or remove the effect)
        and its input names.
    """
    validate_enum(effect, ALLOWED_EFFECTS, name="effect")
    return _send("add_compositor_effect", {
        "effect": effect, "settings": validate_socket_settings(settings or {}),
    })


@mcp.tool()
def set_compositor_effect(node_name: str, settings: dict[str, Any]) -> dict[str, Any]:
    """Change the settings of an effect already in the compositor.

    Args:
        node_name: The node name returned by add_compositor_effect or
            list_compositor, e.g. "Glare".
        settings: Input name to value, as for add_compositor_effect.

    Returns:
        Dict with the node name and its inputs after the change.
    """
    node_name = validate_object_name(node_name)
    clean = validate_socket_settings(settings)
    if not clean:
        raise ValidationError("settings must name at least one input to change")
    return _send("set_compositor_effect", {"node_name": node_name, "settings": clean})


@mcp.tool()
def remove_compositor_effect(node_name: str) -> dict[str, Any]:
    """Remove an effect and reconnect the chain around it.

    Args:
        node_name: The node name from add_compositor_effect or list_compositor.

    Returns:
        Dict with the removed name and the remaining chain.
    """
    return _send("remove_compositor_effect", {"node_name": validate_object_name(node_name)})


@mcp.tool()
def list_compositor() -> dict[str, Any]:
    """List the compositor chain from render to output with each effect's settings.

    Returns:
        Dict with the tree name and the chain of effects in order.
    """
    return _send("list_compositor", {})
