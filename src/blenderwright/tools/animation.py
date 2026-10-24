"""MCP tools for Blender animation operations."""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    VARIABLE_NAME_PATTERN,
    coerce_scalar,
    validate_data_path,
    validate_driver_expression,
    validate_int,
    validate_object_name,
    validate_enum,
    validate_numeric_range,
    ValidationError,
)

# Allowed data paths for keyframes
ALLOWED_DATA_PATHS = {
    "location",
    "rotation_euler",
    "rotation_quaternion",
    "scale",
    "location[0]",
    "location[1]",
    "location[2]",
    "rotation_euler[0]",
    "rotation_euler[1]",
    "rotation_euler[2]",
    "scale[0]",
    "scale[1]",
    "scale[2]",
}

# Allowed interpolation types
ALLOWED_INTERPOLATIONS = {
    "CONSTANT", "LINEAR", "BEZIER", "SINE", "QUAD", "CUBIC",
    "QUART", "QUINT", "EXPO", "CIRC", "BACK", "BOUNCE", "ELASTIC",
}


def _validate_data_path(data_path: str) -> str:
    """Validate that data_path is in the allowed set."""
    if not data_path or not isinstance(data_path, str):
        raise ValidationError("data_path must be a non-empty string")
    if data_path not in ALLOWED_DATA_PATHS:
        raise ValidationError(
            f"data_path must be one of {sorted(ALLOWED_DATA_PATHS)}, got '{data_path}'"
        )
    return data_path


