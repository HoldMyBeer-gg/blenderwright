"""Blender handlers for rendering operations."""

import bpy
from .. import dispatcher


# Blender renamed its EEVEE engine twice: BLENDER_EEVEE (pre-4.2),
# BLENDER_EEVEE_NEXT (4.2-4.4), BLENDER_EEVEE again (5.x). Callers should not
# have to know which build they reached, so either name maps to whichever this
# build actually offers.
_EEVEE_ALIASES = ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT")


def _resolve_engine(engine):
    """Map an engine id to one this Blender accepts."""
    available = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    if engine in available:
        return engine
    if engine in _EEVEE_ALIASES:
        for alias in _EEVEE_ALIASES:
            if alias in available:
                return alias
    raise ValueError(
        f"Render engine '{engine}' is not available in this Blender build. "
        f"Available: {', '.join(sorted(available))}"
    )


def handle_set_render_engine(params):
    """Set the render engine."""
    engine = _resolve_engine(params["engine"])
    bpy.context.scene.render.engine = engine
    return {"engine": bpy.context.scene.render.engine}


def handle_set_render_resolution(params):
    """Set the render resolution."""
    width = params["width"]
    height = params["height"]
    percentage = params.get("percentage", 100)

    render = bpy.context.scene.render
    render.resolution_x = width
    render.resolution_y = height
    render.resolution_percentage = percentage

    return {
        "resolution_x": render.resolution_x,
        "resolution_y": render.resolution_y,
        "resolution_percentage": render.resolution_percentage,
    }


def handle_set_render_samples(params):
    """Set the number of render samples."""
    samples = params["samples"]
    engine = bpy.context.scene.render.engine

    if engine == "CYCLES":
        bpy.context.scene.cycles.samples = samples
        return {"engine": engine, "samples": bpy.context.scene.cycles.samples}
    else:
        # EEVEE and Workbench
        bpy.context.scene.eevee.taa_render_samples = samples
        return {"engine": engine, "samples": bpy.context.scene.eevee.taa_render_samples}


def handle_set_output_format(params):
    """Set the output format and optionally file path."""
    fmt = params["format"]
    filepath = params.get("filepath", "")

    render = bpy.context.scene.render
    # Image formats are refused while media_type is VIDEO
    render.image_settings.media_type = "IMAGE"
    render.image_settings.file_format = fmt

    if filepath:
        render.filepath = filepath

    result = {"format": render.image_settings.file_format}
    if filepath:
        result["filepath"] = render.filepath
    return result


def handle_render_image(params):
    """Render the current scene to an image file."""
    filepath = params["filepath"]

    render = bpy.context.scene.render
    # Store original filepath
    original_filepath = render.filepath

    render.filepath = filepath
    bpy.ops.render.render(write_still=True)

    # Restore original filepath
    render.filepath = original_filepath

    return {"filepath": filepath, "rendered": True}


def handle_render_animation(params):
    """Render the animation sequence."""
    filepath = params["filepath"]
    fmt = params.get("format", "PNG")

    render = bpy.context.scene.render
    # Store originals
    original_filepath = render.filepath
    original_media_type = render.image_settings.media_type
    original_format = render.image_settings.file_format

    try:
        render.filepath = filepath
        render.image_settings.media_type = "IMAGE"
        render.image_settings.file_format = fmt
        bpy.ops.render.render(animation=True)
    finally:
        render.filepath = original_filepath
        render.image_settings.media_type = original_media_type
        render.image_settings.file_format = original_format

    return {
        "filepath": filepath,
        "format": fmt,
        "frame_start": bpy.context.scene.frame_start,
        "frame_end": bpy.context.scene.frame_end,
        "rendered": True,
    }


def handle_set_eevee_light_path(params: dict) -> dict:
    """Set EEVEE light intensity controls.

    The previous implementation set light_path_diffuse_intensity and two
    siblings, which exist in no Blender version, so every call raised
    AttributeError. EEVEE Next exposes direct_light_intensity and
    indirect_light_intensity instead, with no per-lobe split.
    """
    eevee = bpy.context.scene.eevee

    supported = {
        "direct_intensity": "direct_light_intensity",
        "indirect_intensity": "indirect_light_intensity",
    }

    missing = [attr for attr in supported.values() if not hasattr(eevee, attr)]
    if missing:
        raise RuntimeError(
            f"This Blender build has no EEVEE light intensity controls "
            f"({', '.join(missing)}). They were added in Blender 5.1."
        )

    applied = {}
    for param, attr in supported.items():
        if params.get(param) is not None:
            setattr(eevee, attr, params[param])
        applied[param] = getattr(eevee, attr)
    return applied


