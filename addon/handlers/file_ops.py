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


EXPORT_OPERATOR_RNA = {
    ".fbx": lambda: bpy.ops.export_scene.fbx, ".gltf": lambda: bpy.ops.export_scene.gltf,
    ".glb": lambda: bpy.ops.export_scene.gltf, ".obj": lambda: bpy.ops.wm.obj_export,
    ".usd": lambda: bpy.ops.wm.usd_export, ".usda": lambda: bpy.ops.wm.usd_export,
    ".usdc": lambda: bpy.ops.wm.usd_export, ".usdz": lambda: bpy.ops.wm.usd_export,
    ".stl": lambda: bpy.ops.wm.stl_export, ".ply": lambda: bpy.ops.wm.ply_export,
    ".abc": lambda: bpy.ops.wm.alembic_export,
}
# Text settings are never passed: they include paths (filepath, export_texture_dir)
EXPORT_OPTION_TYPES = {"BOOLEAN", "INT", "FLOAT", "ENUM"}


def _export_options(ext, options):
    props = EXPORT_OPERATOR_RNA[ext]().get_rna_type().properties
    allowed = sorted(k for k, p in props.items() if p.type in EXPORT_OPTION_TYPES
                     and not getattr(p, "is_array", False) and k != "rna_type")
    for key in options:
        rna = props.get(key)
        if rna is not None and rna.type == "STRING":
            raise ValueError(f"'{key}' is a text setting; exporter text settings (paths "
                             f"and names) are never passed")
        if key not in allowed:
            raise ValueError(f"'{key}' is not a {ext} export setting. Settings: "
                             f"{', '.join(allowed)}")
    return dict(options)


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

        kwargs = _export_options(ext, params.get("options") or {})
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
    """List recently opened files. In 5.2 preferences.filepaths.recent_files
    is how many to remember; the list itself is recent-files.txt."""
    path = bpy.utils.user_resource("CONFIG", path="recent-files.txt")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as handle:
        return [line.strip() for line in handle if line.strip()]


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


ESSENTIALS = "Essentials"
MAX_ASSET_FILES = 200


def _library_root(name):
    """The folder of a local, enabled library. Online libraries are refused:
    nothing here may reach the internet."""
    if name == ESSENTIALS:
        return os.path.realpath(bpy.utils.system_resource("DATAFILES", path="assets"))
    for lib in bpy.context.preferences.filepaths.asset_libraries:
        if lib.name == name:
            if getattr(lib, "use_remote_url", False):
                raise ValueError(f"'{name}' is an online library; only local ones are used")
            if not lib.enabled:
                raise ValueError(f"Library '{name}' is disabled in Preferences")
            return os.path.realpath(lib.path)
    raise ValueError(f"No asset library '{name}'")


def _inside(root, path):
    real = os.path.realpath(path)
    return real == root or real.startswith(root + os.sep)


def _library_file(library, rel):
    """A .blend inside the library, after resolving '..' and symlinks."""
    root = _library_root(library)
    if os.path.isabs(rel):
        raise ValueError(f"{rel!r} must be relative to the library")
    path = os.path.realpath(os.path.join(root, rel))
    if not _inside(root, path):
        raise ValueError(f"{rel!r} is outside library '{library}'")
    return _blend_path(path)


def handle_list_asset_libraries(params):
    libraries = [{"name": ESSENTIALS, "path": _library_root(ESSENTIALS)}]
    for lib in bpy.context.preferences.filepaths.asset_libraries:
        if lib.enabled and not getattr(lib, "use_remote_url", False):
            libraries.append({"name": lib.name, "path": lib.path,
                              "exists": os.path.isdir(lib.path)})
    return {"libraries": libraries}


