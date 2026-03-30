"""Input validation and security utilities for blend-ai."""

import re
import os
from pathlib import Path

# Allowed file extensions for import/export
ALLOWED_IMPORT_EXTENSIONS = {".fbx", ".obj", ".gltf", ".glb", ".usd", ".usda", ".usdc", ".usdz", ".stl", ".ply", ".abc", ".dae", ".svg", ".x3d"}
ALLOWED_EXPORT_EXTENSIONS = {".fbx", ".obj", ".gltf", ".glb", ".usd", ".usda", ".usdc", ".usdz", ".stl", ".ply", ".abc", ".dae", ".svg", ".x3d"}

# Limits
MAX_OBJECT_NAME_LENGTH = 63  # Blender's internal limit
MAX_SUBDIVISION_LEVEL = 6
MAX_RENDER_RESOLUTION = 8192
MAX_RENDER_SAMPLES = 10000
MAX_ARRAY_COUNT = 1000
MAX_PARTICLE_COUNT = 1000000

# Safe object name pattern - alphanumeric, underscores, hyphens, spaces, dots
SAFE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-. ]+$")


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_object_name(name: str) -> str:
    """Validate and sanitize a Blender object name."""
    if not name or not isinstance(name, str):
        raise ValidationError("Object name must be a non-empty string")
    name = name.strip()
    if len(name) > MAX_OBJECT_NAME_LENGTH:
        raise ValidationError(f"Object name exceeds maximum length of {MAX_OBJECT_NAME_LENGTH}")
    if not SAFE_NAME_PATTERN.match(name):
        raise ValidationError(
            "Object name contains invalid characters. "
            "Only alphanumeric, underscores, hyphens, spaces, and dots are allowed."
        )
    return name


def validate_file_path(path: str, allowed_extensions: set[str] | None = None, must_exist: bool = False) -> str:
    """Validate a file path for safety.

    Checks:
    - Path is absolute
    - No path traversal sequences
    - Extension is in allowed set (if provided)
    - File exists (if must_exist=True)
    """
    if not path or not isinstance(path, str):
        raise ValidationError("File path must be a non-empty string")

    resolved = str(Path(path).resolve())

    # Check for null bytes (path traversal attack)
    if "\x00" in path:
        raise ValidationError("File path contains null bytes")

    if allowed_extensions is not None:
        ext = Path(resolved).suffix.lower()
        if ext not in allowed_extensions:
            raise ValidationError(
                f"File extension '{ext}' is not allowed. "
                f"Allowed: {', '.join(sorted(allowed_extensions))}"
            )

    if must_exist and not os.path.exists(resolved):
        raise ValidationError(f"File does not exist: {resolved}")

    return resolved


def validate_numeric_range(value: float | int, min_val: float | int | None = None, max_val: float | int | None = None, name: str = "value") -> float | int:
    """Validate a numeric value is within range."""
    if not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be a number")
    if min_val is not None and value < min_val:
        raise ValidationError(f"{name} must be >= {min_val}, got {value}")
    if max_val is not None and value > max_val:
        raise ValidationError(f"{name} must be <= {max_val}, got {value}")
    return value


def validate_color(color: list | tuple) -> tuple:
    """Validate an RGBA or RGB color value."""
    if not isinstance(color, (list, tuple)):
        raise ValidationError("Color must be a list or tuple")
    if len(color) not in (3, 4):
        raise ValidationError("Color must have 3 (RGB) or 4 (RGBA) components")
    for i, c in enumerate(color):
        if not isinstance(c, (int, float)) or c < 0.0 or c > 1.0:
            raise ValidationError(f"Color component {i} must be a float between 0.0 and 1.0")
    return tuple(color)


def validate_vector(vec: list | tuple, size: int = 3, name: str = "vector") -> tuple:
    """Validate a vector (e.g., location, rotation, scale)."""
    if not isinstance(vec, (list, tuple)):
        raise ValidationError(f"{name} must be a list or tuple")
    if len(vec) != size:
        raise ValidationError(f"{name} must have exactly {size} components")
    for i, v in enumerate(vec):
        if not isinstance(v, (int, float)):
            raise ValidationError(f"{name} component {i} must be a number")
    return tuple(vec)


def validate_enum(value: str, allowed: set[str], name: str = "value") -> str:
    """Validate a string is one of the allowed values."""
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string")
    if value not in allowed:
        raise ValidationError(f"{name} must be one of {sorted(allowed)}, got '{value}'")
    return value
