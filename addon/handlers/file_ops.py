"""Blender addon handlers for file import/export commands.

SECURITY: All imports disable auto-execute scripts to prevent script injection
from untrusted files.
"""

import os

import bpy
from .. import dispatcher

# Map file extensions to import operators
IMPORT_OPERATORS = {
    ".fbx": lambda fp, **kw: bpy.ops.wm.fbx_import(filepath=fp, **kw),
    ".obj": lambda fp, **kw: bpy.ops.wm.obj_import(filepath=fp, **kw),
    ".gltf": lambda fp, **kw: bpy.ops.import_scene.gltf(filepath=fp, **kw),
    ".glb": lambda fp, **kw: bpy.ops.import_scene.gltf(filepath=fp, **kw),
    ".usd": lambda fp, **kw: bpy.ops.wm.usd_import(filepath=fp, **kw),
    ".usda": lambda fp, **kw: bpy.ops.wm.usd_import(filepath=fp, **kw),
    ".usdc": lambda fp, **kw: bpy.ops.wm.usd_import(filepath=fp, **kw),
    ".usdz": lambda fp, **kw: bpy.ops.wm.usd_import(filepath=fp, **kw),
    ".stl": lambda fp, **kw: bpy.ops.wm.stl_import(filepath=fp, **kw),
    ".ply": lambda fp, **kw: bpy.ops.wm.ply_import(filepath=fp, **kw),
    ".abc": lambda fp, **kw: bpy.ops.wm.alembic_import(filepath=fp, **kw),
    ".svg": lambda fp, **kw: bpy.ops.import_curve.svg(filepath=fp, **kw),
}

# Map file extensions to export operators
EXPORT_OPERATORS = {
    ".fbx": lambda fp, **kw: bpy.ops.export_scene.fbx(filepath=fp, **kw),
    ".obj": lambda fp, **kw: bpy.ops.wm.obj_export(filepath=fp, **kw),
    ".gltf": lambda fp, **kw: bpy.ops.export_scene.gltf(filepath=fp, export_format='GLTF_SEPARATE', **kw),
    ".glb": lambda fp, **kw: bpy.ops.export_scene.gltf(filepath=fp, export_format='GLB', **kw),
    ".usd": lambda fp, **kw: bpy.ops.wm.usd_export(filepath=fp, **kw),
    ".usda": lambda fp, **kw: bpy.ops.wm.usd_export(filepath=fp, **kw),
    ".usdc": lambda fp, **kw: bpy.ops.wm.usd_export(filepath=fp, **kw),
    ".usdz": lambda fp, **kw: bpy.ops.wm.usd_export(filepath=fp, **kw),
    ".stl": lambda fp, **kw: bpy.ops.wm.stl_export(filepath=fp, **kw),
    ".ply": lambda fp, **kw: bpy.ops.wm.ply_export(filepath=fp, **kw),
    ".abc": lambda fp, **kw: bpy.ops.wm.alembic_export(filepath=fp, **kw),
}

# Each exporter names its "selected objects only" option differently
EXPORT_SELECTION_KEYWORDS = {
    ".fbx": "use_selection",
    ".gltf": "use_selection",
    ".glb": "use_selection",
    ".obj": "export_selected_objects",
    ".stl": "export_selected_objects",
    ".ply": "export_selected_objects",
    ".usd": "selected_objects_only",
    ".usda": "selected_objects_only",
    ".usdc": "selected_objects_only",
    ".usdz": "selected_objects_only",
    ".abc": "selected",
}

# Map type strings to extensions
TYPE_TO_EXTENSION = {
    "FBX": ".fbx",
    "OBJ": ".obj",
    "GLTF": ".gltf",
    "USD": ".usd",
    "STL": ".stl",
    "PLY": ".ply",
    "ABC": ".abc",
    "SVG": ".svg",
}


def _get_extension(filepath: str, type_hint: str = "") -> str:
    """Determine file extension from type hint or filepath."""
    if type_hint:
        ext = TYPE_TO_EXTENSION.get(type_hint.upper())
        if ext:
            return ext
    return os.path.splitext(filepath)[1].lower()


