"""Blender handlers for lighting operations."""

import os

import bpy
from .. import dispatcher


def _get_light_object(name: str):
    """Get a light object by name or raise."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.type != 'LIGHT':
        raise ValueError(f"Object '{name}' is not a light (type: {obj.type})")
    return obj


def handle_create_light(params: dict) -> dict:
    """Create a new light."""
    try:
        light_type = params["type"]
        name = params.get("name", "") or f"{light_type.capitalize()} Light"
        location = tuple(params.get("location", (0, 0, 0)))
        energy = params.get("energy", 1000.0)
        color = tuple(params.get("color", (1.0, 1.0, 1.0)))

        # Create light data
        light_data = bpy.data.lights.new(name=name, type=light_type)
        light_data.energy = energy
        light_data.color = color[:3]

        # Create light object
        light_obj = bpy.data.objects.new(name=name, object_data=light_data)
        light_obj.location = location

        # Link to active collection
        bpy.context.collection.objects.link(light_obj)

        return {
            "name": light_obj.name,
            "type": light_type,
            "energy": energy,
            "color": list(color[:3]),
            "location": list(location),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to create light: {e}")


def handle_set_light_property(params: dict) -> dict:
    """Set a property on a light."""
    try:
        name = params["name"]
        prop = params["property"]
        value = params["value"]

        obj = _get_light_object(name)
        light = obj.data

        if prop == "energy":
            light.energy = value
        elif prop == "color":
            light.color = tuple(value)[:3]
        elif prop == "shadow_soft_size":
            light.shadow_soft_size = value
        elif prop == "spot_size":
            if light.type != 'SPOT':
                raise ValueError("spot_size only applies to SPOT lights")
            light.spot_size = value
        elif prop == "spot_blend":
            if light.type != 'SPOT':
                raise ValueError("spot_blend only applies to SPOT lights")
            light.spot_blend = value
        elif prop == "area_size":
            if light.type != 'AREA':
                raise ValueError("area_size only applies to AREA lights")
            light.size = value
        elif prop == "area_size_y":
            if light.type != 'AREA':
                raise ValueError("area_size_y only applies to AREA lights")
            light.size_y = value
        elif prop == "use_shadow":
            light.use_shadow = value
        elif prop == "angle":
            if light.type != 'SUN':
                raise ValueError("angle only applies to SUN lights")
            light.angle = value
        elif prop == "specular_factor":
            light.specular_factor = value
        elif prop == "diffuse_factor":
            light.diffuse_factor = value
        elif prop == "volume_factor":
            light.volume_factor = value
        else:
            raise ValueError(f"Unknown light property: '{prop}'")

        return {"light": obj.name, "property": prop, "value": value}
    except Exception as e:
        raise RuntimeError(f"Failed to set light property: {e}")


BUILTIN_HDRIS = {"city", "courtyard", "forest", "interior", "night", "studio", "sunrise", "sunset"}
SKY_TYPES = {"MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "PREETHAM", "HOSEK_WILKIE"}
SKY_PROPERTIES = ("sun_elevation", "sun_rotation", "sun_intensity", "sun_disc", "altitude",
                  "air_density", "aerosol_density", "ozone_density")


def _fresh_world_tree():
    """The scene's world node tree, emptied. Worlds always use nodes in 5.x."""
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    tree = world.node_tree
    tree.nodes.clear()
    return tree


def _background_to_output(tree, color_socket, strength):
    bg_node = tree.nodes.new(type='ShaderNodeBackground')
    bg_node.location = (0, 300)
    bg_node.inputs["Strength"].default_value = strength
    output_node = tree.nodes.new(type='ShaderNodeOutputWorld')
    output_node.location = (200, 300)
    if color_socket is not None:
        tree.links.new(color_socket, bg_node.inputs["Color"])
    tree.links.new(bg_node.outputs["Background"], output_node.inputs["Surface"])
    return bg_node


def handle_set_world_background(params: dict) -> dict:
    """Set world background color or HDRI."""
    try:
        strength = params.get("strength", 1.0)
        builtin = params.get("builtin_hdri")
        if builtin is not None:
            if builtin not in BUILTIN_HDRIS:
                raise ValueError(f"Unknown built-in HDRI {builtin!r}")
            hdri_path = os.path.join(
                bpy.utils.system_resource("DATAFILES", path="studiolights/world"),
                f"{builtin}.exr")
        else:
            hdri_path = params.get("hdri_path")

        tree = _fresh_world_tree()
        if hdri_path:
            # Environment Texture -> Background -> World Output
            env_tex = tree.nodes.new(type='ShaderNodeTexEnvironment')
            env_tex.location = (-300, 300)
            env_tex.image = bpy.data.images.load(hdri_path, check_existing=True)
            rotation = params.get("rotation", 0.0)
            if rotation:
                coords = tree.nodes.new(type='ShaderNodeTexCoord')
                coords.location = (-700, 300)
                mapping = tree.nodes.new(type='ShaderNodeMapping')
                mapping.location = (-500, 300)
                mapping.inputs["Rotation"].default_value = (0.0, 0.0, rotation)
                tree.links.new(coords.outputs["Generated"], mapping.inputs["Vector"])
                tree.links.new(mapping.outputs["Vector"], env_tex.inputs["Vector"])
            _background_to_output(tree, env_tex.outputs["Color"], strength)
            result = {"type": "hdri", "hdri_path": hdri_path, "strength": strength,
                      "rotation": rotation}
            if builtin is not None:
                result["builtin_hdri"] = builtin
            return result

        color = tuple(params.get("color", (0.05, 0.05, 0.05)))
        bg_node = _background_to_output(tree, None, strength)
        bg_node.inputs["Color"].default_value = (*color[:3], 1.0)
        return {"type": "color", "color": list(color[:3]), "strength": strength}
    except Exception as e:
        raise RuntimeError(f"Failed to set world background: {e}")


