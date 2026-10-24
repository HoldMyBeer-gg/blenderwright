"""MCP tools for Blender physics simulation operations."""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_int,
    validate_new_name,
    coerce_scalar,
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
ALLOWED_BAKE_TYPES = ALLOWED_PHYSICS_TYPES | {"SOFT_BODY"}
# Force fields usable without extra setup (texture, guide curve, boids, fluid)
ALLOWED_FIELD_TYPES = {"FORCE", "WIND", "VORTEX", "MAGNET", "HARMONIC", "CHARGE",
                       "LENNARDJ", "TURBULENCE", "DRAG"}
ALLOWED_FALLOFF_TYPES = {"SPHERE", "TUBE", "PLANE"}
MAX_FIELD_STRENGTH = 100000.0
MAX_PLACEMENT = 1_000_000.0
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
    mass = validate_numeric_range(mass, min_val=0.001, max_val=1000000.0, name="mass")
    friction = validate_numeric_range(friction, min_val=0.0, max_val=1.0, name="friction")
    restitution = validate_numeric_range(restitution, min_val=0.0, max_val=1.0, name="restitution")

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
    quality = validate_numeric_range(quality, min_val=1, max_val=80, name="quality")
    mass = validate_numeric_range(mass, min_val=0.001, max_val=1000.0, name="mass")

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
    count = validate_numeric_range(count, min_val=1, max_val=MAX_PARTICLE_COUNT, name="count")
    lifetime = validate_numeric_range(lifetime, min_val=1.0, max_val=100000.0, name="lifetime")
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
    value = coerce_scalar(value)

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
        physics_type: Optional physics type to bake: RIGID_BODY, CLOTH, FLUID,
            PARTICLE_SYSTEM or SOFT_BODY. If empty, bakes all physics on the object.

    Returns:
        Confirmation dict.
    """
    object_name = validate_object_name(object_name)
    if physics_type:
        validate_enum(physics_type, ALLOWED_BAKE_TYPES, name="physics_type")

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


def _send_physics_command(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _placement(vec: Any, name: str) -> list[float]:
    validate_vector(vec, size=3, name=name)
    return [float(validate_numeric_range(v, min_val=-MAX_PLACEMENT, max_val=MAX_PLACEMENT,
                                         name=name)) for v in vec]


@mcp.tool()
def add_force_field(
    type: str,
    name: str = "",
    location: list[float] | tuple[float, ...] = (0, 0, 0),
    rotation: list[float] | tuple[float, ...] = (0, 0, 0),
    strength: float = 1.0,
    flow: float = 0.0,
    noise: float = 0.0,
    seed: int = 1,
    falloff_type: str = "SPHERE",
    falloff_power: float = 0.0,
    max_distance: float = 0.0,
) -> dict[str, Any]:
    """Add a force field that pushes cloth, particles, soft and rigid bodies.

    Args:
        type: WIND (blows along its local Z), TURBULENCE (random gusts),
            VORTEX (spins around Z), FORCE (pushes outward, negative pulls in),
            MAGNET, HARMONIC (springs to the centre), CHARGE, LENNARDJ (keeps
            things apart), DRAG (slows everything down).
        name: Name for the field object; empty uses the type.
        location: Position [x, y, z].
        rotation: Euler rotation in radians; aims WIND and VORTEX.
        strength: -100000 to 100000. Negative reverses the push.
        flow: Air flow, 0 to 100; for WIND it carries particles along.
        noise: Randomness added to the force, 0 to 100.
        seed: Noise seed, 1 to 128.
        falloff_type: SPHERE, TUBE or PLANE: the shape the force fades over.
        falloff_power: How fast it fades with distance, 0 to 10.
        max_distance: Range beyond which there is no force; 0 for unlimited.

    Returns:
        Dict with the field object's name and settings.
    """
    def ranged(value, lo, hi, label):
        return float(validate_numeric_range(value, min_val=lo, max_val=hi, name=label))

    return _send_physics_command("add_force_field", {
        "type": validate_enum(type, ALLOWED_FIELD_TYPES, name="type"),
        "name": validate_new_name(name) if name else "",
        "location": _placement(location, "location"),
        "rotation": _placement(rotation, "rotation"),
        "strength": ranged(strength, -MAX_FIELD_STRENGTH, MAX_FIELD_STRENGTH, "strength"),
        "flow": ranged(flow, 0.0, 100.0, "flow"),
        "noise": ranged(noise, 0.0, 100.0, "noise"),
        "seed": validate_int(seed, 1, 128, name="seed"),
        "falloff_type": validate_enum(falloff_type, ALLOWED_FALLOFF_TYPES, name="falloff_type"),
        "falloff_power": ranged(falloff_power, 0.0, 10.0, "falloff_power"),
        "max_distance": ranged(max_distance, 0.0, MAX_PLACEMENT, "max_distance"),
    })


@mcp.tool()
def add_collision(
    object_name: str,
    thickness: float = 0.02,
    damping: float = 0.1,
    friction: float = 5.0,
    stickiness: float = 0.0,
    permeability: float = 0.0,
) -> dict[str, Any]:
    """Make an object solid to cloth, particles and soft bodies.

    Without it, a cloth falls straight through the floor.

    Args:
        object_name: Mesh object to collide with.
        thickness: Outer collision distance, 0.001 to 1.0. Raise it if cloth
            pokes through.
        damping: How much bounce is lost, 0.0 to 1.0.
        friction: Cloth friction against the surface, 0 to 80.
        stickiness: Particles stick to the surface, 0 to 10.
        permeability: Share of particles that pass through, 0.0 to 1.0.

    Returns:
        Dict with the collision settings.
    """
    def ranged(value, lo, hi, label):
        return float(validate_numeric_range(value, min_val=lo, max_val=hi, name=label))

    return _send_physics_command("add_collision", {
        "object_name": validate_object_name(object_name),
        "thickness": ranged(thickness, 0.001, 1.0, "thickness"),
        "damping": ranged(damping, 0.0, 1.0, "damping"),
        "friction": ranged(friction, 0.0, 80.0, "friction"),
        "stickiness": ranged(stickiness, 0.0, 10.0, "stickiness"),
        "permeability": ranged(permeability, 0.0, 1.0, "permeability"),
    })


@mcp.tool()
def add_soft_body(
    object_name: str,
    mass: float = 1.0,
    goal: bool = True,
    goal_strength: float = 0.7,
    pull: float = 0.5,
    push: float = 0.5,
    bend: float = 0.0,
    damping: float = 0.5,
    friction: float = 0.5,
    self_collision: bool = False,
) -> dict[str, Any]:
    """Make an object soft and wobbly: jelly, cushions, bellies, antennae.

    Bake it with bake_physics. With goal on, vertices are pulled back to
    their shape (higher goal_strength is stiffer); with goal off the object
    sags and bounces freely, like a water balloon. Add collision to the floor.

    Args:
        object_name: Mesh object.
        mass: Vertex mass, 0.001 to 50.
        goal: Pull vertices back toward the original shape.
        goal_strength: How strongly, 0.0 to 1.0.
        pull: Edge stiffness when stretched, 0.0 to 0.999.
        push: Edge stiffness when squashed, 0.0 to 0.999.
        bend: Resistance to bending, 0 to 10.
        damping: Edge spring damping, 0 to 50.
        friction: Air friction, 0 to 50.
        self_collision: Stop the body passing through itself (slower).

    Returns:
        Dict with the soft body settings.
    """
    def ranged(value, lo, hi, label):
        return float(validate_numeric_range(value, min_val=lo, max_val=hi, name=label))

    return _send_physics_command("add_soft_body", {
        "object_name": validate_object_name(object_name),
        "mass": ranged(mass, 0.001, 50.0, "mass"),
        "goal": bool(goal),
        "goal_strength": ranged(goal_strength, 0.0, 1.0, "goal_strength"),
        "pull": ranged(pull, 0.0, 0.999, "pull"),
        "push": ranged(push, 0.0, 0.999, "push"),
        "bend": ranged(bend, 0.0, 10.0, "bend"),
        "damping": ranged(damping, 0.0, 50.0, "damping"),
        "friction": ranged(friction, 0.0, 50.0, "friction"),
        "self_collision": bool(self_collision),
    })
