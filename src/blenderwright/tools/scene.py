"""MCP tools for Blender scene management."""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    ValidationError,
    validate_enum,
    validate_numeric_range,
    validate_object_name,
    validate_new_name,
    validate_vector,
)

# Allowed scene properties that can be set
ALLOWED_SCENE_PROPERTIES = {
    "frame_start",
    "frame_end",
    "frame_current",
    "frame_step",
    "fps",
    "unit_system",
    "render_engine",
    "use_gravity",
    "gravity",
}

# Allowed unit systems
ALLOWED_UNIT_SYSTEMS = {"NONE", "METRIC", "IMPERIAL"}

# Unit names per system, read from a live Blender 5.2.3 (the enums are dynamic).
_TIMES = {"ADAPTIVE", "DAYS", "HOURS", "MINUTES", "SECONDS", "MILLISECONDS", "MICROSECONDS"}
UNITS_BY_SYSTEM = {
    "METRIC": {
        "length_unit": {
            "ADAPTIVE", "KILOMETERS", "METERS", "CENTIMETERS", "MILLIMETERS", "MICROMETERS",
        },
        "mass_unit": {"ADAPTIVE", "TONNES", "KILOGRAMS", "GRAMS", "MILLIGRAMS"},
        "time_unit": _TIMES,
        "temperature_unit": {"ADAPTIVE", "KELVIN", "CELSIUS"},
    },
    "IMPERIAL": {
        "length_unit": {"ADAPTIVE", "MILES", "FEET", "INCHES", "THOU"},
        "mass_unit": {"ADAPTIVE", "TONNES", "CENTUM_WEIGHTS", "STONES", "POUNDS", "OUNCES"},
        "time_unit": _TIMES,
        "temperature_unit": {"ADAPTIVE", "KELVIN", "FAHRENHEIT"},
    },
}
ALLOWED_ROTATION_UNITS = {"DEGREES", "RADIANS"}

# Allowed render engines
# See tools/rendering.py: 4.2-4.4 use BLENDER_EEVEE_NEXT, 5.x uses BLENDER_EEVEE.
ALLOWED_RENDER_ENGINES = {
    "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH", "CYCLES",
}

# Extension catalog with keyword matching for proactive suggestions
EXTENSION_CATALOG = {
    "bool_tool": {
        "name": "Bool Tool",
        "description": "Boolean operations (union, difference, intersect) with automatic cleanup",
        "keywords": ["boolean", "union", "difference", "intersect", "cut", "subtract", "combine", "bool"],
    },
    "looptools": {
        "name": "LoopTools",
        "description": "Advanced loop editing (relax, space, circle, curve, flatten)",
        "keywords": ["loop", "edge loop", "relax", "circle", "curve", "flatten", "space", "ring"],
    },
    "node_wrangler": {
        "name": "Node Wrangler",
        "description": "Shader and geometry node editing shortcuts (lazy connect, preview, switch)",
        "keywords": ["shader", "node", "material", "texture", "geometry nodes", "compositor", "nodes"],
    },
    "print3d_toolbox": {
        "name": "3D Print Toolbox",
        "description": "Print checks that no ordinary mesh check catches: reversed normals, self-intersection, thin walls, overhangs. Needed by check_3d_printability",
        "keywords": ["3d print", "print", "printable", "printability", "stl", "slicer",
                     "manifold", "overhang", "wall thickness", "watertight", "solid"],
    },
}