def handle_set_world_sky(params: dict) -> dict:
    """Build a procedural sky: Sky Texture -> Background -> World Output."""
    sky_type = params.get("sky_type", "MULTIPLE_SCATTERING")
    if sky_type not in SKY_TYPES:
        raise ValueError(f"Unknown sky type {sky_type!r}")
    tree = _fresh_world_tree()
    sky = tree.nodes.new(type='ShaderNodeTexSky')
    sky.location = (-300, 300)
    sky.sky_type = sky_type
    for prop in SKY_PROPERTIES:
        if prop in params:
            setattr(sky, prop, params[prop])
    _background_to_output(tree, sky.outputs["Color"], params.get("strength", 1.0))
    return {"sky_type": sky.sky_type, "strength": params.get("strength", 1.0),
            **{prop: getattr(sky, prop) for prop in SKY_PROPERTIES}}


def handle_create_light_rig(params: dict) -> dict:
    """Create a pre-built lighting rig."""
    try:
        rig_type = params["type"]
        target_name = params.get("target", "")
        intensity = params.get("intensity", 1000.0)

        created_lights = []

        # Get target location for aiming
        target_loc = (0, 0, 0)
        if target_name:
            target_obj = bpy.data.objects.get(target_name)
            if target_obj:
                target_loc = tuple(target_obj.location)

        def _create_light_in_rig(name, light_type, location, energy, color=(1, 1, 1)):
            light_data = bpy.data.lights.new(name=name, type=light_type)
            light_data.energy = energy
            light_data.color = color
            obj = bpy.data.objects.new(name=name, object_data=light_data)
            obj.location = location
            bpy.context.collection.objects.link(obj)

            # Point at target using Track To constraint
            if target_name:
                target_obj = bpy.data.objects.get(target_name)
                if target_obj:
                    constraint = obj.constraints.new(type='TRACK_TO')
                    constraint.target = target_obj
                    constraint.track_axis = 'TRACK_NEGATIVE_Z'
                    constraint.up_axis = 'UP_Y'

            created_lights.append(obj.name)
            return obj

        if rig_type == "THREE_POINT":
            _create_light_in_rig("Key Light", "AREA",
                                 (target_loc[0] + 4, target_loc[1] - 3, target_loc[2] + 5),
                                 intensity, (1.0, 0.95, 0.9))
            _create_light_in_rig("Fill Light", "AREA",
                                 (target_loc[0] - 3, target_loc[1] - 2, target_loc[2] + 3),
                                 intensity * 0.4, (0.9, 0.95, 1.0))
            _create_light_in_rig("Rim Light", "POINT",
                                 (target_loc[0] - 1, target_loc[1] + 4, target_loc[2] + 4),
                                 intensity * 0.6, (1.0, 1.0, 1.0))

        elif rig_type == "STUDIO":
            _create_light_in_rig("Studio Key", "AREA",
                                 (target_loc[0] + 3, target_loc[1] - 4, target_loc[2] + 5),
                                 intensity, (1.0, 0.98, 0.95))
            _create_light_in_rig("Studio Fill", "AREA",
                                 (target_loc[0] - 3, target_loc[1] - 3, target_loc[2] + 3),
                                 intensity * 0.3, (0.95, 0.98, 1.0))
            _create_light_in_rig("Studio Hair", "SPOT",
                                 (target_loc[0], target_loc[1] + 3, target_loc[2] + 6),
                                 intensity * 0.5, (1.0, 1.0, 1.0))
            _create_light_in_rig("Studio Background", "AREA",
                                 (target_loc[0], target_loc[1] + 5, target_loc[2] + 2),
                                 intensity * 0.2, (0.9, 0.9, 1.0))

        elif rig_type == "RIM":
            _create_light_in_rig("Rim Left", "AREA",
                                 (target_loc[0] - 4, target_loc[1] + 2, target_loc[2] + 3),
                                 intensity * 0.8, (1.0, 1.0, 1.0))
            _create_light_in_rig("Rim Right", "AREA",
                                 (target_loc[0] + 4, target_loc[1] + 2, target_loc[2] + 3),
                                 intensity * 0.8, (1.0, 1.0, 1.0))

        elif rig_type == "OUTDOOR":
            sun = _create_light_in_rig("Sun Light", "SUN",  # noqa: F841
                                       (target_loc[0] + 5, target_loc[1] - 5, target_loc[2] + 10),
                                       intensity * 0.005, (1.0, 0.95, 0.85))
            _create_light_in_rig("Sky Fill", "AREA",
                                 (target_loc[0], target_loc[1], target_loc[2] + 8),
                                 intensity * 0.1, (0.6, 0.75, 1.0))
        else:
            raise ValueError(f"Unknown rig type: '{rig_type}'")

        return {"rig_type": rig_type, "lights": created_lights, "target": target_name}
    except Exception as e:
        raise RuntimeError(f"Failed to create light rig: {e}")