def handle_list_assets(params):
    library = params.get("library")
    root = _library_root(library)
    wanted = params.get("asset_type")
    types = {wanted: LINK_TYPES[wanted]} if wanted else LINK_TYPES
    files = []
    for folder, dirs, names in os.walk(root):
        dirs.sort()
        files += [os.path.join(folder, n) for n in sorted(names)
                  if n.lower().endswith(".blend") and _inside(root, os.path.join(folder, n))]
    assets = []
    for path in files[:MAX_ASSET_FILES]:
        with bpy.data.libraries.load(_blend_path(path), assets_only=True) as (src, _dst):
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            for data_type, attr in types.items():
                assets += [{"file": rel, "type": data_type, "name": n}
                           for n in sorted(getattr(src, attr))]
    return {"library": library, "assets": assets, "files_read": min(len(files), MAX_ASSET_FILES),
            "truncated": len(files) > MAX_ASSET_FILES}


def handle_place_asset(params):
    path = _library_file(params.get("library"), params.get("file", ""))
    data_type, name = params.get("asset_type"), params.get("name")
    attr = LINK_TYPES.get(data_type)
    if attr is None:
        raise ValueError(f"Cannot place {data_type!r}")
    with bpy.data.libraries.load(path, assets_only=True) as (src, _dst):
        marked = set(getattr(src, attr))
    if name not in marked:
        raise ValueError(f"'{name}' is not an asset in {params.get('file')}; assets: "
                         f"{', '.join(sorted(marked)) or 'none'}")
    return handle_link_or_append({"filepath": path, "data_type": params.get("asset_type"),
                                  "names": [params.get("name")],
                                  "link": bool(params.get("link", False))})


def _linked_block(data_type, name, library=None):
    """The linked data-block of that name: a local one may share it."""
    attr = LINK_TYPES.get(data_type)
    if attr is None:
        raise ValueError(f"Unknown data type {data_type!r}")
    found = [b for b in getattr(bpy.data, attr) if b.name == name and b.library is not None
             and (library is None or b.library.name == library)]
    if not found:
        raise ValueError(f"No linked {data_type.lower()} '{name}': it is not linked, "
                         f"or not in this file")
    if len(found) > 1:
        raise ValueError(f"'{name}' is linked from several libraries "
                         f"({', '.join(b.library.name for b in found)}); give library")
    return found[0]


def _get_library(name):
    for lib in bpy.data.libraries:
        if lib.name == name:
            return lib
    raise ValueError(f"No library '{name}'; libraries: "
                     f"{', '.join(lib.name for lib in bpy.data.libraries) or 'none'}")


def handle_manage_linked_data(params):
    action = params.get("action")
    if action == "LIST":
        linked, overrides = [], []
        for data_type, attr in LINK_TYPES.items():
            for block in getattr(bpy.data, attr):
                if block.library is not None:
                    linked.append({"type": data_type, "name": block.name,
                                   "library": block.library.name})
                elif block.override_library is not None:
                    overrides.append({"type": data_type, "name": block.name})
        return {"libraries": [{"name": lib.name, "filepath": lib.filepath,
                               "missing": lib.is_missing} for lib in bpy.data.libraries],
                "linked": linked, "overrides": overrides}
    if action == "RELOAD":
        lib = _get_library(params.get("library"))
        lib.reload()
        return {"reloaded": lib.name}

    data_type = params.get("data_type", "OBJECT")
    block = _linked_block(data_type, params.get("data_name"), params.get("library"))
    if action == "MAKE_LOCAL":
        local = block.make_local()
        data = getattr(local, "data", None)
        if data is not None and data.library is not None:
            data.make_local()  # otherwise the object is local but its mesh stays read-only
        return {"made_local": local.name, "type": data_type}
    if action == "OVERRIDE":
        if data_type not in ("OBJECT", "COLLECTION"):
            raise ValueError("OVERRIDE works on OBJECT or COLLECTION")
        scene, layer = bpy.context.scene, bpy.context.view_layer
        reference = None
        if data_type == "COLLECTION":
            reference = next((o for o in bpy.data.objects
                              if getattr(o, "instance_collection", None) == block), None)
        override = block.override_hierarchy_create(scene, layer, reference=reference,
                                                   do_fully_editable=True)
        if override is None:
            raise RuntimeError(f"Blender could not override '{block.name}'")
        if data_type == "OBJECT":
            for coll in block.users_collection:
                if coll.library is None:
                    coll.objects.unlink(block)  # the editable override takes its place
        elif reference is not None:
            bpy.data.objects.remove(reference)
        return {"override": override.name, "type": data_type}
    raise ValueError(f"Unknown action {action!r}")