def handle_import_file(params: dict) -> dict:
    """Import a file into Blender."""
    filepath = params.get("filepath")
    type_hint = params.get("type", "")

    try:
        # SECURITY: Disable auto-execute scripts to prevent script injection
        # from imported files. This MUST happen before any import operation.
        bpy.context.preferences.filepaths.use_scripts_auto_execute = False

        ext = _get_extension(filepath, type_hint)
        import_op = IMPORT_OPERATORS.get(ext)
        if import_op is None:
            raise ValueError(f"Unsupported import format: '{ext}'")

        # Count objects before import to determine what was imported
        objects_before = set(bpy.data.objects.keys())

        result = import_op(filepath)

        if result != {'FINISHED'}:
            raise RuntimeError(f"Import operator did not finish successfully: {result}")

        # Determine newly imported objects
        objects_after = set(bpy.data.objects.keys())
        new_objects = list(objects_after - objects_before)

        return {
            "filepath": filepath,
            "format": ext.lstrip(".").upper(),
            "imported_objects": new_objects,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to import '{filepath}': {e}")


def handle_export_file(params: dict) -> dict:
    """Export to a file from Blender."""
    filepath = params.get("filepath")
    type_hint = params.get("type", "")
    selected_only = params.get("selected_only", False)

    try:
        ext = _get_extension(filepath, type_hint)
        export_op = EXPORT_OPERATORS.get(ext)
        if export_op is None:
            raise ValueError(f"Unsupported export format: '{ext}'")

        kwargs = {}
        if selected_only:
            kwargs[EXPORT_SELECTION_KEYWORDS[ext]] = True

        result = export_op(filepath, **kwargs)
        if result != {'FINISHED'}:
            raise RuntimeError(f"Export operator did not finish successfully: {result}")

        return {
            "filepath": filepath,
            "format": ext.lstrip(".").upper(),
            "selected_only": selected_only,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to export '{filepath}': {e}")


def handle_save_file(params: dict) -> dict:
    """Save the current Blender file."""
    filepath = params.get("filepath", "")

    try:
        if filepath:
            bpy.ops.wm.save_as_mainfile(filepath=filepath)
            saved_path = filepath
        else:
            current_path = bpy.data.filepath
            if not current_path:
                raise ValueError(
                    "No current file path. Provide a filepath for Save As."
                )
            bpy.ops.wm.save_mainfile()
            saved_path = current_path

        return {
            "filepath": saved_path,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to save file: {e}")


def handle_open_file(params: dict) -> dict:
    """Open a .blend file."""
    filepath = params.get("filepath")

    try:
        # SECURITY: Disable auto-execute scripts before opening files
        bpy.context.preferences.filepaths.use_scripts_auto_execute = False

        bpy.ops.wm.open_mainfile(filepath=filepath)

        return {
            "filepath": filepath,
            "success": True,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to open file '{filepath}': {e}")


def handle_list_recent_files(params: dict) -> list:
    """List recently opened files."""
    try:
        recent_files = []
        for recent in bpy.context.preferences.filepaths.recent_files:
            recent_files.append(recent.filepath)
        return recent_files
    except Exception as e:
        raise RuntimeError(f"Failed to list recent files: {e}")


# Linkable data type -> bpy.data collection name
LINK_TYPES = {
    "OBJECT": "objects",
    "COLLECTION": "collections",
    "MATERIAL": "materials",
    "NODE_GROUP": "node_groups",
    "WORLD": "worlds",
    "MESH": "meshes",
}


def _blend_path(filepath):
    """An existing .blend file, with script auto-run off before it is read."""
    if not filepath or os.path.splitext(filepath)[1].lower() != ".blend":
        raise ValueError(f"Not a .blend file: {filepath!r}")
    if not os.path.isfile(filepath):
        raise ValueError(f"File not found: {filepath}")
    # SECURITY: never run scripts embedded in another .blend
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    return filepath


def handle_list_blend_contents(params):
    path = _blend_path(params.get("filepath"))
    with bpy.data.libraries.load(path) as (src, _dst):
        return {attr: sorted(getattr(src, attr)) for attr in LINK_TYPES.values()}


def handle_link_or_append(params):
    path = _blend_path(params.get("filepath"))
    data_type = params.get("data_type")
    attr = LINK_TYPES.get(data_type)
    if attr is None:
        raise ValueError(f"Cannot link or append {data_type!r}")
    names = list(params.get("names", []))
    link = bool(params.get("link", False))

    with bpy.data.libraries.load(path, link=link) as (src, dst):
        available = set(getattr(src, attr))
        missing = [n for n in names if n not in available]
        if missing:
            raise ValueError(f"Not in {os.path.basename(path)}: {', '.join(missing)}. "
                             f"Available: {', '.join(sorted(available)) or 'none'}")
        setattr(dst, attr, list(names))  # Blender fills this list in place
    loaded = getattr(dst, attr)

    scene = bpy.context.scene
    instances = []
    for block in loaded:
        if data_type == "OBJECT":
            scene.collection.objects.link(block)
        elif data_type == "COLLECTION":
            if link:
                # A linked collection is read-only; show it through an instance empty
                inst = bpy.data.objects.new(block.name, None)
                inst.instance_type = "COLLECTION"
                inst.instance_collection = block
                scene.collection.objects.link(inst)
                instances.append(inst.name)
            else:
                scene.collection.children.link(block)
    return {"filepath": path, "data_type": data_type, "link": link,
            "items": {name: block.name for name, block in zip(names, loaded)},
            "instances": instances}


def register():
    """Register file operations handlers with the dispatcher."""
    dispatcher.register_handler("import_file", handle_import_file)
    dispatcher.register_handler("export_file", handle_export_file)
    dispatcher.register_handler("save_file", handle_save_file)
    dispatcher.register_handler("open_file", handle_open_file)
    dispatcher.register_handler("list_recent_files", handle_list_recent_files)
    dispatcher.register_handler("list_blend_contents", handle_list_blend_contents)
    dispatcher.register_handler("link_or_append", handle_link_or_append)
