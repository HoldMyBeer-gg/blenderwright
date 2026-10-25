"""MCP tools for Blender file import/export operations."""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_directory,
    validate_file_path,
    validate_object_name,
    validate_enum,
    ValidationError,
    ALLOWED_IMPORT_EXTENSIONS,
    ALLOWED_EXPORT_EXTENSIONS,
)

# Allowed import/export format identifiers
ALLOWED_IMPORT_TYPES = {
    "", "FBX", "OBJ", "GLTF", "USD", "STL", "PLY", "ABC", "SVG",
}
ALLOWED_EXPORT_TYPES = {
    "", "FBX", "OBJ", "GLTF", "USD", "STL", "PLY", "ABC",
}

ALLOWED_PATH_ACTIONS = {"LIST", "MAKE_RELATIVE", "MAKE_ABSOLUTE", "FIND_MISSING"}

# .blend file extension for save/open
BLEND_EXTENSIONS = {".blend"}

# Data-block kinds that can be linked or appended from another .blend
ALLOWED_LINK_TYPES = {"OBJECT", "COLLECTION", "MATERIAL", "NODE_GROUP", "WORLD", "MESH"}
MAX_LINK_NAMES = 100


@mcp.tool()
def import_file(
    filepath: str,
    type: str = "",
) -> dict[str, Any]:
    """Import a 3D file into Blender.

    Supports FBX, OBJ, GLTF/GLB, USD, STL, PLY, Alembic (ABC), and SVG formats.
    Auto-detects format from file extension if type is empty.

    Args:
        filepath: Absolute path to the file to import. Must exist.
        type: Optional format override. One of: FBX, OBJ, GLTF, USD, STL, PLY,
              ABC, SVG. Auto-detected from extension if empty.

    Returns:
        Dict with imported file path and format.
    """
    filepath = validate_file_path(filepath, ALLOWED_IMPORT_EXTENSIONS, must_exist=True)
    if type:
        validate_enum(type, ALLOWED_IMPORT_TYPES, name="type")

    conn = get_connection()
    response = conn.send_command("import_file", {
        "filepath": filepath,
        "type": type,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def export_file(
    filepath: str,
    type: str = "",
    selected_only: bool = False,
) -> dict[str, Any]:
    """Export scene or selected objects to a 3D file.

    Supports FBX, OBJ, GLTF/GLB, USD, STL, PLY, and Alembic (ABC) formats.

    Args:
        filepath: Absolute path for the export file.
        type: Optional format override. Auto-detected from extension if empty.
        selected_only: If True, export only selected objects. Defaults to False.

    Returns:
        Dict with exported file path and format.
    """
    filepath = validate_file_path(filepath, ALLOWED_EXPORT_EXTENSIONS, must_exist=False)
    if type:
        validate_enum(type, ALLOWED_EXPORT_TYPES, name="type")

    conn = get_connection()
    response = conn.send_command("export_file", {
        "filepath": filepath,
        "type": type,
        "selected_only": selected_only,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def save_file(
    filepath: str = "",
) -> dict[str, Any]:
    """Save the current Blender file.

    If filepath is empty, saves to the current file path (overwrite).
    If filepath is provided, performs a "Save As" to the given path.

    Args:
        filepath: Optional absolute path to save as. Must have .blend extension.
                  Empty string saves to current file.

    Returns:
        Dict with the saved file path.
    """
    if filepath:
        filepath = validate_file_path(filepath, BLEND_EXTENSIONS, must_exist=False)

    conn = get_connection()
    response = conn.send_command("save_file", {
        "filepath": filepath,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def open_file(
    filepath: str,
) -> dict[str, Any]:
    """Open a .blend file.

    Args:
        filepath: Absolute path to the .blend file. Must exist.

    Returns:
        Dict with the opened file path.
    """
    filepath = validate_file_path(filepath, BLEND_EXTENSIONS, must_exist=True)

    conn = get_connection()
    response = conn.send_command("open_file", {
        "filepath": filepath,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def list_recent_files() -> list[str]:
    """List recently opened files from Blender preferences.

    Returns:
        List of file path strings.
    """
    conn = get_connection()
    response = conn.send_command("list_recent_files")
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _send_file_command(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def list_blend_contents(filepath: str) -> dict[str, Any]:
    """List what another .blend file contains without opening it.

    Use before link_or_append to find the names to bring in. Scripts in the
    file are never run.

    Args:
        filepath: Absolute path to an existing .blend file.

    Returns:
        Dict of data type (objects, collections, materials, node_groups,
        worlds, meshes) to the names in the file.
    """
    return _send_file_command("list_blend_contents", {
        "filepath": validate_file_path(filepath, BLEND_EXTENSIONS, must_exist=True),
    })


@mcp.tool()
def link_or_append(
    filepath: str,
    data_type: str,
    names: list[str],
    link: bool = False,
) -> dict[str, Any]:
    """Bring objects, collections, materials and more in from another .blend file.

    Append copies the data into this file so it can be edited. Link keeps a
    live reference: edits to the source file show up here, but the data is
    read-only. A linked collection is placed as an instance; appended objects
    and collections go into the scene. Scripts in the file are never run.

    Args:
        filepath: Absolute path to an existing .blend file.
        data_type: OBJECT, COLLECTION, MATERIAL, NODE_GROUP, WORLD or MESH.
        names: Names to bring in (see list_blend_contents), at most 100.
        link: True to link instead of append.

    Returns:
        Dict with each requested name and the name it has here (appends may
        gain a .001 suffix), plus any instance created for a linked collection.
    """
    if not isinstance(names, list) or not names:
        raise ValidationError("names must be a non-empty list of data-block names")
    if len(names) > MAX_LINK_NAMES:
        raise ValidationError(f"At most {MAX_LINK_NAMES} names per call")
    clean: list[str] = []
    for block_name in names:
        block_name = validate_object_name(block_name)
        if block_name not in clean:
            clean.append(block_name)
    return _send_file_command("link_or_append", {
        "filepath": validate_file_path(filepath, BLEND_EXTENSIONS, must_exist=True),
        "data_type": validate_enum(data_type, ALLOWED_LINK_TYPES, name="data_type"),
        "names": clean,
        "link": bool(link),
    })


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{name} must be true or false, got {value!r}")
    return value


@mcp.tool()
def pack_resources(autopack: bool | None = None) -> dict[str, Any]:
    """Pack every external image, sound, font and volume into the .blend file.

    Makes the file self-contained so it can be moved or shared without
    missing textures.

    Args:
        autopack: Also pack new external files automatically on every save.

    Returns:
        Dict with the packed items (type, name) and whether autopack is on.
    """
    params: dict[str, Any] = {}
    if autopack is not None:
        params["autopack"] = _bool(autopack, "autopack")
    return _send_file_command("pack_resources", params)


@mcp.tool()
def unpack_resources(overwrite: bool = False) -> dict[str, Any]:
    """Write packed files out to folders next to the saved .blend (textures/, sounds/, ...).

    Files only ever go beside the .blend, never to paths stored in the file.
    The .blend must be saved first.

    Args:
        overwrite: Replace files already there; by default an existing file is reused.

    Returns:
        Dict with each unpacked item (type, name, filepath relative to the .blend).
    """
    return _send_file_command("unpack_resources", {
        "overwrite": _bool(overwrite, "overwrite"),
    })


@mcp.tool()
def manage_external_paths(action: str, directory: str | None = None) -> dict[str, Any]:
    """Check and fix the external files (textures, sounds, libraries) a .blend uses.

    Args:
        action: LIST every external path and whether the file exists;
            MAKE_RELATIVE or MAKE_ABSOLUTE to rewrite them (relative paths
            survive moving the project folder; the .blend must be saved);
            FIND_MISSING to search a folder and relink files that moved.
        directory: FIND_MISSING only: absolute folder to search, recursively.

    Returns:
        Dict with each external file (type, name, path, exists) and the
        missing count, after the action.
    """
    params: dict[str, Any] = {
        "action": validate_enum(action, ALLOWED_PATH_ACTIONS, name="action"),
    }
    if action == "FIND_MISSING":
        if directory is None:
            raise ValidationError("FIND_MISSING needs a directory to search")
        params["directory"] = validate_directory(directory)
    return _send_file_command("manage_external_paths", params)


MAX_ASSET_FILE_PATH = 512


def _library_relative_blend(file: Any) -> str:
    """A .blend path relative to a library root that cannot climb out of it."""
    if not isinstance(file, str) or not file or len(file) > MAX_ASSET_FILE_PATH:
        raise ValidationError("file must be a .blend path relative to the library")
    if "\x00" in file or "\\" in file:
        raise ValidationError("file contains a null byte or backslash; use / separators")
    if file.startswith("/") or (len(file) > 1 and file[1] == ":"):
        raise ValidationError("file must be relative to the library, not absolute")
    if ".." in file.split("/"):
        raise ValidationError("file may not contain '..'")
    if not file.lower().endswith(".blend"):
        raise ValidationError("file must be a .blend file")
    return file


@mcp.tool()
def list_asset_libraries() -> dict[str, Any]:
    """List the asset libraries this Blender can use: Essentials (bundled with
    Blender) and the local libraries set in Preferences. Online libraries are
    never listed or fetched.

    Returns:
        Dict with each library's name and folder.
    """
    return _send_file_command("list_asset_libraries", {})


@mcp.tool()
def list_assets(library: str, asset_type: str = "") -> dict[str, Any]:
    """List the assets in a library, by file, for place_asset.

    Args:
        library: Library name from list_asset_libraries.
        asset_type: Only this type: OBJECT, COLLECTION, MATERIAL, NODE_GROUP,
            WORLD or MESH. Empty for all.

    Returns:
        Dict with assets (file relative to the library, type, name), and
        truncated if the library has more files than one call reads.
    """
    params: dict[str, Any] = {"library": validate_object_name(library)}
    if asset_type:
        params["asset_type"] = validate_enum(asset_type, ALLOWED_LINK_TYPES, name="asset_type")
    return _send_file_command("list_assets", params)


@mcp.tool()
def place_asset(
    library: str,
    file: str,
    asset_type: str,
    asset_name: str,
    link: bool = False,
) -> dict[str, Any]:
    """Bring an asset from a library into the scene (append, or link to keep it
    in sync with the library). Find it with list_assets first.

    Args:
        library: Library name from list_asset_libraries.
        file: The asset's .blend file, relative to the library, as list_assets
            gives it.
        asset_type: OBJECT, COLLECTION, MATERIAL, NODE_GROUP, WORLD or MESH.
        asset_name: The asset's name.
        link: Link instead of append. Linked assets update with the library
            but can't be edited here.

    Returns:
        Dict with the name it got in this file, and any collection instance.
    """
    if not isinstance(link, bool):
        raise ValidationError(f"link must be true or false, got {link!r}")
    return _send_file_command("place_asset", {
        "library": validate_object_name(library),
        "file": _library_relative_blend(file),
        "asset_type": validate_enum(asset_type, ALLOWED_LINK_TYPES, name="asset_type"),
        "name": validate_object_name(asset_name),
        "link": link,
    })
