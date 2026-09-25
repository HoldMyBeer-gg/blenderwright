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
    original_format = render.image_settings.file_format

    render.filepath = filepath
    render.image_settings.file_format = fmt
    bpy.ops.render.render(animation=True)

    # Restore originals
    render.filepath = original_filepath
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


def register():
    """Register all rendering handlers with the dispatcher."""
    dispatcher.register_handler("set_render_engine", handle_set_render_engine)
    dispatcher.register_handler("set_render_resolution", handle_set_render_resolution)
    dispatcher.register_handler("set_render_samples", handle_set_render_samples)
    dispatcher.register_handler("set_output_format", handle_set_output_format)
    dispatcher.register_handler("render_image", handle_render_image)
    dispatcher.register_handler("render_animation", handle_render_animation)
    dispatcher.register_handler("set_eevee_light_path", handle_set_eevee_light_path)
