"""Input validation and security utilities for blenderwright."""

import math
import re
import os
import tempfile
from pathlib import Path
from typing import Any

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

# A whole number or a decimal written as text, with nothing else around it
INT_TEXT_PATTERN = re.compile(r"[+-]?\d+")
FLOAT_TEXT_PATTERN = re.compile(r"[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?")


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_object_name(name: str) -> str:
    """Validate and sanitize a Blender object name."""
    if not name or not isinstance(name, str):
        raise ValidationError("Object name must be a non-empty string")
    name = name.strip()
    if len(name) > MAX_OBJECT_NAME_LENGTH:
        raise ValidationError(
            f"Object names are at most {MAX_OBJECT_NAME_LENGTH} characters, so no object "
            f"has this name. Use the name returned when the object was created."
        )
    if not SAFE_NAME_PATTERN.match(name):
        raise ValidationError(
            "Object name contains invalid characters. "
            "Only alphanumeric, underscores, hyphens, spaces, and dots are allowed."
        )
    return name


def validate_new_name(name: str) -> str:
    """Validate the name for something about to be created.

    Same rules as validate_object_name, except that a name over Blender's
    limit is cut to fit rather than refused. A model that has just been told
    its shuttle lacks thermal tiles will name the next part in sixty-eight
    characters, and the refusal cost it seventeen rounds. Blender would cut
    it anyway; do it here and return what was used.
    """
    if not name or not isinstance(name, str):
        raise ValidationError("Object name must be a non-empty string")
    name = name.strip()[:MAX_OBJECT_NAME_LENGTH].rstrip("_-. ")
    return validate_object_name(name)


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

    # Before any path operation: os.path raises a bare ValueError on an
    # embedded null, which escapes as a stack trace instead of the clean
    # rejection this function exists to give.
    if "\x00" in path:
        raise ValidationError("File path contains null bytes")

    resolved = str(Path(path).resolve())

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


def default_output_path(filename: str) -> str:
    """A writable default for an output file: the system temp directory.

    /tmp was the default for years and does not exist on Windows, which
    nothing noticed until the directory check arrived.
    """
    return os.path.join(tempfile.gettempdir(), filename)


def validate_output_path(
    path: str,
    allowed_extensions: set[str] | None = None,
    allow_directory: bool = False,
) -> str:
    """Validate a path a tool will write to.

    validate_file_path checks the shape of the path; this also checks that
    the directory exists, because Blender's own failure for a missing one
    is a bare "cannot save". A model on a Mac sent /home/user/render.png,
    read that, and had nothing to go on. Name a directory that does exist.

    Args:
        path: The output path.
        allowed_extensions: As for validate_file_path.
        allow_directory: Accept an existing directory as the target. True for
            a frame prefix, where Blender appends the frame number itself.

    Returns:
        The resolved absolute path.
    """
    resolved = validate_file_path(path, allowed_extensions=allowed_extensions)
    if os.path.isdir(resolved):
        if allow_directory:
            return resolved
        raise ValidationError(
            f"{resolved} is a directory. Give the full path of the file to write, "
            f"including its name."
        )
    parent = os.path.dirname(resolved)
    if not os.path.isdir(parent):
        suggestion = os.path.join(tempfile.gettempdir(), os.path.basename(resolved))
        raise ValidationError(
            f"Directory {parent} does not exist on this machine. Use a directory "
            f"that does, for example {suggestion}"
        )
    return resolved


