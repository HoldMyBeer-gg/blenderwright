"""Blender handlers for rendering operations."""

import bpy
from .. import dispatcher


def handle_set_render_engine(params):
    """Set the render engine."""
    engine = params["engine"]
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
    """Set EEVEE light path intensity controls."""
    eevee = bpy.context.scene.eevee

    if "diffuse_intensity" in params:
        eevee.light_path_diffuse_intensity = params["diffuse_intensity"]
    if "glossy_intensity" in params:
        eevee.light_path_glossy_intensity = params["glossy_intensity"]
    if "transmission_intensity" in params:
        eevee.light_path_transmission_intensity = params["transmission_intensity"]

    return {
        "diffuse_intensity": eevee.light_path_diffuse_intensity,
        "glossy_intensity": eevee.light_path_glossy_intensity,
        "transmission_intensity": eevee.light_path_transmission_intensity,
    }


def register():
    """Register all rendering handlers with the dispatcher."""
    dispatcher.register_handler("set_render_engine", handle_set_render_engine)
    dispatcher.register_handler("set_render_resolution", handle_set_render_resolution)
    dispatcher.register_handler("set_render_samples", handle_set_render_samples)
    dispatcher.register_handler("set_output_format", handle_set_output_format)
    dispatcher.register_handler("render_image", handle_render_image)
    dispatcher.register_handler("render_animation", handle_render_animation)
    dispatcher.register_handler("set_eevee_light_path", handle_set_eevee_light_path)