PACKABLE = (("image", "images"), ("sound", "sounds"), ("font", "fonts"), ("volume", "volumes"))


def _packed_items():
    return [
        (kind, block)
        for kind, collection in PACKABLE
        for block in getattr(bpy.data, collection)
        if block.packed_file is not None
    ]


def handle_pack_resources(params):
    """Pack all external files; optionally turn autopack on or off."""
    bpy.ops.file.pack_all()
    if "autopack" in params:
        bpy.data.use_autopack = bool(params["autopack"])
    return {
        "packed": [{"type": kind, "name": block.name} for kind, block in _packed_items()],
        "autopack": bpy.data.use_autopack,
    }


def handle_unpack_resources(params):
    """Unpack beside the .blend only. The *_ORIGINAL methods would write to
    whatever paths a downloaded file carries, so they are never used."""
    if not bpy.data.filepath:
        raise ValueError("Save the .blend first; packed files are written next to it")
    items = _packed_items()
    method = "WRITE_LOCAL" if params.get("overwrite") else "USE_LOCAL"
    bpy.ops.file.unpack_all(method=method)
    return {
        "unpacked": [
            {"type": kind, "name": block.name, "filepath": block.filepath}
            for kind, block in items
        ],
    }


def _external_files():
    files = []

    def visit(idb, path, meta):
        files.append({"type": idb.id_type, "name": idb.name, "path": path,
                      "exists": os.path.exists(bpy.path.abspath(path))})

    bpy.data.file_path_foreach(visit)
    return files


def handle_manage_external_paths(params):
    """List external paths, rewrite them relative/absolute, or relink moved files."""
    action = params.get("action")
    if action in ("MAKE_RELATIVE", "MAKE_ABSOLUTE"):
        if not bpy.data.filepath:
            raise ValueError("Save the .blend first; paths are relative to it")
        if action == "MAKE_RELATIVE":
            bpy.ops.file.make_paths_relative()
        else:
            bpy.ops.file.make_paths_absolute()
    elif action == "FIND_MISSING":
        directory = params.get("directory")
        if not (isinstance(directory, str) and os.path.isabs(directory)
                and os.path.isdir(directory)
                and os.path.dirname(directory.rstrip(os.sep)) != directory.rstrip(os.sep)):
            raise ValueError(f"Not a searchable directory: {directory!r}")
        bpy.ops.file.find_missing_files(directory=directory, find_all=False)
    elif action != "LIST":
        raise ValueError(f"Unknown action {action!r}")
    files = _external_files()
    return {"files": files, "missing": sum(not f["exists"] for f in files)}


def register():
    """Register file operations handlers with the dispatcher."""
    dispatcher.register_handler("import_file", handle_import_file)
    dispatcher.register_handler("export_file", handle_export_file)
    dispatcher.register_handler("save_file", handle_save_file)
    dispatcher.register_handler("open_file", handle_open_file)
    dispatcher.register_handler("list_recent_files", handle_list_recent_files)
    dispatcher.register_handler("list_blend_contents", handle_list_blend_contents)
    dispatcher.register_handler("link_or_append", handle_link_or_append)
    dispatcher.register_handler("pack_resources", handle_pack_resources)
    dispatcher.register_handler("unpack_resources", handle_unpack_resources)
    dispatcher.register_handler("manage_external_paths", handle_manage_external_paths)
    dispatcher.register_handler("list_asset_libraries", handle_list_asset_libraries)
    dispatcher.register_handler("list_assets", handle_list_assets)
    dispatcher.register_handler("place_asset", handle_place_asset)
    dispatcher.register_handler("manage_linked_data", handle_manage_linked_data)