def coerce_scalar(value: Any) -> Any:
    """Turn a number or boolean that arrived as text back into its own type.

    A client that sees no type on a parameter may send 53.0 as "53.0", and
    Blender then refuses the string or stores it as text. Anything that is not
    plainly a number or a boolean is returned unchanged, so enum words such as
    "BOX" pass through.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    if INT_TEXT_PATTERN.fullmatch(text):
        return int(text)
    if FLOAT_TEXT_PATTERN.fullmatch(text):
        number = float(text)
        if math.isfinite(number):
            return number
    return value


def validate_numeric_range(value: float | int | str, min_val: float | int | None = None, max_val: float | int | None = None, name: str = "value") -> float | int:
    """Validate a numeric value is within range.

    Numeric strings are accepted and converted. Callers driving this through a
    language model routinely send "0.55" rather than 0.55, and the modifier
    handler already coerces for the same reason; rejecting here only cost a
    round trip before the caller sent the identical value unquoted.
    """
    if isinstance(value, bool):
        # bool is a subclass of int, and True is not a brightness.
        raise ValidationError(f"{name} must be a number")
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            raise ValidationError(f"{name} must be a number, got '{value}'") from None
    if not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be a number")
    if min_val is not None and value < min_val:
        raise ValidationError(f"{name} must be >= {min_val}, got {value}")
    if max_val is not None and value > max_val:
        # 3.1416 means pi. A caller that rounds must not be refused for the
        # rounding, so an angle within a hair of its cap is the cap. Only
        # angles: 10001 samples against a cap of 10000 is still over.
        if max_val <= math.tau and math.isclose(value, max_val, abs_tol=1e-3):
            return max_val
        # Every angle in this API is radians, and a caller reaching for 30 or
        # 90 is thinking in degrees. Saying only "must be <= 3.14159" is true
        # and useless; offer the conversion.
        if "angle" in name.lower() and max_val <= math.tau and value >= 2 * max_val:
            radians = math.radians(value)
            if radians <= max_val:
                raise ValidationError(
                    f"{name} must be <= {max_val}, got {value}. Angles are in "
                    f"radians: {value:g} degrees is {radians:.2f}."
                )
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


def validate_scale(vec: list | tuple, name: str = "scale") -> tuple:
    """Validate a scale vector, rejecting degenerate and mirrored values.

    A zero component collapses the object to no thickness, and a negative one
    mirrors it and inverts its normals. Both are almost always mistakes from a
    caller reasoning about a shape rather than a transform, and neither
    reports an error from Blender, so they are caught here instead.

    Args:
        vec: Scale as a 3-element list or tuple.
        name: Parameter name, used in error messages.

    Returns:
        The validated scale as a tuple.
    """
    vec = validate_vector(vec, size=3, name=name)
    axes = ("x", "y", "z")
    for i, v in enumerate(vec):
        if v == 0:
            raise ValidationError(
                f"{name} component {i} ({axes[i]}) is zero, which flattens the "
                f"object to no thickness. Every axis needs a positive size."
            )
        if v < 0:
            # Flipping along one axis is a half turn about either of the
            # other two. Name one so the fix is a single call.
            turn_about = axes[(i + 1) % 3]
            raise ValidationError(
                f"{name} component {i} ({axes[i]}) is negative, which mirrors "
                f"the object and inverts its normals. Use positive scale "
                f"{abs(v):g} and, to point the object the other way along "
                f"{axes[i]}, rotate it 180 degrees about {turn_about} with "
                f"set_rotation. For a mirrored copy, add a Mirror modifier."
            )
    return vec


def validate_enum(value: str, allowed: set[str], name: str = "value") -> str:
    """Validate a string is one of the allowed values."""
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string")
    if value not in allowed:
        raise ValidationError(f"{name} must be one of {sorted(allowed)}, got '{value}'")
    return value


# Per-modifier numeric ceilings. Blender accepts far higher values and then
# grinds: a Subdivision at level 11 is 4^11 faces per original face, and the
# socket's retry budget expires long before it returns. Keyed on modifier type
# so an unrelated property of the same name is not caught by accident.
MODIFIER_PROPERTY_LIMITS: dict[str, dict[str, tuple[float, float]]] = {
    "SUBSURF": {
        "levels": (0, MAX_SUBDIVISION_LEVEL),
        "render_levels": (0, MAX_SUBDIVISION_LEVEL),
    },
    "MULTIRES": {
        "levels": (0, MAX_SUBDIVISION_LEVEL),
        "render_levels": (0, MAX_SUBDIVISION_LEVEL),
        "sculpt_levels": (0, MAX_SUBDIVISION_LEVEL),
    },
    "ARRAY": {"count": (1, MAX_ARRAY_COUNT)},
    "BEVEL": {"segments": (1, 100)},
    "SCREW": {"steps": (1, 1000), "render_steps": (1, 1000), "iterations": (1, 100)},
    "REMESH": {"octree_depth": (1, 12)},
}


def validate_modifier_property_value(modifier_type: str, prop: str, value):
    """Bound a modifier property that can hang Blender if set too high.

    Args:
        modifier_type: The modifier's type, e.g. "SUBSURF".
        prop: The property being set.
        value: The value requested.

    Returns:
        The validated value, coerced from a numeric string where applicable,
        or the value untouched if no limit is known for it.
    """
    limits = MODIFIER_PROPERTY_LIMITS.get(modifier_type, {})
    if prop not in limits:
        return value
    low, high = limits[prop]
    value = validate_numeric_range(value, min_val=low, max_val=high,
                                   name=f"{modifier_type}.{prop}")
    return int(value) if float(value).is_integer() else value
