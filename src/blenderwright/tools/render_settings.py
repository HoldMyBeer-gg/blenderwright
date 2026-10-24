"""MCP tools for render settings: colour management, film, denoising,
sampling, light paths, motion blur and render passes.

Kept apart from the core rendering tools so a small-context client can load
them only when a task asks for a finished look.
"""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_enum,
    validate_int,
    validate_numeric_range,
    ValidationError,
)

# Color management values in Blender 5.2 (dynamic enums, read from a live session)
ALLOWED_VIEW_TRANSFORMS = {
    "Standard", "ACES 1.3", "ACES 2.0", "Khronos PBR Neutral", "AgX",
    "Filmic", "Filmic Log", "False Color", "Raw",
}
ALLOWED_DISPLAY_DEVICES = {
    "sRGB", "Display P3", "Rec.1886", "Rec.2020", "Rec.2100-PQ", "Rec.2100-HLG",
}
ALLOWED_DENOISERS = {"OPENIMAGEDENOISE", "OPTIX"}
ALLOWED_DENOISE_QUALITY = {"HIGH", "BALANCED", "FAST"}
ALLOWED_DENOISE_PREFILTER = {"NONE", "FAST", "ACCURATE"}
ALLOWED_DENOISE_INPUT_PASSES = {"RGB", "RGB_ALBEDO", "RGB_ALBEDO_NORMAL"}
ALLOWED_MOTION_BLUR_POSITIONS = {"START", "CENTER", "END"}

# Render pass names: the suffix of Blender's use_pass_* property
ALLOWED_RENDER_PASSES = {
    "combined", "z", "mist", "normal", "position", "vector", "uv",
    "object_index", "material_index", "ambient_occlusion", "shadow", "emit",
    "environment", "diffuse_direct", "diffuse_indirect", "diffuse_color",
    "glossy_direct", "glossy_indirect", "glossy_color",
    "transmission_direct", "transmission_indirect", "transmission_color",
    "subsurface_direct", "subsurface_indirect", "subsurface_color",
    "cryptomatte_object", "cryptomatte_material", "cryptomatte_asset",
    "shadow_catcher", "volume_direct", "volume_indirect", "transparent",
    "grease_pencil",
}
RENDER_PASS_ALIASES = {"depth": "z", "emission": "emit", "ao": "ambient_occlusion"}

# Short look names; Blender prefixes some per view transform ("AgX - Punchy")
ALLOWED_LOOKS = {
    "None", "Punchy", "Greyscale", "Very High Contrast", "High Contrast",
    "Medium High Contrast", "Medium Contrast", "Base Contrast",
    "Medium Low Contrast", "Low Contrast", "Very Low Contrast",
    "Reference Gamut Compression",
}


def _send_render_command(command: str, params: dict[str, Any]) -> dict[str, Any]:
    conn = get_connection()
    response = conn.send_command(command, params)
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

    return _send_render_command("set_color_management", params)


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

    return _send_render_command("set_film", params)


@mcp.tool()
def set_denoising(
    enabled: bool | None = None,
    denoiser: str = "",
    quality: str = "",
    prefilter: str = "",
    input_passes: str = "",
    use_gpu: bool | None = None,
    viewport: bool | None = None,
) -> dict[str, Any]:
    """Configure Cycles denoising for final renders and the viewport.

    Denoising lets a render use far fewer samples: 128 denoised samples often
    beat 2048 raw ones. Leave anything unset to keep it.

    Args:
        enabled: Denoise final renders.
        denoiser: OPENIMAGEDENOISE (any machine) or OPTIX (NVIDIA GPUs only).
        quality: HIGH, BALANCED or FAST.
        prefilter: How the albedo and normal guides are cleaned: ACCURATE
            (sharpest detail), FAST, or NONE.
        input_passes: Guides the denoiser uses: RGB, RGB_ALBEDO, or
            RGB_ALBEDO_NORMAL (best edges).
        use_gpu: Run the denoiser on the GPU when one is available.
        viewport: Denoise the rendered viewport preview too.

    Returns:
        Dict with the denoising settings after the change.
    """
    params: dict[str, Any] = {}
    if enabled is not None:
        params["enabled"] = bool(enabled)
    if denoiser:
        params["denoiser"] = validate_enum(denoiser, ALLOWED_DENOISERS, name="denoiser")
    if quality:
        params["quality"] = validate_enum(quality, ALLOWED_DENOISE_QUALITY, name="quality")
    if prefilter:
        params["prefilter"] = validate_enum(prefilter, ALLOWED_DENOISE_PREFILTER,
                                            name="prefilter")
    if input_passes:
        params["input_passes"] = validate_enum(input_passes, ALLOWED_DENOISE_INPUT_PASSES,
                                               name="input_passes")
    if use_gpu is not None:
        params["use_gpu"] = bool(use_gpu)
    if viewport is not None:
        params["viewport"] = bool(viewport)
    return _send_render_command("set_denoising", params)


