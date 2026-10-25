"""MCP tools for render settings: colour management, film, denoising,
sampling, light paths, motion blur, render passes, light groups and AOVs.

Kept apart from the core rendering tools so a small-context client can load
them only when a task asks for a finished look.
"""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_enum,
    validate_int,
    validate_new_name,
    validate_numeric_range,
    validate_object_name,
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


RAY_VISIBILITY_FLAGS = ("camera", "diffuse", "glossy", "transmission", "volume_scatter",
                        "shadow", "holdout", "shadow_catcher")
ALLOWED_AOV_ACTIONS = {"LIST", "ADD", "REMOVE"}
ALLOWED_AOV_TYPES = {"COLOR", "VALUE"}
MAX_LIGHT_GROUP_OBJECTS = 1000


@mcp.tool()
def set_light_group(
    group: str,
    objects: list[str] | None = None,
    world: bool = False,
    remove: bool = False,
) -> dict[str, Any]:
    """Put lights (or emissive objects, or the world) into a light group.

    Each light group renders as its own pass (Cycles), so light balance can
    be changed in the compositor without re-rendering: the Render Layers
    node gets a Combined_<group> output. The group is created if needed.

    Args:
        group: Light group name. Blender turns dots into underscores; the
            result gives the name actually used.
        objects: Lights or emissive objects to move into the group.
        world: Also put the world (sky/HDRI light) into the group.
        remove: Delete the group and take every member out of it.

    Returns:
        Dict with the group name used and every light group with its members.
    """
    if not isinstance(world, bool) or not isinstance(remove, bool):
        raise ValidationError("world and remove must be true or false")
    if objects is None:
        objects = []
    if not isinstance(objects, list):
        raise ValidationError("objects must be a list of object names")
    if len(objects) > MAX_LIGHT_GROUP_OBJECTS:
        raise ValidationError(f"At most {MAX_LIGHT_GROUP_OBJECTS} objects per call")
    if remove and (objects or world):
        raise ValidationError("remove deletes the whole group; leave objects and world out")
    return _send_render_command("set_light_group", {
        "group": validate_new_name(group),
        "objects": [validate_object_name(object_name) for object_name in objects],
        "world": world,
        "remove": remove,
    })


@mcp.tool()
def manage_aov(action: str, name: str | None = None, type: str = "COLOR") -> dict[str, Any]:
    """List, add or remove shader AOVs: custom render passes written by materials.

    In a material, an Output AOV node (ShaderNodeOutputAOV, its aov_name set to
    this name) writes a color or value into the pass. Use for masks and IDs
    in compositing. The Render Layers node gets an output with the AOV name.

    Args:
        action: LIST, ADD or REMOVE.
        name: AOV name, for ADD and REMOVE.
        type: ADD only: COLOR or VALUE.

    Returns:
        Dict with every AOV (name, type).
    """
    params: dict[str, Any] = {
        "action": validate_enum(action, ALLOWED_AOV_ACTIONS, name="action"),
    }
    if action != "LIST":
        if name is None:
            raise ValidationError(f"{action} needs a name")
        params["name"] = validate_new_name(name)
    if action == "ADD":
        params["type"] = validate_enum(type, ALLOWED_AOV_TYPES, name="type")
    return _send_render_command("manage_aov", params)


ALLOWED_RAY_TRACING_METHODS = {"PROBE", "SCREEN"}
ALLOWED_FAST_GI_METHODS = {"AMBIENT_OCCLUSION_ONLY", "GLOBAL_ILLUMINATION"}
ALLOWED_SHADOW_POOL_SIZES = {16, 32, 64, 128, 256, 512, 1024, 1536, 2048}
ALLOWED_VOLUME_TILE_SIZES = {1, 2, 4, 8, 16}
ALLOWED_TEXTURE_LIMITS = {"OFF", "128", "256", "512", "1024", "2048", "4096", "8192"}
ALLOWED_ANISOTROPIC = {0, 2, 4, 8, 16}


