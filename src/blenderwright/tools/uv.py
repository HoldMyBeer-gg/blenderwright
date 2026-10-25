"""MCP tools for Blender UV mapping operations."""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_object_name,
    validate_enum,
    validate_int,
    validate_numeric_range,
    ValidationError,
)

ALLOWED_UNWRAP_METHODS = {"ANGLE_BASED", "CONFORMAL", "MINIMUM_STRETCH"}
ALLOWED_PROJECTIONS = {"CUBE", "CYLINDER", "SPHERE"}
ALLOWED_PACK_ROTATE_METHODS = {
    "ANY", "CARDINAL", "AXIS_ALIGNED", "AXIS_ALIGNED_X", "AXIS_ALIGNED_Y",
}
ALLOWED_UV_ISLAND_OPERATIONS = {
    "AVERAGE_SCALE", "MINIMIZE_STRETCH", "ALIGN_ROTATION", "RANDOMIZE",
    "SEAMS_FROM_ISLANDS", "ARRANGE", "WELD",
}
ALLOWED_SELECTION_MODES = {"ALL", "CURRENT"}
ALLOWED_UV_MAP_ACTIONS = {"LIST", "ADD", "REMOVE", "SET_ACTIVE", "SET_RENDER", "RENAME"}
ALLOWED_TEXTURE_SIZES = {64, 128, 256, 512, 1024, 2048, 4096, 8192}