@mcp.tool()
def set_cycles_sampling(
    adaptive: bool | None = None,
    noise_threshold: float | None = None,
    min_samples: int | None = None,
    time_limit: float | None = None,
    clamp_direct: float | None = None,
    clamp_indirect: float | None = None,
    path_guiding: bool | None = None,
    seed: int | None = None,
    animated_seed: bool | None = None,
) -> dict[str, Any]:
    """Tune how Cycles spends samples. Set the sample count with set_render_samples.

    Leave anything unset to keep it.

    Args:
        adaptive: Stop sampling pixels once they are clean enough.
        noise_threshold: Adaptive cut-off, 0.0 to 1.0. 0.01 is Blender's
            default; 0.05 renders faster and noisier, 0.001 slower and cleaner.
        min_samples: Samples every pixel gets before adaptive stopping,
            0 to 4096. 0 lets Blender choose.
        time_limit: Seconds per frame before stopping, 0 to 86400. 0 means no limit.
        clamp_direct: Cap on direct light per sample, 0 to 1000000. 0 means no
            clamp. Lowers fireflies at the cost of some energy.
        clamp_indirect: Cap on bounced light per sample, 0 to 1000000. 10 is
            Blender's default; lower removes fireflies.
        path_guiding: Learn where light comes from; helps interiors lit
            through small openings. CPU only.
        seed: Noise pattern seed, 0 or more.
        animated_seed: Change the seed every frame so noise does not stick
            to the screen in animations.

    Returns:
        Dict with the sampling settings after the change.
    """
    params: dict[str, Any] = {}
    if adaptive is not None:
        params["adaptive"] = bool(adaptive)
    if noise_threshold is not None:
        params["noise_threshold"] = validate_numeric_range(
            noise_threshold, min_val=0.0, max_val=1.0, name="noise_threshold")
    if min_samples is not None:
        params["min_samples"] = validate_int(min_samples, 0, 4096, name="min_samples")
    if time_limit is not None:
        params["time_limit"] = validate_numeric_range(
            time_limit, min_val=0.0, max_val=86400.0, name="time_limit")
    if clamp_direct is not None:
        params["clamp_direct"] = validate_numeric_range(
            clamp_direct, min_val=0.0, max_val=1000000.0, name="clamp_direct")
    if clamp_indirect is not None:
        params["clamp_indirect"] = validate_numeric_range(
            clamp_indirect, min_val=0.0, max_val=1000000.0, name="clamp_indirect")
    if path_guiding is not None:
        params["path_guiding"] = bool(path_guiding)
    if seed is not None:
        params["seed"] = validate_int(seed, 0, 2147483647, name="seed")
    if animated_seed is not None:
        params["animated_seed"] = bool(animated_seed)
    return _send_render_command("set_cycles_sampling", params)


