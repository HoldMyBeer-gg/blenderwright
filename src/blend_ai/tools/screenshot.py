"""MCP tool for capturing Blender viewport screenshots."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import validate_numeric_range, validate_enum

# Allowed screenshot capture modes
ALLOWED_SCREENSHOT_MODES = {"fast", "full"}


@mcp.tool()
def get_viewport_screenshot(
    max_size: int = 1000,
    mode: str = "fast",
) -> dict[str, Any]:
    """Capture a screenshot of the current Blender 3D viewport.

    Args:
        max_size: Maximum size in pixels for the largest dimension (default: 1000).
        mode: Capture mode - 'fast' for instant viewport capture using OpenGL
            (default), 'full' for a complete render through the active render
            engine.

    Returns:
        Dict with base64-encoded PNG image data, width, height, format, and mode.
    """
    validate_numeric_range(max_size, min_val=64, max_val=4096, name="max_size")
    validate_enum(mode, ALLOWED_SCREENSHOT_MODES, name="mode")

    # Calculate dimensions maintaining roughly 16:9 aspect
    width = max_size
    height = int(max_size * 9 / 16)
    if height > max_size:
        height = max_size
        width = int(max_size * 16 / 9)

    conn = get_connection()

    if mode == "fast":
        command = "fast_viewport_capture"
    else:
        command = "capture_viewport"

    response = conn.send_command(command, {
        "width": width,
        "height": height,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Screenshot failed: {response.get('result')}")

    return response.get("result")
