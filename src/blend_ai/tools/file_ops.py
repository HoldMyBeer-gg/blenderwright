"""MCP tools for Blender file import/export operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_file_path,
    validate_enum,
    ALLOWED_IMPORT_EXTENSIONS,
    ALLOWED_EXPORT_EXTENSIONS,
)

# Allowed import/export format identifiers
ALLOWED_IMPORT_TYPES = {
    "", "FBX", "OBJ", "GLTF", "USD", "STL", "PLY", "ABC", "DAE", "SVG", "X3D",
}
ALLOWED_EXPORT_TYPES = {
    "", "FBX", "OBJ", "GLTF", "USD", "STL", "PLY", "ABC", "DAE", "SVG", "X3D",
}

# .blend file extension for save/open
BLEND_EXTENSIONS = {".blend"}


@mcp.tool()
def import_file(
    filepath: str,
    type: str = "",
) -> dict[str, Any]:
    """Import a 3D file into Blender.

    Supports FBX, OBJ, GLTF/GLB, USD, STL, PLY, Alembic (ABC), Collada (DAE),
    SVG, and X3D formats. Auto-detects format from file extension if type is empty.

    Args:
        filepath: Absolute path to the file to import. Must exist.
        type: Optional format override. One of: FBX, OBJ, GLTF, USD, STL, PLY,
              ABC, DAE, SVG, X3D. Auto-detected from extension if empty.

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

    Supports FBX, OBJ, GLTF/GLB, USD, STL, PLY, Alembic (ABC), Collada (DAE),
    SVG, and X3D formats.

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