@mcp.tool()
def set_light_paths(
    total: int | None = None,
    diffuse: int | None = None,
    glossy: int | None = None,
    transmission: int | None = None,
    volume: int | None = None,
    transparent: int | None = None,
    caustics_reflective: bool | None = None,
    caustics_refractive: bool | None = None,
    filter_glossy: float | None = None,
) -> dict[str, Any]:
    """Set Cycles light bounce limits and caustics.

    Fewer bounces render faster; glass and liquids need enough transmission
    bounces or they turn black. Each bounce count is 0 to 1024. Leave
    anything unset to keep it.

    Args:
        total: Overall bounce cap (Blender default 12).
        diffuse: Bounces off matte surfaces (default 4).
        glossy: Bounces off shiny surfaces (default 4).
        transmission: Bounces through glass and liquid (default 12).
        volume: Bounces inside smoke and fog (default 0).
        transparent: Layers of alpha-transparent surfaces such as leaves
            (default 8).
        caustics_reflective: Allow light focused by mirrors.
        caustics_refractive: Allow light focused by glass; turning it off
            removes much glass noise.
        filter_glossy: Blur sharp reflections to cut noise, 0.0 to 10.0.

    Returns:
        Dict with the light path settings after the change.
    """
    params: dict[str, Any] = {}
    for key, value in (("total", total), ("diffuse", diffuse), ("glossy", glossy),
                       ("transmission", transmission), ("volume", volume),
                       ("transparent", transparent)):
        if value is not None:
            params[key] = validate_int(value, 0, 1024, name=key)
    if caustics_reflective is not None:
        params["caustics_reflective"] = bool(caustics_reflective)
    if caustics_refractive is not None:
        params["caustics_refractive"] = bool(caustics_refractive)
    if filter_glossy is not None:
        params["filter_glossy"] = validate_numeric_range(
            filter_glossy, min_val=0.0, max_val=10.0, name="filter_glossy")
    return _send_render_command("set_light_paths", params)


@mcp.tool()
def set_motion_blur(
    enabled: bool | None = None,
    shutter: float | None = None,
    position: str = "",
    eevee_steps: int | None = None,
) -> dict[str, Any]:
    """Set render motion blur for moving objects and cameras.

    Args:
        enabled: Turn motion blur on or off.
        shutter: Shutter time in frames, 0.0 to 2.0. 0.5 is a film-like
            180 degree shutter.
        position: Where the shutter opens around the frame: START, CENTER or END.
        eevee_steps: EEVEE only. Blur passes, 1 to 64. More gives smoother
            curved motion.

    Returns:
        Dict with the motion blur settings after the change.
    """
    params: dict[str, Any] = {}
    if enabled is not None:
        params["enabled"] = bool(enabled)
    if shutter is not None:
        params["shutter"] = validate_numeric_range(shutter, min_val=0.0, max_val=2.0,
                                                   name="shutter")
    if position:
        params["position"] = validate_enum(position, ALLOWED_MOTION_BLUR_POSITIONS,
                                           name="position")
    if eevee_steps is not None:
        params["eevee_steps"] = validate_int(eevee_steps, 1, 64, name="eevee_steps")
    return _send_render_command("set_motion_blur", params)


@mcp.tool()
def set_render_passes(passes: list[str], enabled: bool = True) -> dict[str, Any]:
    """Turn render passes on or off for the active view layer.

    Passes are extra images saved with a multilayer EXR or used in the
    compositor: depth for fog and focus, mist, normals, cryptomatte masks
    for picking objects later.

    Args:
        passes: Pass names: combined, z (alias depth), mist, normal,
            position, vector, uv, object_index, material_index,
            ambient_occlusion (alias ao), shadow, emit (alias emission),
            environment, diffuse_direct, diffuse_indirect, diffuse_color,
            glossy_direct, glossy_indirect, glossy_color,
            transmission_direct, transmission_indirect, transmission_color,
            subsurface_direct, subsurface_indirect, subsurface_color,
            cryptomatte_object, cryptomatte_material, cryptomatte_asset,
            shadow_catcher (Cycles), volume_direct, volume_indirect (Cycles),
            transparent (EEVEE), grease_pencil.
        enabled: True to turn them on, False to turn them off.

    Returns:
        Dict with the view layer name and the passes changed.
    """
    if not isinstance(passes, list) or not passes:
        raise ValidationError("passes must be a non-empty list of pass names")
    names: list[str] = []
    for name in passes:
        if not isinstance(name, str):
            raise ValidationError("passes must be a list of pass names")
        name = RENDER_PASS_ALIASES.get(name, name)
        validate_enum(name, ALLOWED_RENDER_PASSES, name="pass")
        if name not in names:
            names.append(name)
    return _send_render_command("set_render_passes", {"passes": names,
                                                      "enabled": bool(enabled)})
