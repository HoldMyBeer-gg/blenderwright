"""MCP tools for Blender physics simulation operations."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    validate_object_name,
    validate_enum,
    validate_numeric_range,
    validate_vector,
    MAX_PARTICLE_COUNT,
    ValidationError,
)

ALLOWED_RIGID_BODY_TYPES = {"ACTIVE", "PASSIVE"}
ALLOWED_FLUID_TYPES = {"DOMAIN", "FLOW", "EFFECTOR"}
ALLOWED_DOMAIN_TYPES = {"GAS", "LIQUID"}
ALLOWED_EMIT_FROM = {"VERT", "FACE", "VOLUME"}
ALLOWED_PHYSICS_TYPES = {"RIGID_BODY", "CLOTH", "FLUID", "PARTICLE_SYSTEM"}
ALLOWED_PARTICLE_RENDER_TYPES = {"NONE", "PATH", "OBJECT", "COLLECTION"}


@mcp.tool()
def add_rigid_body(
    object_name: str,
    type: str = "ACTIVE",
    mass: float = 1.0,
    friction: float = 0.5,
    restitution: float = 0.0,
) -> dict[str, Any]:
    """Add a rigid body physics simulation to an object.

    Args:
        object_name: Name of the object.
        type: Rigid body type - ACTIVE (affected by physics) or PASSIVE (static collider).
        mass: Mass of the object in kg.
        friction: Surface friction coefficient (0.0-1.0).
        restitution: Bounciness (0.0-1.0).

    Returns:
        Confirmation dict with rigid body settings.
    """
    object_name = validate_object_name(object_name)
    validate_enum(type, ALLOWED_RIGID_BODY_TYPES, name="type")
    validate_numeric_range(mass, min_val=0.001, max_val=1000000.0, name="mass")
    validate_numeric_range(friction, min_val=0.0, max_val=1.0, name="friction")
    validate_numeric_range(restitution, min_val=0.0, max_val=1.0, name="restitution")

    conn = get_connection()
    response = conn.send_command("add_rigid_body", {
        "object_name": object_name,
        "type": type,
        "mass": mass,
        "friction": friction,
        "restitution": restitution,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_cloth_sim(
    object_name: str,
    quality: int = 5,
    mass: float = 0.3,
) -> dict[str, Any]:
    """Add a cloth physics simulation to an object.

    Args:
        object_name: Name of the mesh object.
        quality: Simulation quality steps (1-80).
        mass: Mass of the cloth in kg.

    Returns:
        Confirmation dict with cloth settings.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(quality, min_val=1, max_val=80, name="quality")
    validate_numeric_range(mass, min_val=0.001, max_val=1000.0, name="mass")

    conn = get_connection()
    response = conn.send_command("add_cloth_sim", {
        "object_name": object_name,
        "quality": int(quality),
        "mass": mass,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_fluid_sim(
    object_name: str,
    type: str = "DOMAIN",
    domain_type: str = "GAS",
) -> dict[str, Any]:
    """Add a fluid physics simulation to an object.

    Args:
        object_name: Name of the object.
        type: Fluid type - DOMAIN (container), FLOW (emitter), or EFFECTOR (obstacle).
        domain_type: Domain simulation type - GAS (smoke/fire) or LIQUID. Only used when type is DOMAIN.

    Returns:
        Confirmation dict with fluid settings.
    """
    object_name = validate_object_name(object_name)
    validate_enum(type, ALLOWED_FLUID_TYPES, name="type")
    if type == "DOMAIN":
        validate_enum(domain_type, ALLOWED_DOMAIN_TYPES, name="domain_type")

    conn = get_connection()
    response = conn.send_command("add_fluid_sim", {
        "object_name": object_name,
        "type": type,
        "domain_type": domain_type,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_particle_system(
    object_name: str,
    count: int = 1000,
    lifetime: float = 50.0,
    emit_from: str = "FACE",
) -> dict[str, Any]:
    """Add a particle system to an object.

    Args:
        object_name: Name of the mesh object.
        count: Number of particles (max 1000000).
        lifetime: Particle lifetime in frames.
        emit_from: Emission source - VERT, FACE, or VOLUME.

    Returns:
        Confirmation dict with particle system settings.
    """
    object_name = validate_object_name(object_name)
    validate_numeric_range(count, min_val=1, max_val=MAX_PARTICLE_COUNT, name="count")
    validate_numeric_range(lifetime, min_val=1.0, max_val=100000.0, name="lifetime")
    validate_enum(emit_from, ALLOWED_EMIT_FROM, name="emit_from")

    conn = get_connection()
    response = conn.send_command("add_particle_system", {
        "object_name": object_name,
        "count": int(count),
        "lifetime": lifetime,
        "emit_from": emit_from,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_physics_property(
    object_name: str,
    physics_type: str,
    property: str,
    value: Any,
) -> dict[str, Any]:
    """Set a property on an existing physics simulation.

    Args:
        object_name: Name of the object with the physics simulation.
        physics_type: Physics type - RIGID_BODY, CLOTH, FLUID, or PARTICLE_SYSTEM.
        property: Property name to set (depends on physics type).
        value: Value to set.

    Returns:
        Confirmation dict with property name and new value.
    """
    object_name = validate_object_name(object_name)
    validate_enum(physics_type, ALLOWED_PHYSICS_TYPES, name="physics_type")
    if not property or not isinstance(property, str):
        raise ValidationError("property must be a non-empty string")

    conn = get_connection()
    response = conn.send_command("set_physics_property", {
        "object_name": object_name,
        "physics_type": physics_type,
        "property": property,
        "value": value,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def bake_physics(
    object_name: str,
    physics_type: str = "",
) -> dict[str, Any]:
    """Bake a physics simulation for an object.

    Args:
        object_name: Name of the object with physics.
        physics_type: Optional physics type to bake. If empty, bakes all physics on the object.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    if physics_type:
        validate_enum(physics_type, ALLOWED_PHYSICS_TYPES, name="physics_type")

    conn = get_connection()
    response = conn.send_command("bake_physics", {
        "object_name": object_name,
        "physics_type": physics_type,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def delete_particle_system(
    object_name: str, particle_system_name: str = ""
) -> dict[str, Any]:
    """Remove a particle system from an object.

    Args:
        object_name: Name of the object.
        particle_system_name: Name of the particle system to remove.
            If empty, removes the first particle system.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    if particle_system_name:
        particle_system_name = validate_object_name(particle_system_name)

    conn = get_connection()
    response = conn.send_command("delete_particle_system", {
        "object_name": object_name,
        "particle_system_name": particle_system_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_particle_velocity(
    object_name: str,
    normal: float = 1.0,
    tangent: float = 0.0,
    object_align_factor: list[float] | tuple[float, ...] = (0, 0, 0),
) -> dict[str, Any]:
    """Set velocity settings for an object's particle system.

    Args:
        object_name: Name of the object with a particle system.
        normal: Velocity along face normals.
        tangent: Velocity along face tangents.
        object_align_factor: XYZ velocity factors relative to the object. 3-element vector.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    object_align_factor = validate_vector(object_align_factor, size=3, name="object_align_factor")

    conn = get_connection()
    response = conn.send_command("set_particle_velocity", {
        "object_name": object_name,
        "normal": normal,
        "tangent": tangent,
        "object_align_factor": list(object_align_factor),
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_particle_rendering(
    object_name: str,
    render_type: str = "PATH",
    instance_object: str = "",
    instance_collection: str = "",
) -> dict[str, Any]:
    """Set rendering mode for an object's particle system.

    Args:
        object_name: Name of the object with a particle system.
        render_type: Render type. One of: NONE, PATH, OBJECT, COLLECTION.
        instance_object: Object to instance (when render_type is OBJECT).
        instance_collection: Collection to instance (when render_type is COLLECTION).

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    validate_enum(render_type, ALLOWED_PARTICLE_RENDER_TYPES, name="render_type")
    if instance_object:
        instance_object = validate_object_name(instance_object)
    if instance_collection:
        instance_collection = validate_object_name(instance_collection)

    conn = get_connection()
    response = conn.send_command("set_particle_rendering", {
        "object_name": object_name,
        "render_type": render_type,
        "instance_object": instance_object,
        "instance_collection": instance_collection,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