def _set_look(view_settings, look):
    """Set a look by its short name, as this view transform spells it.

    AgX and False Color prefix their looks ("AgX - Punchy"); the others use
    the bare name. Setting a look the transform lacks raises TypeError.
    """
    for candidate in (f"{view_settings.view_transform} - {look}", look):
        try:
            view_settings.look = candidate
            return
        except TypeError:
            continue
    raise ValueError(
        f"Look '{look}' is not available for view transform "
        f"'{view_settings.view_transform}'"
    )


def handle_set_color_management(params):
    """Set view transform, look, exposure, gamma, display and white balance."""
    scene = bpy.context.scene
    vs = scene.view_settings

    # The transform first: changing it resets the look
    if "view_transform" in params:
        vs.view_transform = params["view_transform"]
    if "look" in params:
        _set_look(vs, params["look"])
    if "exposure" in params:
        vs.exposure = params["exposure"]
    if "gamma" in params:
        vs.gamma = params["gamma"]
    if "display_device" in params:
        scene.display_settings.display_device = params["display_device"]
    if "white_balance_temperature" in params:
        vs.use_white_balance = True
        vs.white_balance_temperature = params["white_balance_temperature"]

    return {
        "view_transform": vs.view_transform,
        "look": vs.look,
        "exposure": vs.exposure,
        "gamma": vs.gamma,
        "display_device": scene.display_settings.display_device,
        "use_white_balance": vs.use_white_balance,
        "white_balance_temperature": vs.white_balance_temperature,
    }


def handle_set_film(params):
    """Set transparent film and the Cycles pixel filter."""
    scene = bpy.context.scene
    if "transparent" in params:
        scene.render.film_transparent = params["transparent"]
    if "transparent_glass" in params:
        scene.cycles.film_transparent_glass = params["transparent_glass"]
    if "filter_width" in params:
        scene.cycles.filter_width = params["filter_width"]

    return {
        "transparent": scene.render.film_transparent,
        "transparent_glass": scene.cycles.film_transparent_glass,
        "filter_width": scene.cycles.filter_width,
    }


# Tool parameter -> Cycles property, per tool
DENOISING_PROPERTIES = {
    "enabled": "use_denoising",
    "denoiser": "denoiser",
    "quality": "denoising_quality",
    "prefilter": "denoising_prefilter",
    "input_passes": "denoising_input_passes",
    "use_gpu": "denoising_use_gpu",
    "viewport": "use_preview_denoising",
}
SAMPLING_PROPERTIES = {
    "adaptive": "use_adaptive_sampling",
    "noise_threshold": "adaptive_threshold",
    "min_samples": "adaptive_min_samples",
    "time_limit": "time_limit",
    "clamp_direct": "sample_clamp_direct",
    "clamp_indirect": "sample_clamp_indirect",
    "path_guiding": "use_guiding",
    "seed": "seed",
    "animated_seed": "use_animated_seed",
}
LIGHT_PATH_PROPERTIES = {
    "total": "max_bounces",
    "diffuse": "diffuse_bounces",
    "glossy": "glossy_bounces",
    "transmission": "transmission_bounces",
    "volume": "volume_bounces",
    "transparent": "transparent_max_bounces",
    "caustics_reflective": "caustics_reflective",
    "caustics_refractive": "caustics_refractive",
    "filter_glossy": "blur_glossy",
}