@mcp.tool()
def insert_keyframe(
    object_name: str,
    data_path: str,
    frame: int,
    value: float | list[float] | None = None,
) -> dict[str, Any]:
    """Insert a keyframe on an object property at a specific frame.

    Args:
        object_name: Name of the object.
        data_path: Property to keyframe. Must be one of: location, rotation_euler,
            rotation_quaternion, scale, or indexed variants like location[0].
        frame: Frame number to insert the keyframe at.
        value: Optional value to set before inserting the keyframe: a number
            for an indexed path like location[2], a list for a whole vector.

    Returns:
        Confirmation dict with keyframe details.
    """
    object_name = validate_object_name(object_name)
    data_path = _validate_data_path(data_path)
    frame = validate_numeric_range(frame, min_val=0, max_val=1048574, name="frame")
    value = coerce_scalar(value)

    conn = get_connection()
    response = conn.send_command("insert_keyframe", {
        "object_name": object_name,
        "data_path": data_path,
        "frame": frame,
        "value": value,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def delete_keyframe(object_name: str, data_path: str, frame: int) -> dict[str, Any]:
    """Remove a keyframe from an object property at a specific frame.

    Args:
        object_name: Name of the object.
        data_path: Property data path (e.g., location, rotation_euler, scale).
        frame: Frame number of the keyframe to remove.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    data_path = _validate_data_path(data_path)
    frame = validate_numeric_range(frame, min_val=0, max_val=1048574, name="frame")

    conn = get_connection()
    response = conn.send_command("delete_keyframe", {
        "object_name": object_name,
        "data_path": data_path,
        "frame": frame,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_frame(frame: int) -> dict[str, Any]:
    """Set the current frame in the timeline.

    Args:
        frame: Frame number to set as current.

    Returns:
        Confirmation dict with the new current frame.
    """
    frame = validate_numeric_range(frame, min_val=0, max_val=1048574, name="frame")

    conn = get_connection()
    response = conn.send_command("set_frame", {"frame": frame})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_frame_range(start: int, end: int) -> dict[str, Any]:
    """Set the start and end frames of the scene timeline.

    Args:
        start: Start frame number.
        end: End frame number. Must be greater than start.

    Returns:
        Confirmation dict with the new frame range.
    """
    start = validate_numeric_range(start, min_val=0, max_val=1048574, name="start")
    end = validate_numeric_range(end, min_val=0, max_val=1048574, name="end")
    if end <= start:
        raise ValidationError(f"end ({end}) must be greater than start ({start})")

    conn = get_connection()
    response = conn.send_command("set_frame_range", {
        "start": start,
        "end": end,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_interpolation(
    object_name: str, data_path: str, interpolation: str = "BEZIER"
) -> dict[str, Any]:
    """Set the interpolation type for keyframes on a property.

    Args:
        object_name: Name of the object.
        data_path: Property data path.
        interpolation: Interpolation type. One of: CONSTANT, LINEAR, BEZIER, SINE,
            QUAD, CUBIC, QUART, QUINT, EXPO, CIRC, BACK, BOUNCE, ELASTIC.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    data_path = _validate_data_path(data_path)
    validate_enum(interpolation, ALLOWED_INTERPOLATIONS, name="interpolation")

    conn = get_connection()
    response = conn.send_command("set_interpolation", {
        "object_name": object_name,
        "data_path": data_path,
        "interpolation": interpolation,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def create_animation_path(object_name: str, path_object: str) -> dict[str, Any]:
    """Make an object follow a path (curve) using a Follow Path constraint.

    Args:
        object_name: Name of the object to animate along the path.
        path_object: Name of the curve object to use as the path.

    Returns:
        Confirmation dict with constraint details.
    """
    object_name = validate_object_name(object_name)
    path_object = validate_object_name(path_object)

    conn = get_connection()
    response = conn.send_command("create_animation_path", {
        "object_name": object_name,
        "path_object": path_object,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def list_keyframes(object_name: str) -> list[dict[str, Any]]:
    """List all keyframes on an object.

    Args:
        object_name: Name of the object.

    Returns:
        List of dicts with data_path, frame, and value for each keyframe.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("list_keyframes", {
        "object_name": object_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def clear_animation(object_name: str) -> dict[str, Any]:
    """Remove all animation data from an object.

    Args:
        object_name: Name of the object.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)

    conn = get_connection()
    response = conn.send_command("clear_animation", {
        "object_name": object_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


ALLOWED_DRIVER_TYPES = {"SCRIPTED", "AVERAGE", "SUM", "MIN", "MAX"}
ALLOWED_VARIABLE_TYPES = {"TRANSFORMS", "SINGLE_PROP", "LOC_DIFF", "ROTATION_DIFF"}
ALLOWED_TRANSFORM_TYPES = {
    "LOC_X", "LOC_Y", "LOC_Z", "ROT_X", "ROT_Y", "ROT_Z", "ROT_W",
    "SCALE_X", "SCALE_Y", "SCALE_Z", "SCALE_AVG",
}
ALLOWED_TRANSFORM_SPACES = {"WORLD_SPACE", "TRANSFORM_SPACE", "LOCAL_SPACE"}
MAX_DRIVER_VARIABLES = 32


def _send_animation_command(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _driver_variable(var: Any) -> dict[str, Any]:
    if not isinstance(var, dict):
        raise ValidationError("each variable must be an object")
    name = var.get("name")
    if not isinstance(name, str) or not VARIABLE_NAME_PATTERN.match(name):
        raise ValidationError(f"variable name {name!r} must start with a letter and use "
                              f"letters, digits and _, up to 32 characters")
    kind = validate_enum(var.get("type", "TRANSFORMS"), ALLOWED_VARIABLE_TYPES,
                         name="variable type")
    out: dict[str, Any] = {"name": name, "type": kind,
                           "object": validate_object_name(var.get("object", ""))}
    if kind == "TRANSFORMS":
        out["transform_type"] = validate_enum(var.get("transform_type", "LOC_X"),
                                              ALLOWED_TRANSFORM_TYPES, name="transform_type")
        out["transform_space"] = validate_enum(var.get("transform_space", "WORLD_SPACE"),
                                               ALLOWED_TRANSFORM_SPACES, name="transform_space")
    elif kind == "SINGLE_PROP":
        out["data_path"] = validate_data_path(var.get("data_path", ""))
    else:
        out["object_2"] = validate_object_name(var.get("object_2", ""))
    return out


@mcp.tool()
def add_driver(
    object_name: str,
    data_path: str,
    expression: str = "",
    index: int = -1,
    driver_type: str = "SCRIPTED",
    variables: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Drive a property from other properties or the frame: a door that opens
    as a handle turns, a wheel that spins as a car moves, a light that dims
    with distance.

    Expressions use Blender's simple subset, evaluated without Python:
    numbers, + - * / % //, comparisons, and/or/not, "a if c else b",
    parentheses, the variables below, frame, pi, and sin cos tan asin acos
    atan atan2 sqrt abs fabs floor ceil trunc round int min max radians
    degrees exp log pow fmod lerp clamp smoothstep. No ** (use pow).

    Args:
        object_name: Object that owns the driven property.
        data_path: Property to drive, e.g. "location", "rotation_euler",
            "data.energy" (a light's power), 'modifiers["Bend"].angle',
            'data.shape_keys.key_blocks["Smile"].value'. Paths into the
            object's data or shape keys are driven on that data.
        expression: SCRIPTED drivers only, e.g. "lx * 2" or "sin(frame / 10)".
        index: Component of a vector property (0, 1, 2 for X, Y, Z), or -1 for
            a single value.
        driver_type: SCRIPTED (use the expression), or AVERAGE, SUM, MIN, MAX
            of the variables.
        variables: Up to 32, each {"name", "type", "object", ...}:
            TRANSFORMS: "transform_type" LOC_X..SCALE_AVG, optional
                "transform_space" WORLD_SPACE (default), LOCAL_SPACE or
                TRANSFORM_SPACE.
            SINGLE_PROP: "data_path" on the object, e.g. "data.energy".
            LOC_DIFF / ROTATION_DIFF: distance or angle between "object" and
                "object_2".

    Returns:
        Dict with the driven path, index, expression and variables.
    """
    variables = variables or []
    if not isinstance(variables, list) or len(variables) > MAX_DRIVER_VARIABLES:
        raise ValidationError(f"variables must be a list of at most {MAX_DRIVER_VARIABLES}")
    clean_vars = [_driver_variable(v) for v in variables]
    names = [v["name"] for v in clean_vars]
    if len(set(names)) != len(names):
        raise ValidationError("variable names must be unique")
    driver_type = validate_enum(driver_type, ALLOWED_DRIVER_TYPES, name="driver_type")
    if driver_type == "SCRIPTED":
        expression = validate_driver_expression(expression, set(names))
    else:
        if not clean_vars:
            raise ValidationError(f"a {driver_type} driver needs at least one variable")
        expression = ""
    return _send_animation_command("add_driver", {
        "object_name": validate_object_name(object_name),
        "data_path": validate_data_path(data_path),
        "index": validate_int(index, -1, 3, name="index"),
        "driver_type": driver_type,
        "expression": expression,
        "variables": clean_vars,
    })


@mcp.tool()
def remove_driver(object_name: str, data_path: str, index: int = -1) -> dict[str, Any]:
    """Remove a driver so the property goes back to its own value.

    Args:
        object_name: Object that owns the driven property.
        data_path: The driven property, as given to add_driver.
        index: Component, or -1 for all components of the property.

    Returns:
        Dict with how many drivers were removed.
    """
    return _send_animation_command("remove_driver", {
        "object_name": validate_object_name(object_name),
        "data_path": validate_data_path(data_path),
        "index": validate_int(index, -1, 3, name="index"),
    })


@mcp.tool()
def list_drivers(object_name: str) -> dict[str, Any]:
    """List the drivers on an object with their expressions and variables.

    Args:
        object_name: Object to inspect.

    Returns:
        Dict with each driver's path, index, type, expression, variables and
        whether Blender considers it valid.
    """
    return _send_animation_command("list_drivers",
                                   {"object_name": validate_object_name(object_name)})