@mcp.tool()
def set_object_ray_visibility(
    object_name: str,
    camera: bool | None = None,
    diffuse: bool | None = None,
    glossy: bool | None = None,
    transmission: bool | None = None,
    volume_scatter: bool | None = None,
    shadow: bool | None = None,
    holdout: bool | None = None,
    shadow_catcher: bool | None = None,
) -> dict[str, Any]:
    """Choose which rays see an object: hide it from the camera but keep its
    shadow, keep it out of reflections, or turn it into a shadow catcher.

    Leave anything unset to keep it.

    Args:
        object_name: Object to change.
        camera: Seen directly by the camera.
        diffuse: Lights matte surfaces by bounced light.
        glossy: Shows in reflections.
        transmission: Shows through glass.
        volume_scatter: Affects smoke and fog.
        shadow: Casts shadows.
        holdout: Cut a transparent hole where the object is, for compositing.
        shadow_catcher: Cycles only. Show only the shadows other objects cast
            on it, for placing renders into photos (pair with set_film
            transparent).

    Returns:
        Dict with every visibility flag after the change.
    """
    params: dict[str, Any] = {"object_name": validate_object_name(object_name)}
    given = {k: v for k, v in locals().items() if k in RAY_VISIBILITY_FLAGS and v is not None}
    if not given:
        raise ValidationError("Set at least one visibility flag")
    params.update({k: bool(v) for k, v in given.items()})
    return _send_render_command("set_object_ray_visibility", params)


@mcp.tool()
def set_eevee_quality(
    raytracing: bool | None = None,
    ray_tracing_method: str = "",
    fast_gi: bool | None = None,
    fast_gi_method: str = "",
    shadow_pool_size: int | None = None,
    shadow_rays: int | None = None,
    shadow_steps: int | None = None,
    volumetric_samples: int | None = None,
    volumetric_tile_size: int | None = None,
    volumetric_shadows: bool | None = None,
    clamp_direct: float | None = None,
    clamp_indirect: float | None = None,
) -> dict[str, Any]:
    """Tune EEVEE's reflections, global illumination, shadows and volumes.

    Leave anything unset to keep it.

    Args:
        raytracing: Screen-space ray traced reflections and refraction.
        ray_tracing_method: PROBE (fast, uses light probes) or SCREEN
            (accurate for what is on screen).
        fast_gi: Approximate bounced light.
        fast_gi_method: GLOBAL_ILLUMINATION or AMBIENT_OCCLUSION_ONLY.
        shadow_pool_size: Shadow memory in MB: 16 to 2048 in powers of two,
            plus 1536 (new in 5.2). Raise it if shadows go blocky.
        shadow_rays: Soft shadow rays per light, 1 to 4.
        shadow_steps: Soft shadow steps, 1 to 16.
        volumetric_samples: Fog and smoke slices, 1 to 256.
        volumetric_tile_size: Volume detail in pixels: 1, 2, 4, 8 or 16
            (smaller is sharper and slower).
        volumetric_shadows: Volumes cast shadows on themselves.
        clamp_direct: Cap on direct light per sample, 0 for none.
        clamp_indirect: Cap on bounced light per sample, 0 for none.

    Returns:
        Dict with the EEVEE settings after the change.
    """
    params: dict[str, Any] = {}
    for key, value in (("raytracing", raytracing), ("fast_gi", fast_gi),
                       ("volumetric_shadows", volumetric_shadows)):
        if value is not None:
            params[key] = bool(value)
    if ray_tracing_method:
        params["ray_tracing_method"] = validate_enum(
            ray_tracing_method, ALLOWED_RAY_TRACING_METHODS, name="ray_tracing_method")
    if fast_gi_method:
        params["fast_gi_method"] = validate_enum(fast_gi_method, ALLOWED_FAST_GI_METHODS,
                                                 name="fast_gi_method")
    if shadow_pool_size is not None:
        size = validate_int(shadow_pool_size, 16, 2048, name="shadow_pool_size")
        if size not in ALLOWED_SHADOW_POOL_SIZES:
            raise ValidationError(f"shadow_pool_size must be one of "
                                  f"{sorted(ALLOWED_SHADOW_POOL_SIZES)}")
        params["shadow_pool_size"] = size
    for key, value, lo, hi in (("shadow_rays", shadow_rays, 1, 4),
                               ("shadow_steps", shadow_steps, 1, 16),
                               ("volumetric_samples", volumetric_samples, 1, 256)):
        if value is not None:
            params[key] = validate_int(value, lo, hi, name=key)
    if volumetric_tile_size is not None:
        tile = validate_int(volumetric_tile_size, 1, 16, name="volumetric_tile_size")
        if tile not in ALLOWED_VOLUME_TILE_SIZES:
            raise ValidationError("volumetric_tile_size must be 1, 2, 4, 8 or 16")
        params["volumetric_tile_size"] = tile
    for key, value in (("clamp_direct", clamp_direct), ("clamp_indirect", clamp_indirect)):
        if value is not None:
            params[key] = validate_numeric_range(value, min_val=0.0, max_val=1000000.0,
                                                 name=key)
    if not params:
        raise ValidationError("Set at least one EEVEE option")
    return _send_render_command("set_eevee_quality", params)


