"""MCP tools for Blender armature and rigging operations."""

import re
from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    coerce_scalar,
    validate_int,
    validate_numeric_range,
    validate_object_name,
    validate_new_name,
    validate_enum,
    validate_vector,
    ValidationError,
    validate_scale,
)

# Allowed constraint types
ALLOWED_CONSTRAINT_TYPES = {
    "IK",
    "COPY_ROTATION",
    "COPY_LOCATION",
    "COPY_SCALE",
    "COPY_TRANSFORMS",
    "TRACK_TO",
    "DAMPED_TRACK",
    "LOCKED_TRACK",
    "LIMIT_ROTATION",
    "LIMIT_LOCATION",
    "LIMIT_SCALE",
    "STRETCH_TO",
    "FLOOR",
    "CLAMP_TO",
    "TRANSFORM",
    "MAINTAIN_VOLUME",
    "CHILD_OF",
    "PIVOT",
    "ARMATURE",
    "LIMIT_DISTANCE",
    "SPLINE_IK",
    "ACTION",
    "FOLLOW_PATH",
    "SHRINKWRAP",
    "GEOMETRY_ATTRIBUTE",
}
CONSTRAINT_PROPERTY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MAX_PROPERTY_TEXT = 64
ALLOWED_BONE_COLLECTION_ACTIONS = {"CREATE", "DELETE", "ASSIGN", "UNASSIGN", "SHOW", "HIDE"}
MAX_BONES = 1000

# Allowed bone properties
ALLOWED_BONE_PROPERTIES = {
    "roll",
    "length",
    "use_connect",
    "use_deform",
    "envelope_distance",
    "head_radius",
    "tail_radius",
    "use_inherit_rotation",
    "use_local_location",
}

# Allowed parenting types
ALLOWED_PARENT_TYPES = {"ARMATURE_AUTO", "ARMATURE_NAME", "ARMATURE_ENVELOPE"}