@mcp.tool()
def smart_uv_project(
    object_name: str,
    angle_limit: float = 66.0,
    island_margin: float = 0.0,
    area_weight: float = 0.0,
) -> dict[str, Any]:
    """Apply Smart UV Project to a mesh object.

    Automatically unwraps the mesh using angle-based projection.

    Args:
        object_name: Name of the mesh object.
        angle_limit: Angle limit in degrees for splitting faces (0.0-89.0).
        island_margin: Margin between UV islands (0.0-1.0).
        area_weight: Weight given to face area for island arrangement (0.0-1.0).

    Returns:
        Confirmation dict with object name and UV map info.
    """
    object_name = validate_object_name(object_name)
    angle_limit = validate_numeric_range(angle_limit, min_val=0.0, max_val=89.0, name="angle_limit")
    island_margin = validate_numeric_range(island_margin, min_val=0.0, max_val=1.0, name="island_margin")
    area_weight = validate_numeric_range(area_weight, min_val=0.0, max_val=1.0, name="area_weight")

    conn = get_connection()
    response = conn.send_command("smart_uv_project", {
        "object_name": object_name,
        "angle_limit": angle_limit,
        "island_margin": island_margin,
        "area_weight": area_weight,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def uv_unwrap(
    object_name: str,
    method: str = "ANGLE_BASED",
) -> dict[str, Any]:
    """Unwrap a mesh object's UVs using standard unwrap.

    Requires seams to be marked for best results.

    Args:
        object_name: Name of the mesh object.
        method: Unwrap method - ANGLE_BASED, CONFORMAL, or MINIMUM_STRETCH
            (the SLIM unwrapper; least distortion, slower).

    Returns:
        Confirmation dict with object name.
    """
    object_name = validate_object_name(object_name)
    validate_enum(method, ALLOWED_UNWRAP_METHODS, name="method")

    conn = get_connection()
    response = conn.send_command("uv_unwrap", {
        "object_name": object_name,
        "method": method,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_uv_projection(
    object_name: str,
    projection: str,
) -> dict[str, Any]:
    """Apply a projection-based UV mapping to a mesh object.

    Args:
        object_name: Name of the mesh object.
        projection: Projection type - CUBE, CYLINDER, or SPHERE.

    Returns:
        Confirmation dict with object name and projection type.
    """
    object_name = validate_object_name(object_name)
    validate_enum(projection, ALLOWED_PROJECTIONS, name="projection")

    conn = get_connection()
    response = conn.send_command("set_uv_projection", {
        "object_name": object_name,
        "projection": projection,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def pack_uv_islands(
    object_name: str,
    margin: float = 0.001,
    rotate: bool = True,
    rotate_method: str = "ANY",
    scale: bool = True,
) -> dict[str, Any]:
    """Pack UV islands to fit efficiently within the UV space.

    Args:
        object_name: Name of the mesh object.
        margin: Margin between packed islands (0.0-1.0).
        rotate: Allow islands to rotate for a tighter fit.
        rotate_method: ANY, CARDINAL (90 degree steps), AXIS_ALIGNED,
            AXIS_ALIGNED_X or AXIS_ALIGNED_Y.
        scale: Scale islands to fill the space. Turn off after
            set_texel_density, or the pack undoes the density.

    Returns:
        Confirmation dict with object name.
    """
    object_name = validate_object_name(object_name)
    margin = validate_numeric_range(margin, min_val=0.0, max_val=1.0, name="margin")

    conn = get_connection()
    response = conn.send_command("pack_uv_islands", {
        "object_name": object_name,
        "margin": margin,
        "rotate": bool(rotate),
        "rotate_method": validate_enum(rotate_method, ALLOWED_PACK_ROTATE_METHODS,
                                       name="rotate_method"),
        "scale": bool(scale),
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _send_uv(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def uv_island_operation(
    object_name: str,
    operation: str,
    selection: str = "ALL",
    iterations: int = 20,
    rotation: float = 0.0,
    scale_variation: float = 0.0,
    offset: float = 0.0,
    seed: int = 0,
    margin: float = 0.05,
    threshold: float = 0.0001,
) -> dict[str, Any]:
    """Tidy UV islands after unwrapping.

    Args:
        object_name: Mesh object with a UV map.
        operation: One of:
            AVERAGE_SCALE (give every island the same texel size relative to
                its 3D area, so textures don't look blurrier on some parts),
            MINIMIZE_STRETCH (relax UVs to reduce distortion: iterations),
            ALIGN_ROTATION (turn islands to line up with the axes),
            RANDOMIZE (jitter islands so tiled textures don't repeat
                visibly: rotation in radians, scale_variation, offset, seed),
            SEAMS_FROM_ISLANDS (mark seams along the current island borders),
            ARRANGE (lay islands out in rows, new in 5.0: margin),
            WELD (merge UV points closer than threshold).
        selection: "ALL" for the whole mesh, or "CURRENT" for the faces
            already selected.
        iterations: MINIMIZE_STRETCH passes, 1 to 1000.
        rotation: RANDOMIZE maximum rotation, 0 to 6.283 radians.
        scale_variation: RANDOMIZE scale range, 0.0 to 1.0.
        offset: RANDOMIZE maximum position change, 0.0 to 1.0.
        seed: RANDOMIZE seed, 0 or more.
        margin: ARRANGE spacing, 0.0 to 1.0.
        threshold: WELD distance, 0.0 to 1.0.

    Returns:
        Dict with the operation and the object.
    """
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "operation": validate_enum(operation, ALLOWED_UV_ISLAND_OPERATIONS, name="operation"),
        "selection": validate_enum(selection, ALLOWED_SELECTION_MODES, name="selection"),
    }
    if operation == "MINIMIZE_STRETCH":
        params["iterations"] = validate_int(iterations, 1, 1000, name="iterations")
    elif operation == "RANDOMIZE":
        params["rotation"] = validate_numeric_range(rotation, min_val=0.0, max_val=6.2832,
                                                    name="rotation")
        params["scale_variation"] = validate_numeric_range(
            scale_variation, min_val=0.0, max_val=1.0, name="scale_variation")
        params["offset"] = validate_numeric_range(offset, min_val=0.0, max_val=1.0,
                                                  name="offset")
        params["seed"] = validate_int(seed, 0, 2147483647, name="seed")
    elif operation == "ARRANGE":
        params["margin"] = validate_numeric_range(margin, min_val=0.0, max_val=1.0,
                                                  name="margin")
    elif operation == "WELD":
        params["threshold"] = validate_numeric_range(threshold, min_val=0.0, max_val=1.0,
                                                     name="threshold")
    return _send_uv("uv_island_operation", params)


@mcp.tool()
def manage_uv_map(
    object_name: str,
    action: str,
    uv_map: str = "UVMap",
    new_name: str | None = None,
    copy_active: bool = True,
) -> dict[str, Any]:
    """List, add, remove, rename UV maps, or choose which one is edited or rendered.

    A mesh holds up to 8 UV maps. Common use: ADD a "Lightmap" map, then
    smart_uv_project or pack_uv_islands on it for non-overlapping bake UVs,
    while textures keep using the first map. UV tools work on the active map;
    materials and export use the render map unless a UV Map node picks one.

    Args:
        object_name: Mesh object.
        action: LIST, ADD (becomes the active map), REMOVE, SET_ACTIVE (the
            map UV tools edit), SET_RENDER (the map renders and exports), RENAME.
        uv_map: The map to act on, or the new map's name for ADD.
        new_name: RENAME only: the new name.
        copy_active: ADD only: start from a copy of the active map's UVs
            instead of blank ones.

    Returns:
        Dict with every UV map (name, active, render).
    """
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "action": validate_enum(action, ALLOWED_UV_MAP_ACTIONS, name="action"),
    }
    if action != "LIST":
        params["uv_map"] = validate_object_name(uv_map)
    if action == "ADD":
        if not isinstance(copy_active, bool):
            raise ValidationError(f"copy_active must be true or false, got {copy_active!r}")
        params["copy_active"] = copy_active
    elif action == "RENAME":
        if new_name is None:
            raise ValidationError("RENAME needs new_name")
        params["new_name"] = validate_object_name(new_name)
    return _send_uv("manage_uv_map", params)


def _texture_size(texture_size: Any) -> int:
    size = validate_int(texture_size, 64, 8192, name="texture_size")
    if size not in ALLOWED_TEXTURE_SIZES:
        raise ValidationError(f"texture_size must be a power of two from 64 to 8192, got {size}")
    return size


@mcp.tool()
def get_texel_density(object_name: str, texture_size: int = 1024) -> dict[str, Any]:
    """Measure texel density: how many texture pixels cover one metre of surface.

    Matching density across assets keeps texture sharpness consistent; game
    art often targets 512 or 1024 px/m.

    Args:
        object_name: Mesh object with a UV map.
        texture_size: Texture width in pixels the UVs are meant for.

    Returns:
        Dict with density in px/m, surface area in m^2 (world scale), and the
        share of UV space used.
    """
    return _send_uv("get_texel_density", {
        "object_name": validate_object_name(object_name),
        "texture_size": _texture_size(texture_size),
    })


@mcp.tool()
def set_texel_density(
    object_name: str,
    density: float,
    texture_size: int = 1024,
) -> dict[str, Any]:
    """Scale an object's UVs to hit a target texel density.

    Islands keep their layout and scale about their shared centre, so they
    may spill outside the 0-1 square; pack afterwards with
    pack_uv_islands(scale=False) to bring them back without undoing this.

    Args:
        object_name: Mesh object with a UV map.
        density: Target pixels per metre, above 0 and up to 100000.
        texture_size: Texture width in pixels the UVs are meant for.

    Returns:
        Dict with the density before and after.
    """
    target = validate_numeric_range(density, min_val=1e-6, max_val=100000.0, name="density")
    return _send_uv("set_texel_density", {
        "object_name": validate_object_name(object_name),
        "density": float(target),
        "texture_size": _texture_size(texture_size),
    })
