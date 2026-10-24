"""MCP tools for Blender animation operations."""

import re
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


ALLOWED_KEYFRAME_TARGETS = {"OBJECT", "WORLD", "SCENE"}
MAX_FRAME = 1_048_574
MAX_KEY_VALUE = 1_000_000.0


def _key_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(validate_numeric_range(value, min_val=-MAX_KEY_VALUE,
                                            max_val=MAX_KEY_VALUE, name="value"))
    if isinstance(value, list) and 1 <= len(value) <= 4:
        return [float(validate_numeric_range(v, min_val=-MAX_KEY_VALUE, max_val=MAX_KEY_VALUE,
                                             name="value")) for v in value]
    raise ValidationError("value must be a number, true/false, or a list of 1 to 4 numbers")


@mcp.tool()
def keyframe_property(
    data_path: str,
    frame: int,
    value: Any = None,
    object_name: str = "",
    target: str = "OBJECT",
    index: int = -1,
) -> dict[str, Any]:
    """Keyframe any animatable property: material colours, light power, world
    strength, modifier settings, camera lens and more.

    Optionally sets the value first, so "turn red at frame 24" is one call.
    For location, rotation and scale, insert_keyframe is simpler.

    Args:
        data_path: Property path from the target, e.g.
            'active_material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value',
            "data.energy" (light power), "data.lens" (camera),
            'modifiers["Bend"].angle',
            'node_tree.nodes["Background"].inputs["Strength"].default_value'
            (with target WORLD).
        frame: Frame to key.
        value: Value to set before keying: a number, true/false, or a list for
            colours and vectors. Omit to key the current value.
        object_name: The object the path starts from (target OBJECT).
        target: OBJECT, WORLD (the scene's world) or SCENE.
        index: One component of a vector or colour (0, 1, 2, 3), or -1 for all.

    Returns:
        Dict with the data block keyed, its path, the frame and the value.
    """
    target = validate_enum(target, ALLOWED_KEYFRAME_TARGETS, name="target")
    params: dict[str, Any] = {"target": target}
    if target == "OBJECT":
        if not object_name:
            raise ValidationError("object_name is required when target is OBJECT")
        params["object_name"] = validate_object_name(object_name)
    params.update({
        "data_path": validate_data_path(data_path),
        "frame": validate_int(frame, -MAX_FRAME, MAX_FRAME, name="frame"),
        "index": validate_int(index, -1, 3, name="index"),
    })
    if value is not None:
        params["value"] = _key_value(value)
    return _send_animation_command("keyframe_property", params)


ALLOWED_ACTION_OPERATIONS = {"LIST", "NEW", "ASSIGN", "UNASSIGN", "PUSH_DOWN"}
ALLOWED_BLEND_TYPES = {"REPLACE", "COMBINE", "ADD", "SUBTRACT", "MULTIPLY"}
ALLOWED_EXTRAPOLATIONS = {"NOTHING", "HOLD", "HOLD_FORWARD"}
ALLOWED_FCURVE_MODIFIERS = {"CYCLES", "NOISE", "STEPPED", "SMOOTH"}
FCURVE_SETTING_PATTERN = re.compile(r"^[a-z][a-z_]{0,31}$")


@mcp.tool()
def manage_action(object_name: str, operation: str, action_name: str = "") -> dict[str, Any]:
    """Work with an object's actions (its saved animations).

    Args:
        object_name: Animated object.
        operation: LIST (the file's actions and which one the object plays),
            NEW (start an empty action named action_name and assign it),
            ASSIGN (play an existing action; several objects can share one),
            UNASSIGN (stop playing the active action, keep it in the file),
            PUSH_DOWN (move the active action into an NLA strip so another
            action can be layered on top).
        action_name: Needed for NEW and ASSIGN.

    Returns:
        Dict with the object's active action and slot, and the file's actions.
    """
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "operation": validate_enum(operation, ALLOWED_ACTION_OPERATIONS, name="operation"),
    }
    if operation in ("NEW", "ASSIGN"):
        if not action_name:
            raise ValidationError(f"{operation} needs action_name")
        params["action_name"] = validate_object_name(action_name)
    return _send_animation_command("manage_action", params)