@mcp.tool()
def get_scene_info() -> dict[str, Any]:
    """Get full scene information including object tree, hierarchy, counts, frame range, fps, and render engine.

    Returns a dict with scene name, object list with hierarchy, object type counts,
    frame range (start, end, current), fps, and active render engine.
    """
    conn = get_connection()
    response = conn.send_command("get_scene_info")
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_scene_property(property: str, value: Any) -> dict[str, Any]:
    """Set a scene property such as frame_start, frame_end, frame_current, fps, unit_system, or render_engine.

    Args:
        property: The scene property to set. Must be one of: frame_start, frame_end,
                  frame_current, frame_step, fps, unit_system, render_engine, use_gravity, gravity.
        value: The value to set the property to. Type depends on the property.

    Returns:
        Confirmation dict with the property name and new value.
    """
    validate_enum(property, ALLOWED_SCENE_PROPERTIES, name="property")

    # Validate specific property values
    if property in ("frame_start", "frame_end", "frame_current", "frame_step"):
        value = validate_numeric_range(value, min_val=0, max_val=1048574, name=property)
    elif property == "fps":
        value = validate_numeric_range(value, min_val=1, max_val=240, name="fps")
    elif property == "unit_system":
        validate_enum(value, ALLOWED_UNIT_SYSTEMS, name="unit_system")
    elif property == "render_engine":
        value = validate_enum(value, ALLOWED_RENDER_ENGINES, name="render_engine")
    elif property == "gravity":
        # Reached scene.gravity untouched, so a scalar raised
        # "TypeError: 'float' object is not iterable" from inside Blender.
        value = list(validate_vector(value, size=3, name="gravity"))
    elif property == "use_gravity":
        if not isinstance(value, bool):
            raise ValidationError(
                f"use_gravity must be true or false, got {value!r}"
            )

    conn = get_connection()
    response = conn.send_command("set_scene_property", {"property": property, "value": value})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_units(
    system: str | None = None,
    scale_length: float | None = None,
    length_unit: str | None = None,
    mass_unit: str | None = None,
    time_unit: str | None = None,
    temperature_unit: str | None = None,
    rotation: str | None = None,
    use_separate: bool | None = None,
) -> dict[str, Any]:
    """Set the scene's units, for real-world sizes (e.g. a 3D print in millimetres).

    Only the settings given are changed. Unit names depend on the system:
    METRIC lengths are KILOMETERS, METERS, CENTIMETERS, MILLIMETERS, MICROMETERS;
    IMPERIAL lengths are MILES, FEET, INCHES, THOU. ADAPTIVE picks per value.

    Args:
        system: NONE, METRIC or IMPERIAL. NONE takes no units.
        scale_length: Blender units to scene units, e.g. 0.001 so 1 unit reads 1 mm.
        length_unit: Display unit for lengths.
        mass_unit: METRIC: TONNES, KILOGRAMS, GRAMS, MILLIGRAMS; IMPERIAL: TONNES,
            CENTUM_WEIGHTS, STONES, POUNDS, OUNCES.
        time_unit: DAYS, HOURS, MINUTES, SECONDS, MILLISECONDS, MICROSECONDS.
        temperature_unit: KELVIN plus CELSIUS (METRIC) or FAHRENHEIT (IMPERIAL).
        rotation: DEGREES or RADIANS.
        use_separate: Show compound values like 1 m 20 cm.

    Returns:
        Every unit setting after the change.
    """
    params: dict[str, Any] = {}
    if system is not None:
        params["system"] = validate_enum(system, ALLOWED_UNIT_SYSTEMS, name="system")
    if scale_length is not None:
        params["scale_length"] = validate_numeric_range(
            scale_length, min_val=1e-9, max_val=1e9, name="scale_length"
        )
    units = {
        "length_unit": length_unit, "mass_unit": mass_unit,
        "time_unit": time_unit, "temperature_unit": temperature_unit,
    }
    for key, value in units.items():
        if value is None:
            continue
        if system == "NONE":
            raise ValidationError(f"system NONE takes no units; {key} needs METRIC or IMPERIAL")
        known = set().union(*(names[key] for names in UNITS_BY_SYSTEM.values()))
        validate_enum(value, known, name=key)
        if system is not None and value not in UNITS_BY_SYSTEM[system][key]:
            other = next(s for s, names in UNITS_BY_SYSTEM.items() if value in names[key])
            raise ValidationError(f"{key} {value} is {other}, not {system}")
        params[key] = value
    if rotation is not None:
        params["system_rotation"] = validate_enum(
            rotation, ALLOWED_ROTATION_UNITS, name="rotation"
        )
    if use_separate is not None:
        if not isinstance(use_separate, bool):
            raise ValidationError(f"use_separate must be true or false, got {use_separate!r}")
        params["use_separate"] = use_separate
    if not params:
        raise ValidationError("Give at least one unit setting to change")

    conn = get_connection()
    response = conn.send_command("set_units", params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def list_scenes() -> list[dict[str, Any]]:
    """List all scenes in the current Blender file.

    Returns a list of dicts, each containing the scene name and object count.
    """
    conn = get_connection()
    response = conn.send_command("list_scenes")
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def create_scene(name: str) -> dict[str, Any]:
    """Create a new scene.

    Args:
        name: Name for the new scene.

    Returns:
        Confirmation dict with the created scene name.
    """
    name = validate_new_name(name)
    conn = get_connection()
    response = conn.send_command("create_scene", {"name": name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def delete_scene(scene_name: str) -> dict[str, Any]:
    """Delete a scene by name.

    Args:
        scene_name: Name of the scene to delete. Cannot delete the last remaining scene.

    Returns:
        Confirmation dict.
    """
    scene_name = validate_object_name(scene_name)
    conn = get_connection()
    response = conn.send_command("delete_scene", {"name": scene_name})
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def suggest_extensions(task_description: str = "") -> dict[str, Any]:
    """Suggest helpful Blender extensions for a planned task.

    Analyzes the task description and recommends free Blender extensions
    that could improve the workflow. Already-installed extensions are excluded.

    Args:
        task_description: Description of the planned task. If empty, returns
            all extensions not currently installed.

    Returns:
        Dict with 'suggestions' list of recommended extensions and
        'installed' list of already-installed extension IDs.
    """
    conn = get_connection()
    response = conn.send_command("get_installed_extensions")
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    installed = response.get("result", {}).get("installed", [])

    task_lower = task_description.lower()
    suggestions = []
    for ext_id, info in EXTENSION_CATALOG.items():
        if ext_id in installed:
            continue
        if not task_description:
            suggestions.append({
                "extension_id": ext_id,
                "name": info["name"],
                "description": info["description"],
            })
        elif any(kw in task_lower for kw in info["keywords"]):
            suggestions.append({
                "extension_id": ext_id,
                "name": info["name"],
                "description": info["description"],
            })

    return {"suggestions": suggestions, "installed": installed}
