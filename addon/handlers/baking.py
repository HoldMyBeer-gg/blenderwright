"""Blender handler for baking textures with Cycles."""

import os

import bpy
from .. import dispatcher

BAKE_TYPES = {
    "COMBINED", "AO", "SHADOW", "POSITION", "NORMAL", "UV", "ROUGHNESS", "EMIT",
    "ENVIRONMENT", "DIFFUSE", "GLOSSY", "TRANSMISSION",
}
# Data maps, not colours: stored without a colour transform
NON_COLOR_TYPES = {"NORMAL", "ROUGHNESS", "AO", "SHADOW", "POSITION", "UV"}
FILE_FORMATS = {".png": "PNG", ".exr": "OPEN_EXR", ".tif": "TIFF", ".tiff": "TIFF",
                ".jpg": "JPEG", ".jpeg": "JPEG"}


def _get_mesh(name, role):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"{role} '{name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"{role} '{name}' is not a mesh")
    return obj


def _materials(obj):
    return [slot.material for slot in obj.material_slots if slot.material is not None]


def handle_bake_texture(params):
    bake_type = params.get("bake_type")
    if bake_type not in BAKE_TYPES:
        raise ValueError(f"Unknown bake type {bake_type!r}")
    filepath = params.get("filepath", "")
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in FILE_FORMATS:
        raise ValueError(f"Bake output must be one of {sorted(FILE_FORMATS)}, got {ext!r}")

    target = _get_mesh(params.get("object_name"), "Object")
    if not target.data.uv_layers:
        raise ValueError(f"'{target.name}' has no UV map to bake into; unwrap it first "
                         f"with smart_uv_project or uv_unwrap")
    materials = _materials(target)
    if not materials:
        raise ValueError(f"'{target.name}' has no material; assign one first, the bake "
                         f"is written through an image node in each material")
    source = None
    if params.get("source_object"):
        source = _get_mesh(params["source_object"], "Source object")

    size = int(params.get("resolution", 1024))
    image = bpy.data.images.new(f"{target.name}_{bake_type.lower()}", size, size,
                                alpha=False, float_buffer=(ext == ".exr"))
    if bake_type in NON_COLOR_TYPES:
        image.colorspace_settings.name = "Non-Color"

    scene = bpy.context.scene
    saved_engine, saved_samples = scene.render.engine, scene.cycles.samples
    saved_selection = list(bpy.context.selected_objects)
    saved_active = bpy.context.view_layer.objects.active
    added = []
    try:
        if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        scene.render.engine = "CYCLES"
        scene.cycles.samples = int(params.get("samples", 64))

        # Cycles writes into the active Image Texture node of each material
        for material in materials:
            nodes = material.node_tree.nodes
            node = nodes.new("ShaderNodeTexImage")
            node.image = image
            nodes.active = node
            added.append((nodes, node))

        for obj in saved_selection:
            obj.select_set(False)
        target.select_set(True)
        if source is not None:
            source.select_set(True)
        bpy.context.view_layer.objects.active = target

        kwargs = {
            "type": bake_type,
            "margin": int(params.get("margin", 16)),
            "use_selected_to_active": source is not None,
            "target": "IMAGE_TEXTURES",
            "use_clear": True,
        }
        if source is not None:
            kwargs["cage_extrusion"] = float(params.get("cage_extrusion", 0.0))
            kwargs["max_ray_distance"] = float(params.get("max_ray_distance", 0.0))
        if bake_type == "NORMAL":
            kwargs["normal_space"] = params.get("normal_space", "TANGENT")
        if bake_type == "DIFFUSE":
            kwargs["pass_filter"] = ({"COLOR"} if params.get("diffuse_color_only", True)
                                     else {"DIRECT", "INDIRECT", "COLOR"})
        result = bpy.ops.object.bake(**kwargs)
        if result != {"FINISHED"}:
            raise RuntimeError(f"Bake did not finish: {result}")

        image.filepath_raw = filepath
        image.file_format = FILE_FORMATS[ext]
        image.save()
    finally:
        for nodes, node in added:
            nodes.remove(node)
        scene.render.engine = saved_engine
        scene.cycles.samples = saved_samples
        target.select_set(False)
        if source is not None:
            source.select_set(False)
        for obj in saved_selection:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = saved_active

    return {"filepath": filepath, "image": image.name, "width": size, "height": size,
            "bake_type": bake_type, "source_object": source.name if source else None}


def register():
    dispatcher.register_handler("bake_texture", handle_bake_texture)