@mcp.tool()
def add_nla_strip(
    object_name: str,
    action_name: str,
    frame_start: int = 1,
    track_name: str = "",
    blend_type: str = "REPLACE",
    repeat: float = 1.0,
    scale: float = 1.0,
    extrapolation: str = "HOLD_FORWARD",
    blend_in: float = 0.0,
    blend_out: float = 0.0,
    influence: float | None = None,
) -> dict[str, Any]:
    """Place an action on the NLA timeline as a strip: repeat a walk cycle,
    sequence clips, or layer a wave on top of a walk.

    Args:
        object_name: Object to animate.
        action_name: Action to place.
        frame_start: Frame the strip starts.
        track_name: NLA track to put it on; created if missing. Empty adds a
            new track on top.
        blend_type: How it mixes with the tracks below: REPLACE, COMBINE
            (adds rotations properly, best for layering), ADD, SUBTRACT,
            MULTIPLY.
        repeat: Times to play the action, 0.1 to 1000.
        scale: Playback stretch, 0.01 to 100 (2 is half speed).
        extrapolation: After (and before) the strip: NOTHING, HOLD or
            HOLD_FORWARD.
        blend_in: Frames to fade in, 0 or more.
        blend_out: Frames to fade out, 0 or more.
        influence: Fixed strength 0.0 to 1.0; leave unset for full.

    Returns:
        Dict with the track, strip, and its frame range.
    """
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "action_name": validate_object_name(action_name),
        "frame_start": validate_int(frame_start, -MAX_FRAME, MAX_FRAME, name="frame_start"),
        "track_name": validate_object_name(track_name) if track_name else "",
        "blend_type": validate_enum(blend_type, ALLOWED_BLEND_TYPES, name="blend_type"),
        "repeat": float(validate_numeric_range(repeat, min_val=0.1, max_val=1000.0,
                                               name="repeat")),
        "scale": float(validate_numeric_range(scale, min_val=0.01, max_val=100.0, name="scale")),
        "extrapolation": validate_enum(extrapolation, ALLOWED_EXTRAPOLATIONS,
                                       name="extrapolation"),
        "blend_in": float(validate_numeric_range(blend_in, min_val=0.0, max_val=MAX_FRAME,
                                                 name="blend_in")),
        "blend_out": float(validate_numeric_range(blend_out, min_val=0.0, max_val=MAX_FRAME,
                                                  name="blend_out")),
    }
    if influence is not None:
        params["influence"] = float(validate_numeric_range(influence, min_val=0.0,
                                                           max_val=1.0, name="influence"))
    return _send_animation_command("add_nla_strip", params)


@mcp.tool()
def list_nla(object_name: str) -> dict[str, Any]:
    """List an object's NLA tracks and strips, top to bottom.

    Args:
        object_name: Animated object.

    Returns:
        Dict with each track and its strips (action, frames, blend, repeat).
    """
    return _send_animation_command("list_nla", {"object_name": validate_object_name(object_name)})


@mcp.tool()
def add_fcurve_modifier(
    object_name: str,
    data_path: str,
    modifier: str,
    index: int = -1,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add a modifier to animation curves of the object's active action.

    Args:
        object_name: Animated object.
        data_path: Animated property, e.g. "location", "rotation_euler".
        modifier: CYCLES (repeat the keys forever: settings mode_before /
            mode_after REPEAT, REPEAT_OFFSET for walking forward, MIRROR),
            NOISE (organic jitter: strength, scale, phase, offset, depth),
            STEPPED (stop-motion look: frame_step, frame_offset),
            SMOOTH (Gaussian smoothing: sigma, filter_width).
        index: One component (0, 1, 2) or -1 for every component.
        settings: Modifier settings by name, plain values.

    Returns:
        Dict with how many curves got the modifier.
    """
    clean: dict[str, Any] = {}
    for key, value in (settings or {}).items():
        if not isinstance(key, str) or not FCURVE_SETTING_PATTERN.match(key):
            raise ValidationError(f"Invalid modifier setting name: {key!r}")
        if isinstance(value, bool):
            clean[key] = value
        elif isinstance(value, (int, float)):
            clean[key] = validate_numeric_range(value, min_val=-MAX_KEY_VALUE,
                                                max_val=MAX_KEY_VALUE, name=key)
        elif isinstance(value, str) and len(value) <= 32 and value.isidentifier():
            clean[key] = value
        else:
            raise ValidationError(f"Modifier setting '{key}' must be a number, true/false "
                                  f"or an option name")
    return _send_animation_command("add_fcurve_modifier", {
        "object_name": validate_object_name(object_name),
        "data_path": validate_data_path(data_path),
        "index": validate_int(index, -1, 3, name="index"),
        "modifier": validate_enum(modifier, ALLOWED_FCURVE_MODIFIERS, name="modifier"),
        "settings": clean,
    })
