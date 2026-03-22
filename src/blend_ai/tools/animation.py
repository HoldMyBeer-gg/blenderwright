"""MCP tools for Blender animation operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
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
    object_name: str, data_path: str, frame: int, value: Any = None
) -> dict[str, Any]:
    """Insert a keyframe on an object property at a specific frame.

    Args:
        object_name: Name of the object.
        data_path: Property to keyframe. Must be one of: location, rotation_euler,
            rotation_quaternion, scale, or indexed variants like location[0].
        frame: Frame number to insert the keyframe at.
        value: Optional value to set before inserting the keyframe.

    Returns:
        Confirmation dict with keyframe details.
    """
    object_name = validate_object_name(object_name)
    data_path = _validate_data_path(data_path)
    validate_numeric_range(frame, min_val=0, max_val=1048574, name="frame")

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
    validate_numeric_range(frame, min_val=0, max_val=1048574, name="frame")

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
    validate_numeric_range(frame, min_val=0, max_val=1048574, name="frame")

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
    validate_numeric_range(start, min_val=0, max_val=1048574, name="start")
    validate_numeric_range(end, min_val=0, max_val=1048574, name="end")
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
