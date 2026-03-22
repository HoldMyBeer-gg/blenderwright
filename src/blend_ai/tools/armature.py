"""MCP tools for Blender armature and rigging operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
    validate_enum,
    validate_vector,
    ValidationError,
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
}

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
    name = validate_object_name(name)
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
                        CHILD_OF, PIVOT, ARMATURE.
        properties: Optional dict of constraint properties to set (e.g., target, subtarget,
                   chain_count, influence, etc.).

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
        "properties": properties or {},
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
        scale = validate_vector(scale, size=3, name="scale")
        pose_params["scale"] = list(scale)

    conn = get_connection()
    response = conn.send_command("set_pose", pose_params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