@mcp.tool()
def set_render_performance(
    simplify: bool | None = None,
    max_subdivision: int | None = None,
    texture_limit: str = "",
    texture_resolution: float | None = None,
    persistent_data: bool | None = None,
    auto_tile: bool | None = None,
    tile_size: int | None = None,
    anisotropic_filter: int | None = None,
) -> dict[str, Any]:
    """Speed up heavy renders or fit them in memory.

    Leave anything unset to keep it.

    Args:
        simplify: Turn on Simplify, which max_subdivision and the texture
            settings need.
        max_subdivision: Cap subdivision levels at render, 0 to 6.
        texture_limit: Cycles: largest texture size at render, OFF or 128 to
            8192.
        texture_resolution: Cycles: scale all textures, 0.0 to 1.0 (new in 5.2).
        persistent_data: Cycles: keep scene data between frames of an
            animation for faster re-renders, at the cost of memory.
        auto_tile: Cycles: render in tiles to save memory.
        tile_size: Cycles tile size in pixels, 8 to 8192.
        anisotropic_filter: Texture filtering for angled surfaces: 0, 2, 4, 8
            or 16.

    Returns:
        Dict with the performance settings after the change.
    """
    params: dict[str, Any] = {}
    for key, value in (("simplify", simplify), ("persistent_data", persistent_data),
                       ("auto_tile", auto_tile)):
        if value is not None:
            params[key] = bool(value)
    if max_subdivision is not None:
        params["max_subdivision"] = validate_int(max_subdivision, 0, 6, name="max_subdivision")
    if texture_limit:
        params["texture_limit"] = validate_enum(str(texture_limit), ALLOWED_TEXTURE_LIMITS,
                                                name="texture_limit")
    if texture_resolution is not None:
        params["texture_resolution"] = validate_numeric_range(
            texture_resolution, min_val=0.0, max_val=1.0, name="texture_resolution")
    if tile_size is not None:
        params["tile_size"] = validate_int(tile_size, 8, 8192, name="tile_size")
    if anisotropic_filter is not None:
        level = validate_int(anisotropic_filter, 0, 16, name="anisotropic_filter")
        if level not in ALLOWED_ANISOTROPIC:
            raise ValidationError("anisotropic_filter must be 0, 2, 4, 8 or 16")
        params["anisotropic_filter"] = level
    if not params:
        raise ValidationError("Set at least one performance option")
    return _send_render_command("set_render_performance", params)