def handle_list_lights(params: dict) -> list:
    """List all light objects."""
    try:
        result = []
        for obj in bpy.data.objects:
            if obj.type == 'LIGHT':
                light = obj.data
                info = {
                    "name": obj.name,
                    "type": light.type,
                    "energy": light.energy,
                    "color": list(light.color),
                    "location": list(obj.location),
                    "use_shadow": light.use_shadow,
                }
                if light.type == 'SPOT':
                    info["spot_size"] = light.spot_size
                    info["spot_blend"] = light.spot_blend
                elif light.type == 'AREA':
                    info["area_size"] = light.size
                result.append(info)
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to list lights: {e}")


def handle_delete_light(params: dict) -> dict:
    """Delete a light object."""
    try:
        name = params["name"]
        obj = _get_light_object(name)

        # Remove associated light data
        light_data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if light_data and light_data.users == 0:
            bpy.data.lights.remove(light_data)

        return {"deleted": name}
    except Exception as e:
        raise RuntimeError(f"Failed to delete light: {e}")


def handle_set_shadow_settings(params: dict) -> dict:
    """Set shadow settings for a light."""
    try:
        name = params["name"]
        obj = _get_light_object(name)
        light = obj.data

        use_shadow = params.get("use_shadow", True)
        shadow_soft_size = params.get("shadow_soft_size", 0.25)

        light.use_shadow = use_shadow
        light.shadow_soft_size = shadow_soft_size

        return {
            "light": obj.name,
            "use_shadow": use_shadow,
            "shadow_soft_size": shadow_soft_size,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to set shadow settings: {e}")


LINK_ROLES = {"RECEIVERS": ("receiver_collection", "Light Linking for"),
              "BLOCKERS": ("blocker_collection", "Shadow Linking for")}


def handle_set_light_linking(params: dict) -> dict:
    """Replace a light's receiver or blocker list."""
    light_name = params.get("light_name")
    light = bpy.data.objects.get(light_name)
    if light is None:
        raise ValueError(f"Light '{light_name}' not found")
    role = params.get("role", "RECEIVERS")
    if role not in LINK_ROLES:
        raise ValueError(f"Unknown role {role!r}")
    mode = params.get("mode", "INCLUDE")
    if mode not in ("INCLUDE", "EXCLUDE"):
        raise ValueError(f"Unknown mode {mode!r}")
    targets = []
    for name in params.get("objects", []):
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise ValueError(f"Object '{name}' not found")
        targets.append(obj)

    attr, prefix = LINK_ROLES[role]
    if not targets:
        setattr(light.light_linking, attr, None)
        return {"light": light.name, "role": role, "collection": None, "objects": []}

    collection = getattr(light.light_linking, attr)
    if collection is None:
        collection = bpy.data.collections.new(f"{prefix} {light.name}")
        setattr(light.light_linking, attr, collection)
    for obj in list(collection.objects):
        collection.objects.unlink(obj)
    for obj in targets:
        collection.objects.link(obj)
    # collection_objects line up with objects; each carries the link state
    for entry in collection.collection_objects:
        entry.light_linking.link_state = mode
    return {"light": light.name, "role": role, "mode": mode, "collection": collection.name,
            "objects": [o.name for o in collection.objects]}


def register():
    """Register all lighting handlers with the dispatcher."""
    dispatcher.register_handler("create_light", handle_create_light)
    dispatcher.register_handler("set_light_property", handle_set_light_property)
    dispatcher.register_handler("set_world_background", handle_set_world_background)
    dispatcher.register_handler("create_light_rig", handle_create_light_rig)
    dispatcher.register_handler("list_lights", handle_list_lights)
    dispatcher.register_handler("delete_light", handle_delete_light)
    dispatcher.register_handler("set_shadow_settings", handle_set_shadow_settings)
    dispatcher.register_handler("set_world_sky", handle_set_world_sky)
    dispatcher.register_handler("set_light_linking", handle_set_light_linking)
