"""MCP tools for Blender camera operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
    validate_enum,
    validate_numeric_range,
    validate_vector,
    validate_file_path,
    ValidationError,
)

# Allowed camera properties
ALLOWED_CAMERA_PROPERTIES = {
    "lens",
    "clip_start",
    "clip_end",
    "sensor_width",
    "sensor_height",
    "dof.use_dof",
    "dof.focus_distance",
    "dof.aperture_fstop",
    "ortho_scale",
    "shift_x",
    "shift_y",
    "type",
    "sensor_fit",
}

# Allowed camera types
ALLOWED_CAMERA_TYPES = {"PERSP", "ORTHO", "PANO"}

# Allowed sensor fit modes
ALLOWED_SENSOR_FIT = {"AUTO", "HORIZONTAL", "VERTICAL"}

# Allowed render output extensions
ALLOWED_RENDER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".exr", ".hdr"}


def _send_camera_command(command: str, params: dict[str, Any] | None = None) -> Any:
    """Send a camera command and handle errors."""
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def create_camera(
    name: str = "Camera",
    location: list = [0, 0, 0],
    rotation: list = [0, 0, 0],
    lens: float = 50.0,
) -> dict[str, Any]:
    """Create a new camera in the scene.

    Args:
        name: Name for the camera, default "Camera".
        location: XYZ location as [x, y, z], default [0, 0, 0].
        rotation: XYZ Euler rotation in radians as [x, y, z], default [0, 0, 0].
        lens: Focal length in mm, default 50.

    Returns:
        Confirmation dict with camera name and properties.
    """
    name = validate_object_name(name)
    location = list(validate_vector(location, size=3, name="location"))
    rotation = list(validate_vector(rotation, size=3, name="rotation"))
    validate_numeric_range(lens, min_val=1.0, max_val=500.0, name="lens")

    return _send_camera_command("create_camera", {
        "name": name,
        "location": location,
        "rotation": rotation,
        "lens": lens,
    })


@mcp.tool()
def set_camera_property(name: str, property: str, value: Any) -> dict[str, Any]:
    """Set a property on a camera.

    Args:
        name: Name of the camera object.
        property: Property to set. One of: lens, clip_start, clip_end, sensor_width,
                  sensor_height, dof.use_dof, dof.focus_distance, dof.aperture_fstop,
                  ortho_scale, shift_x, shift_y, type, sensor_fit.
        value: The value to set.

    Returns:
        Confirmation dict.
    """
    name = validate_object_name(name)
    validate_enum(property, ALLOWED_CAMERA_PROPERTIES, name="property")

    # Validate specific properties
    if property == "lens":
        validate_numeric_range(value, min_val=1.0, max_val=500.0, name="lens")
    elif property == "clip_start":
        validate_numeric_range(value, min_val=0.001, max_val=10000.0, name="clip_start")
    elif property == "clip_end":
        validate_numeric_range(value, min_val=0.1, max_val=100000.0, name="clip_end")
    elif property in ("sensor_width", "sensor_height"):
        validate_numeric_range(value, min_val=1.0, max_val=500.0, name=property)
    elif property == "dof.use_dof":
        if not isinstance(value, bool):
            raise ValidationError("dof.use_dof must be a boolean")
    elif property == "dof.focus_distance":
        validate_numeric_range(value, min_val=0.0, max_val=100000.0, name="dof.focus_distance")
    elif property == "dof.aperture_fstop":
        validate_numeric_range(value, min_val=0.1, max_val=128.0, name="dof.aperture_fstop")
    elif property == "ortho_scale":
        validate_numeric_range(value, min_val=0.001, max_val=100000.0, name="ortho_scale")
    elif property in ("shift_x", "shift_y"):
        validate_numeric_range(value, min_val=-10.0, max_val=10.0, name=property)
    elif property == "type":
        validate_enum(value, ALLOWED_CAMERA_TYPES, name="camera type")
    elif property == "sensor_fit":
        validate_enum(value, ALLOWED_SENSOR_FIT, name="sensor_fit")

    return _send_camera_command("set_camera_property", {
        "name": name,
        "property": property,
        "value": value,
    })


@mcp.tool()
def set_active_camera(name: str) -> dict[str, Any]:
    """Set the active scene camera.

    Args:
        name: Name of the camera object to make active.

    Returns:
        Confirmation dict.
    """
    name = validate_object_name(name)
    return _send_camera_command("set_active_camera", {"name": name})


@mcp.tool()
def point_camera_at(
    camera_name: str,
    target: str = "",
    location: list | None = None,
) -> dict[str, Any]:
    """Point a camera at an object or a specific location using a Track To constraint.

    Args:
        camera_name: Name of the camera object.
        target: Name of the target object to point at. Mutually exclusive with location.
        location: XYZ location to point at as [x, y, z]. Mutually exclusive with target.

    Returns:
        Confirmation dict.
    """
    camera_name = validate_object_name(camera_name)

    if not target and location is None:
        raise ValidationError("Must provide either 'target' object name or 'location'")
    if target and location is not None:
        raise ValidationError("Cannot provide both 'target' and 'location'")

    params: dict[str, Any] = {"camera_name": camera_name}
    if target:
        params["target"] = validate_object_name(target)
    if location is not None:
        params["location"] = list(validate_vector(location, size=3, name="location"))

    return _send_camera_command("point_camera_at", params)


@mcp.tool()
def capture_viewport(
    filepath: str = "",
    width: int = 1920,
    height: int = 1080,
) -> dict[str, Any]:
    """Render the viewport to a file or return as base64.

    Args:
        filepath: Optional absolute path for output image. If empty, returns base64-encoded image.
        width: Render width in pixels, default 1920.
        height: Render height in pixels, default 1080.

    Returns:
        Dict with filepath or base64 image data.
    """
    if filepath:
        filepath = validate_file_path(filepath, allowed_extensions=ALLOWED_RENDER_EXTENSIONS)
    validate_numeric_range(width, min_val=1, max_val=8192, name="width")
    validate_numeric_range(height, min_val=1, max_val=8192, name="height")

    return _send_camera_command("capture_viewport", {
        "filepath": filepath,
        "width": int(width),
        "height": int(height),
    })


@mcp.tool()
def set_camera_from_view() -> dict[str, Any]:
    """Match the active camera to the current 3D viewport view.

    Returns:
        Confirmation dict with the camera's new location and rotation.
    """
    return _send_camera_command("set_camera_from_view")
