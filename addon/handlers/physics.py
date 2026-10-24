"""Blender addon handlers for physics simulation commands."""

import bpy
from .. import dispatcher

# Allowed properties per physics type for set_physics_property
ALLOWED_RIGID_BODY_PROPS = {
    "mass", "friction", "restitution", "collision_shape", "kinematic",
    "linear_damping", "angular_damping", "use_margin", "collision_margin",
}
ALLOWED_CLOTH_PROPS = {
    "quality", "mass", "air_damping", "tension_stiffness", "compression_stiffness",
    "shear_stiffness", "bending_stiffness", "use_pressure", "uniform_pressure_force",
}
ALLOWED_FLUID_PROPS = {
    "domain_type", "resolution_max", "use_adaptive_domain",
    "use_noise", "use_mesh", "use_diffusion",
}
ALLOWED_PARTICLE_PROPS = {
    "count", "lifetime", "emit_from", "normal_factor", "factor_random",
    "physics_type", "size", "mass", "use_multiply_size_mass",
}


def handle_add_rigid_body(params: dict) -> dict:
    """Add a rigid body to an object."""
    object_name = params.get("object_name")
    rb_type = params.get("type", "ACTIVE")
    mass = params.get("mass", 1.0)
    friction = params.get("friction", 0.5)
    restitution = params.get("restitution", 0.0)

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        # Select and make active
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        bpy.ops.rigidbody.object_add(type=rb_type)

        rb = obj.rigid_body
        rb.mass = float(mass)
        rb.friction = float(friction)
        rb.restitution = float(restitution)

        return {
            "object_name": obj.name,
            "type": rb_type,
            "mass": rb.mass,
            "friction": rb.friction,
            "restitution": rb.restitution,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to add rigid body: {e}")


def handle_add_cloth_sim(params: dict) -> dict:
    """Add a cloth simulation to an object."""
    object_name = params.get("object_name")
    quality = params.get("quality", 5)
    mass = params.get("mass", 0.3)

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")
        if obj.type != "MESH":
            raise ValueError(f"Object '{object_name}' is not a mesh (type: {obj.type})")

        # Select and make active
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        bpy.ops.object.modifier_add(type='CLOTH')

        cloth = obj.modifiers[-1].settings
        cloth.quality = int(quality)
        cloth.mass = float(mass)

        return {
            "object_name": obj.name,
            "quality": cloth.quality,
            "mass": cloth.mass,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to add cloth sim: {e}")


def handle_add_fluid_sim(params: dict) -> dict:
    """Add a fluid simulation to an object."""
    object_name = params.get("object_name")
    fluid_type = params.get("type", "DOMAIN")
    domain_type = params.get("domain_type", "GAS")

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        # Select and make active
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        bpy.ops.object.modifier_add(type='FLUID')

        # Get the fluid modifier
        fluid_mod = None
        for mod in obj.modifiers:
            if mod.type == 'FLUID':
                fluid_mod = mod
                break

        if fluid_mod is None:
            raise RuntimeError("Failed to find fluid modifier after adding it")

        fluid_mod.fluid_type = fluid_type

        if fluid_type == "DOMAIN" and fluid_mod.domain_settings is not None:
            fluid_mod.domain_settings.domain_type = domain_type

        return {
            "object_name": obj.name,
            "fluid_type": fluid_type,
            "domain_type": domain_type if fluid_type == "DOMAIN" else None,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to add fluid sim: {e}")


def handle_add_particle_system(params: dict) -> dict:
    """Add a particle system to an object."""
    object_name = params.get("object_name")
    count = params.get("count", 1000)
    lifetime = params.get("lifetime", 50.0)
    emit_from = params.get("emit_from", "FACE")

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")
        if obj.type != "MESH":
            raise ValueError(f"Object '{object_name}' is not a mesh (type: {obj.type})")

        # Select and make active
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        bpy.ops.object.particle_system_add()

        ps = obj.particle_systems[-1]
        settings = ps.settings
        settings.count = int(count)
        settings.lifetime = float(lifetime)
        settings.emit_from = emit_from

        return {
            "object_name": obj.name,
            "particle_system_name": ps.name,
            "count": settings.count,
            "lifetime": settings.lifetime,
            "emit_from": settings.emit_from,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to add particle system: {e}")


def handle_set_physics_property(params: dict) -> dict:
    """Set a property on an existing physics simulation."""
    object_name = params.get("object_name")
    physics_type = params.get("physics_type")
    prop = params.get("property")
    value = params.get("value")

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        if physics_type == "RIGID_BODY":
            if obj.rigid_body is None:
                raise ValueError(f"Object '{object_name}' has no rigid body")
            if prop not in ALLOWED_RIGID_BODY_PROPS:
                raise ValueError(f"Property '{prop}' not allowed for rigid body. Allowed: {sorted(ALLOWED_RIGID_BODY_PROPS)}")
            setattr(obj.rigid_body, prop, value)
            actual = getattr(obj.rigid_body, prop)

        elif physics_type == "CLOTH":
            cloth_mod = None
            for mod in obj.modifiers:
                if mod.type == 'CLOTH':
                    cloth_mod = mod
                    break
            if cloth_mod is None:
                raise ValueError(f"Object '{object_name}' has no cloth modifier")
            if prop not in ALLOWED_CLOTH_PROPS:
                raise ValueError(f"Property '{prop}' not allowed for cloth. Allowed: {sorted(ALLOWED_CLOTH_PROPS)}")
            setattr(cloth_mod.settings, prop, value)
            actual = getattr(cloth_mod.settings, prop)

        elif physics_type == "FLUID":
            fluid_mod = None
            for mod in obj.modifiers:
                if mod.type == 'FLUID':
                    fluid_mod = mod
                    break
            if fluid_mod is None:
                raise ValueError(f"Object '{object_name}' has no fluid modifier")
            if prop not in ALLOWED_FLUID_PROPS:
                raise ValueError(f"Property '{prop}' not allowed for fluid. Allowed: {sorted(ALLOWED_FLUID_PROPS)}")
            if fluid_mod.domain_settings is not None:
                setattr(fluid_mod.domain_settings, prop, value)
                actual = getattr(fluid_mod.domain_settings, prop)
            else:
                raise ValueError("Fluid modifier has no domain settings to modify")

        elif physics_type == "PARTICLE_SYSTEM":
            if len(obj.particle_systems) == 0:
                raise ValueError(f"Object '{object_name}' has no particle systems")
            if prop not in ALLOWED_PARTICLE_PROPS:
                raise ValueError(f"Property '{prop}' not allowed for particles. Allowed: {sorted(ALLOWED_PARTICLE_PROPS)}")
            settings = obj.particle_systems[0].settings
            setattr(settings, prop, value)
            actual = getattr(settings, prop)  # noqa: F841

        else:
            raise ValueError(f"Unknown physics type: {physics_type}")

        return {
            "object_name": obj.name,
            "physics_type": physics_type,
            "property": prop,
            "value": value,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set physics property: {e}")


def _bake_cache(point_cache):
    """Bake one point cache; ptcache.bake reads it from the context."""
    with bpy.context.temp_override(point_cache=point_cache):
        bpy.ops.ptcache.bake(bake=True)


def handle_bake_physics(params: dict) -> dict:
    """Bake a physics simulation."""
    object_name = params.get("object_name")
    physics_type = params.get("physics_type", "")

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        # Select and make active
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        baked = []

        if physics_type == "RIGID_BODY" or (not physics_type and obj.rigid_body):
            # Rigid body bake is done through the scene's rigid body world
            scene = bpy.context.scene
            if scene.rigidbody_world is not None:
                point_cache = scene.rigidbody_world.point_cache
                point_cache.frame_start = scene.frame_start
                point_cache.frame_end = scene.frame_end
                _bake_cache(point_cache)
                baked.append("RIGID_BODY")

        if physics_type == "CLOTH" or not physics_type:
            for mod in obj.modifiers:
                if mod.type == 'CLOTH':
                    _bake_cache(mod.point_cache)
                    baked.append("CLOTH")
                    break

        if physics_type == "PARTICLE_SYSTEM" or not physics_type:
            for ps in obj.particle_systems:
                _bake_cache(ps.point_cache)
                baked.append("PARTICLE_SYSTEM")
                break

        if physics_type == "SOFT_BODY" or not physics_type:
            for mod in obj.modifiers:
                if mod.type == 'SOFT_BODY':
                    _bake_cache(mod.point_cache)
                    baked.append("SOFT_BODY")
                    break

        if physics_type == "FLUID" or not physics_type:
            for mod in obj.modifiers:
                if mod.type == 'FLUID' and mod.domain_settings is not None:
                    bpy.ops.fluid.bake_all()
                    baked.append("FLUID")
                    break

        if not baked:
            raise ValueError(f"No bakeable physics found on '{object_name}'" +
                             (f" for type '{physics_type}'" if physics_type else ""))

        return {
            "object_name": obj.name,
            "baked": baked,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to bake physics: {e}")


def handle_delete_particle_system(params: dict) -> dict:
    """Remove a particle system from an object."""
    object_name = params.get("object_name")
    ps_name = params.get("particle_system_name", "")

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        if len(obj.particle_systems) == 0:
            raise ValueError(f"Object '{object_name}' has no particle systems")

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        if ps_name:
            idx = None
            for i, ps in enumerate(obj.particle_systems):
                if ps.name == ps_name:
                    idx = i
                    break
            if idx is None:
                raise ValueError(f"Particle system '{ps_name}' not found on '{object_name}'")
            obj.particle_systems.active_index = idx

        bpy.ops.object.particle_system_remove()

        return {
            "object_name": obj.name,
            "removed": ps_name or "active",
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to delete particle system: {e}")


def handle_set_particle_velocity(params: dict) -> dict:
    """Set velocity settings for a particle system."""
    object_name = params.get("object_name")
    normal = params.get("normal", 1.0)
    tangent = params.get("tangent", 0.0)
    factor = params.get("object_align_factor", (0, 0, 0))

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        if len(obj.particle_systems) == 0:
            raise ValueError(f"Object '{object_name}' has no particle systems")

        settings = obj.particle_systems[0].settings
        settings.normal_factor = float(normal)
        settings.tangent_factor = float(tangent)
        settings.object_align_factor = tuple(factor)

        return {
            "object_name": obj.name,
            "normal": settings.normal_factor,
            "tangent": settings.tangent_factor,
            "object_align_factor": list(settings.object_align_factor),
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set particle velocity: {e}")


def handle_set_particle_rendering(params: dict) -> dict:
    """Set rendering mode for a particle system."""
    object_name = params.get("object_name")
    render_type = params.get("render_type", "PATH")
    instance_object = params.get("instance_object", "")
    instance_collection = params.get("instance_collection", "")

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        if len(obj.particle_systems) == 0:
            raise ValueError(f"Object '{object_name}' has no particle systems")

        settings = obj.particle_systems[0].settings
        settings.render_type = render_type

        if render_type == "OBJECT" and instance_object:
            inst_obj = bpy.data.objects.get(instance_object)
            if inst_obj is None:
                raise ValueError(f"Instance object '{instance_object}' not found")
            settings.instance_object = inst_obj

        if render_type == "COLLECTION" and instance_collection:
            coll = bpy.data.collections.get(instance_collection)
            if coll is None:
                raise ValueError(f"Collection '{instance_collection}' not found")
            settings.instance_collection = coll

        return {
            "object_name": obj.name,
            "render_type": settings.render_type,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set particle rendering: {e}")


FIELD_TYPES = {"FORCE", "WIND", "VORTEX", "MAGNET", "HARMONIC", "CHARGE", "LENNARDJ",
               "TURBULENCE", "DRAG"}


def _get_mesh(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{name}' is not a mesh (type: {obj.type})")
    return obj


def handle_add_force_field(params: dict) -> dict:
    """Create an empty carrying a force field."""
    field_type = params.get("type")
    if field_type not in FIELD_TYPES:
        raise ValueError(f"Unknown force field type {field_type!r}")
    # Only the operator allocates field data; an empty from objects.new has none
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.effector_add(type=field_type,
                                location=tuple(params.get("location", (0, 0, 0))),
                                rotation=tuple(params.get("rotation", (0, 0, 0))))
    obj = bpy.context.active_object
    if params.get("name"):
        obj.name = params["name"]
    field = obj.field
    field.type = field_type
    field.strength = params.get("strength", 1.0)
    field.flow = params.get("flow", 0.0)
    field.noise = params.get("noise", 0.0)
    field.seed = params.get("seed", 1)
    field.falloff_type = params.get("falloff_type", "SPHERE")
    field.falloff_power = params.get("falloff_power", 0.0)
    max_distance = params.get("max_distance", 0.0)
    field.use_max_distance = max_distance > 0
    field.distance_max = max_distance
    return {"name": obj.name, "type": field.type, "strength": field.strength}


def handle_add_collision(params: dict) -> dict:
    """Add a Collision modifier and set its surface response."""
    obj = _get_mesh(params.get("object_name"))
    obj.modifiers.new(name="Collision", type="COLLISION")
    coll = obj.collision
    coll.thickness_outer = params.get("thickness", 0.02)
    coll.damping = params.get("damping", 0.1)
    coll.cloth_friction = params.get("friction", 5.0)
    coll.stickiness = params.get("stickiness", 0.0)
    coll.permeability = params.get("permeability", 0.0)
    return {"object_name": obj.name, "thickness": coll.thickness_outer,
            "damping": coll.damping, "friction": coll.cloth_friction}


def handle_add_soft_body(params: dict) -> dict:
    """Add a Soft Body modifier and set its springs and goal."""
    obj = _get_mesh(params.get("object_name"))
    obj.modifiers.new(name="Softbody", type="SOFT_BODY")
    sb = obj.soft_body
    sb.mass = params.get("mass", 1.0)
    sb.use_goal = bool(params.get("goal", True))
    sb.goal_default = params.get("goal_strength", 0.7)
    sb.pull = params.get("pull", 0.5)
    sb.push = params.get("push", 0.5)
    sb.bend = params.get("bend", 0.0)
    sb.damping = params.get("damping", 0.5)
    sb.friction = params.get("friction", 0.5)
    sb.use_self_collision = bool(params.get("self_collision", False))
    return {"object_name": obj.name, "goal": sb.use_goal, "mass": sb.mass}


def register():
    """Register physics handlers with the dispatcher."""
    dispatcher.register_handler("add_rigid_body", handle_add_rigid_body)
    dispatcher.register_handler("add_cloth_sim", handle_add_cloth_sim)
    dispatcher.register_handler("add_fluid_sim", handle_add_fluid_sim)
    dispatcher.register_handler("add_particle_system", handle_add_particle_system)
    dispatcher.register_handler("set_physics_property", handle_set_physics_property)
    dispatcher.register_handler("bake_physics", handle_bake_physics)
    dispatcher.register_handler("delete_particle_system", handle_delete_particle_system)
    dispatcher.register_handler("set_particle_velocity", handle_set_particle_velocity)
    dispatcher.register_handler("set_particle_rendering", handle_set_particle_rendering)
    dispatcher.register_handler("add_force_field", handle_add_force_field)
    dispatcher.register_handler("add_collision", handle_add_collision)
    dispatcher.register_handler("add_soft_body", handle_add_soft_body)