@mcp.tool()
def create_armature(
    name: str = "Armature",
    location: list[float] | tuple[float, ...] = (0, 0, 0),
) -> dict[str, Any]:
    """Create a new armature object.

    Args:
        name: Name for the armature. Defaults to "Armature".
        location: XYZ position for the armature. Defaults to origin.

    Returns:
        Dict with the created armature's name and location.
    """
    name = validate_new_name(name)
    location = validate_vector(location, size=3, name="location")

    conn = get_connection()
    response = conn.send_command("create_armature", {
        "name": name,
        "location": list(location),
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_bone(
    armature_name: str,
    bone_name: str,
    head: list[float] | tuple[float, ...] = (0, 0, 0),
    tail: list[float] | tuple[float, ...] = (0, 0, 1),
    parent_bone: str = "",
) -> dict[str, Any]:
    """Add a bone to an armature. Enters edit mode automatically.

    Args:
        armature_name: Name of the armature object.
        bone_name: Name for the new bone.
        head: XYZ position of the bone head (root). Defaults to (0, 0, 0).
        tail: XYZ position of the bone tail (tip). Defaults to (0, 0, 1).
        parent_bone: Optional name of the parent bone for hierarchy.

    Returns:
        Dict with the created bone's name, head, and tail positions.
    """
    armature_name = validate_object_name(armature_name)
    bone_name = validate_object_name(bone_name)
    head = validate_vector(head, size=3, name="head")
    tail = validate_vector(tail, size=3, name="tail")
    if head == tail:
        raise ValidationError(
            "head and tail are the same point, so the bone has zero "
            "length. Blender discards those when leaving edit mode, so "
            "the bone would be reported as created and not exist."
        )
    if parent_bone:
        parent_bone = validate_object_name(parent_bone)

    conn = get_connection()
    response = conn.send_command("add_bone", {
        "armature_name": armature_name,
        "bone_name": bone_name,
        "head": list(head),
        "tail": list(tail),
        "parent_bone": parent_bone,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_bone_property(
    armature_name: str,
    bone_name: str,
    property: str,
    value: Any,
) -> dict[str, Any]:
    """Set a property on a bone in an armature.

    Args:
        armature_name: Name of the armature object.
        bone_name: Name of the bone.
        property: Property to set. One of: roll, length, use_connect, use_deform,
                  envelope_distance, head_radius, tail_radius, use_inherit_rotation,
                  use_local_location.
        value: Value to set the property to.

    Returns:
        Confirmation dict with bone name, property, and new value.
    """
    armature_name = validate_object_name(armature_name)
    bone_name = validate_object_name(bone_name)
    validate_enum(property, ALLOWED_BONE_PROPERTIES, name="property")
    value = coerce_scalar(value)

    conn = get_connection()
    response = conn.send_command("set_bone_property", {
        "armature_name": armature_name,
        "bone_name": bone_name,
        "property": property,
        "value": value,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _constraint_properties(properties: Any) -> dict[str, Any]:
    """Setting names and plain values only; the add-on checks them against RNA."""
    if not isinstance(properties, dict):
        raise ValidationError("properties must be an object of setting name to value")
    clean: dict[str, Any] = {}
    for key, value in properties.items():
        if not isinstance(key, str) or not CONSTRAINT_PROPERTY_PATTERN.match(key):
            raise ValidationError(f"Invalid constraint setting name: {key!r}")
        if isinstance(value, bool) or (isinstance(value, str) and len(value) <= MAX_PROPERTY_TEXT
                                       and value.isprintable()):
            clean[key] = value
        elif isinstance(value, (int, float)):
            clean[key] = validate_numeric_range(value, name=key)
        else:
            raise ValidationError(f"Constraint setting '{key}' must be a number, true/false "
                                  f"or short text")
    return clean


@mcp.tool()
def add_constraint(
    object_name: str,
    bone_name: str = "",
    constraint_type: str = "",
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add a constraint to an object or bone.

    Args:
        object_name: Name of the object (armature for bone constraints).
        bone_name: Name of the bone (empty string for object-level constraints).
        constraint_type: Constraint type. One of: IK, COPY_ROTATION, COPY_LOCATION,
                        COPY_SCALE, COPY_TRANSFORMS, TRACK_TO, DAMPED_TRACK,
                        LOCKED_TRACK, LIMIT_ROTATION, LIMIT_LOCATION, LIMIT_SCALE,
                        STRETCH_TO, FLOOR, CLAMP_TO, TRANSFORM, MAINTAIN_VOLUME,
                        CHILD_OF, PIVOT, ARMATURE, LIMIT_DISTANCE, SPLINE_IK,
                        ACTION, FOLLOW_PATH, SHRINKWRAP, GEOMETRY_ATTRIBUTE.
        properties: Optional dict of the constraint's own settings, e.g. target (an
                   object name), subtarget (a bone name), influence, chain_count,
                   owner_space. Only settings Blender declares on that constraint
                   type are accepted. For a full IK setup use setup_ik_chain.

    Returns:
        Dict with the created constraint's name and type.
    """
    object_name = validate_object_name(object_name)
    if bone_name:
        bone_name = validate_object_name(bone_name)
    if not constraint_type:
        raise ValidationError("constraint_type must be specified")
    validate_enum(constraint_type, ALLOWED_CONSTRAINT_TYPES, name="constraint_type")

    conn = get_connection()
    response = conn.send_command("add_constraint", {
        "object_name": object_name,
        "bone_name": bone_name,
        "constraint_type": constraint_type,
        "properties": _constraint_properties(properties or {}),
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def parent_mesh_to_armature(
    mesh_name: str,
    armature_name: str,
    type: str = "ARMATURE_AUTO",
) -> dict[str, Any]:
    """Parent a mesh object to an armature with automatic weights or other methods.

    Args:
        mesh_name: Name of the mesh object to parent.
        armature_name: Name of the armature object.
        type: Parenting method. One of: ARMATURE_AUTO (automatic weights),
              ARMATURE_NAME (by bone names), ARMATURE_ENVELOPE (by envelope).

    Returns:
        Confirmation dict.
    """
    mesh_name = validate_object_name(mesh_name)
    armature_name = validate_object_name(armature_name)
    validate_enum(type, ALLOWED_PARENT_TYPES, name="type")

    conn = get_connection()
    response = conn.send_command("parent_mesh_to_armature", {
        "mesh_name": mesh_name,
        "armature_name": armature_name,
        "type": type,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_pose(
    armature_name: str,
    bone_name: str,
    location: list[float] | tuple[float, ...] | None = None,
    rotation: list[float] | tuple[float, ...] | None = None,
    scale: list[float] | tuple[float, ...] | None = None,
) -> dict[str, Any]:
    """Set the pose of a bone in an armature.

    Args:
        armature_name: Name of the armature object.
        bone_name: Name of the bone to pose.
        location: Optional XYZ location offset for the bone.
        rotation: Optional XYZ Euler rotation in radians.
        scale: Optional XYZ scale.

    Returns:
        Confirmation dict with the bone's new pose values.
    """
    armature_name = validate_object_name(armature_name)
    bone_name = validate_object_name(bone_name)

    pose_params: dict[str, Any] = {
        "armature_name": armature_name,
        "bone_name": bone_name,
    }

    if location is not None:
        location = validate_vector(location, size=3, name="location")
        pose_params["location"] = list(location)
    if rotation is not None:
        rotation = validate_vector(rotation, size=3, name="rotation")
        pose_params["rotation"] = list(rotation)
    if scale is not None:
        scale = validate_scale(scale, name="scale")
        pose_params["scale"] = list(scale)

    conn = get_connection()
    response = conn.send_command("set_pose", pose_params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _send_armature_command(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def manage_bone_collection(
    armature_name: str,
    action: str,
    collection_name: str,
    bones: list[str] | None = None,
    parent: str = "",
) -> dict[str, Any]:
    """Organise an armature's bones into collections and show or hide them.

    Typical rig layout: "Deform" (hidden), "Controls" (visible),
    "Mechanism" (hidden).

    Args:
        armature_name: Armature object.
        action: CREATE (optionally with bones and a parent collection), DELETE,
            ASSIGN or UNASSIGN bones, SHOW or HIDE the collection.
        collection_name: Bone collection to act on.
        bones: Bone names for CREATE, ASSIGN and UNASSIGN, at most 1000.
        parent: CREATE only: nest under this existing collection.

    Returns:
        Dict with the armature's collections, their bones and visibility.
    """
    clean_bones: list[str] = []
    if bones is not None:
        if not isinstance(bones, list) or len(bones) > MAX_BONES:
            raise ValidationError(f"bones must be a list of at most {MAX_BONES} bone names")
        for bone in bones:
            bone = validate_object_name(bone)
            if bone not in clean_bones:
                clean_bones.append(bone)
    return _send_armature_command("manage_bone_collection", {
        "armature_name": validate_object_name(armature_name),
        "action": validate_enum(action, ALLOWED_BONE_COLLECTION_ACTIONS, name="action"),
        "collection_name": validate_object_name(collection_name),
        "bones": clean_bones,
        "parent": validate_object_name(parent) if parent else "",
    })


@mcp.tool()
def setup_ik_chain(
    armature_name: str,
    bone_name: str,
    target_object: str,
    target_bone: str = "",
    chain_count: int = 2,
    pole_object: str = "",
    pole_bone: str = "",
    pole_angle: float = 0.0,
    use_stretch: bool = False,
    iterations: int = 500,
) -> dict[str, Any]:
    """Give a limb inverse kinematics: move the target and the chain follows.

    Put the IK on the last bone of the limb (forearm, shin). A pole target
    (an empty or bone in front of the knee or behind the elbow) keeps the
    joint bending the right way.

    Args:
        armature_name: Armature object.
        bone_name: Last bone of the chain (the IK sits on it).
        target_object: Object the chain reaches for (often the armature itself
            when target_bone names a control bone).
        target_bone: Bone in target_object to reach for, if any.
        chain_count: Bones in the chain counting up from bone_name, 0 to 255
            (0 means the whole chain to the root).
        pole_object: Object that sets the joint's bend direction, if any.
        pole_bone: Bone in pole_object, if any.
        pole_angle: Rotate the pole's effect, radians, -3.142 to 3.142;
            -1.571 (-90 degrees) is a common fix for a twisted limb.
        use_stretch: Let bones stretch to reach a target out of range.
        iterations: Solver iterations, 1 to 10000.

    Returns:
        Dict with the constraint and chain details.
    """
    return _send_armature_command("setup_ik_chain", {
        "armature_name": validate_object_name(armature_name),
        "bone_name": validate_object_name(bone_name),
        "target_object": validate_object_name(target_object),
        "target_bone": validate_object_name(target_bone) if target_bone else "",
        "chain_count": validate_int(chain_count, 0, 255, name="chain_count"),
        "pole_object": validate_object_name(pole_object) if pole_object else "",
        "pole_bone": validate_object_name(pole_bone) if pole_bone else "",
        "pole_angle": validate_numeric_range(pole_angle, min_val=-3.1416, max_val=3.1416,
                                             name="pole_angle"),
        "use_stretch": bool(use_stretch),
        "iterations": validate_int(iterations, 1, 10000, name="iterations"),
    })
