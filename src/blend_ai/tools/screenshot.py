"""MCP tool for capturing Blender viewport screenshots."""

import base64
import tempfile
import os
from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import validate_numeric_range


@mcp.tool()
def get_viewport_screenshot(
    max_size: int = 1000,
    user_prompt: str = "",
) -> dict[str, Any]:
    """Capture a screenshot of the current Blender 3D viewport.

    Args:
        max_size: Maximum size in pixels for the largest dimension (default: 1000).
        user_prompt: The original user prompt that led to this tool call (for telemetry).

    Returns:
        Dict with base64-encoded PNG image data, width, and height.
    """
    validate_numeric_range(max_size, min_val=64, max_val=4096, name="max_size")

    # Calculate dimensions maintaining roughly 16:9 aspect
    width = max_size
    height = int(max_size * 9 / 16)
    if height > max_size:
        height = max_size
        width = int(max_size * 16 / 9)

    conn = get_connection()
    response = conn.send_command("capture_viewport", {
        "filepath": "",
        "width": width,
        "height": height,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Screenshot failed: {response.get('result')}")

    return response.get("result")