# Render pass name -> (view layer sub-owner, property). "" is the view layer itself.
RENDER_PASSES = {
    name: ("", f"use_pass_{name}") for name in (
        "combined", "z", "mist", "normal", "position", "vector", "uv",
        "object_index", "material_index", "ambient_occlusion", "shadow", "emit",
        "environment", "diffuse_direct", "diffuse_indirect", "diffuse_color",
        "glossy_direct", "glossy_indirect", "glossy_color",
        "transmission_direct", "transmission_indirect", "transmission_color",
        "subsurface_direct", "subsurface_indirect", "subsurface_color",
        "cryptomatte_object", "cryptomatte_material", "cryptomatte_asset",
        "grease_pencil",
    )
}
RENDER_PASSES.update({
    "shadow_catcher": ("cycles", "use_pass_shadow_catcher"),
    "volume_direct": ("cycles", "use_pass_volume_direct"),
    "volume_indirect": ("cycles", "use_pass_volume_indirect"),
    "transparent": ("eevee", "use_pass_transparent"),
})


def _apply(owner, mapping, params):
    """Set each given parameter through the mapping and report every mapped value."""
    for key, prop in mapping.items():
        if key in params:
            setattr(owner, prop, params[key])
    return {key: getattr(owner, prop) for key, prop in mapping.items()}


def handle_set_denoising(params):
    """Set Cycles denoising options."""
    cycles = bpy.context.scene.cycles
    if "denoiser" in params:
        try:
            cycles.denoiser = params["denoiser"]
        except TypeError:
            raise ValueError(
                f"Denoiser '{params['denoiser']}' is not available on this machine"
            ) from None
    return _apply(cycles, DENOISING_PROPERTIES, params)


def handle_set_cycles_sampling(params):
    """Set Cycles adaptive sampling, time limit, clamping, guiding and seed."""
    return _apply(bpy.context.scene.cycles, SAMPLING_PROPERTIES, params)


def handle_set_light_paths(params):
    """Set Cycles bounce limits, caustics and glossy filtering."""
    return _apply(bpy.context.scene.cycles, LIGHT_PATH_PROPERTIES, params)


def handle_set_motion_blur(params):
    """Set render motion blur and EEVEE blur steps."""
    scene = bpy.context.scene
    render = scene.render
    if "enabled" in params:
        render.use_motion_blur = params["enabled"]
    if "shutter" in params:
        render.motion_blur_shutter = params["shutter"]
    if "position" in params:
        render.motion_blur_position = params["position"]
    if "eevee_steps" in params:
        scene.eevee.motion_blur_steps = params["eevee_steps"]
    return {
        "enabled": render.use_motion_blur,
        "shutter": render.motion_blur_shutter,
        "position": render.motion_blur_position,
        "eevee_steps": scene.eevee.motion_blur_steps,
    }


def handle_set_render_passes(params):
    """Turn render passes on or off on the active view layer."""
    passes = params.get("passes", [])
    unknown = [p for p in passes if p not in RENDER_PASSES]
    if unknown:
        raise ValueError(f"Unknown render pass(es): {', '.join(map(str, unknown))}")
    enabled = bool(params.get("enabled", True))
    view_layer = bpy.context.view_layer
    for name in passes:
        sub, prop = RENDER_PASSES[name]
        owner = getattr(view_layer, sub) if sub else view_layer
        setattr(owner, prop, enabled)
    return {"view_layer": view_layer.name, "enabled": enabled, "changed": list(passes)}


def register():
    """Register all rendering handlers with the dispatcher."""
    dispatcher.register_handler("set_render_engine", handle_set_render_engine)
    dispatcher.register_handler("set_render_resolution", handle_set_render_resolution)
    dispatcher.register_handler("set_render_samples", handle_set_render_samples)
    dispatcher.register_handler("set_output_format", handle_set_output_format)
    dispatcher.register_handler("render_image", handle_render_image)
    dispatcher.register_handler("render_animation", handle_render_animation)
    dispatcher.register_handler("set_eevee_light_path", handle_set_eevee_light_path)
    dispatcher.register_handler("set_color_management", handle_set_color_management)
    dispatcher.register_handler("set_film", handle_set_film)
    dispatcher.register_handler("set_denoising", handle_set_denoising)
    dispatcher.register_handler("set_cycles_sampling", handle_set_cycles_sampling)
    dispatcher.register_handler("set_light_paths", handle_set_light_paths)
    dispatcher.register_handler("set_motion_blur", handle_set_motion_blur)
    dispatcher.register_handler("set_render_passes", handle_set_render_passes)
