"""Blender addon handlers for object operations."""

import bpy
from .. import dispatcher

# Map of primitive type to bpy.ops function
_PRIMITIVE_OPS = {
    "CUBE": "bpy.ops.mesh.primitive_cube_add",
    "SPHERE": "bpy.ops.mesh.primitive_uv_sphere_add",
    "UV_SPHERE": "bpy.ops.mesh.primitive_uv_sphere_add",
    "ICO_SPHERE": "bpy.ops.mesh.primitive_ico_sphere_add",
    "CYLINDER": "bpy.ops.mesh.primitive_cylinder_add",
    "CONE": "bpy.ops.mesh.primitive_cone_add",
    "TORUS": "bpy.ops.mesh.primitive_torus_add",
    "PLANE": "bpy.ops.mesh.primitive_plane_add",
    "CIRCLE": "bpy.ops.mesh.primitive_circle_add",
    "MONKEY": "bpy.ops.mesh.primitive_monkey_add",
    "EMPTY": None,  # Handled separately
}


def _get_primitive_op(ptype: str):
    """Get the bpy.ops function for a primitive type."""
    ops_map = {
        "CUBE": bpy.ops.mesh.primitive_cube_add,
        "SPHERE": bpy.ops.mesh.primitive_uv_sphere_add,
        "UV_SPHERE": bpy.ops.mesh.primitive_uv_sphere_add,
        "ICO_SPHERE": bpy.ops.mesh.primitive_ico_sphere_add,
        "CYLINDER": bpy.ops.mesh.primitive_cylinder_add,
        "CONE": bpy.ops.mesh.primitive_cone_add,
        "TORUS": bpy.ops.mesh.primitive_torus_add,
        "PLANE": bpy.ops.mesh.primitive_plane_add,
        "CIRCLE": bpy.ops.mesh.primitive_circle_add,
        "MONKEY": bpy.ops.mesh.primitive_monkey_add,
    }
    return ops_map.get(ptype)


def handle_create_object(params: dict) -> dict:
    """Create a primitive object in the scene."""
    obj_type = params.get("type", "CUBE")
    name = params.get("name", "")
    location = tuple(params.get("location", (0, 0, 0)))
    rotation = tuple(params.get("rotation", (0, 0, 0)))
    scale = tuple(params.get("scale", (1, 1, 1)))

    try:
        if obj_type == "EMPTY":
            bpy.ops.object.empty_add(location=location, rotation=rotation)
        else:
            op_func = _get_primitive_op(obj_type)
            if op_func is None:
                raise ValueError(f"Unknown object type: {obj_type}")
            op_func(location=location, rotation=rotation, scale=scale)

        obj = bpy.context.active_object
        if name:
            obj.name = name
            if obj.data:
                obj.data.name = name

        return {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to create object: {e}")


def handle_delete_object(params: dict) -> dict:
    """Delete an object from the scene by name."""
    name = params.get("name")

    try:
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise ValueError(f"Object '{name}' not found")

        bpy.data.objects.remove(obj, do_unlink=True)
        return {"name": name, "deleted": True}
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to delete object '{name}': {e}")


def handle_duplicate_object(params: dict) -> dict:
    """Duplicate an object."""
    name = params.get("name")
    linked = params.get("linked", False)

    try:
        src = bpy.data.objects.get(name)
        if src is None:
            raise ValueError(f"Object '{name}' not found")

        if linked:
            new_obj = src.copy()
        else:
            new_obj = src.copy()
            if src.data:
                new_obj.data = src.data.copy()

        bpy.context.collection.objects.link(new_obj)

        return {
            "name": new_obj.name,
            "source": name,
            "linked": linked,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to duplicate object '{name}': {e}")


def handle_rename_object(params: dict) -> dict:
    """Rename an object."""
    old_name = params.get("old_name")
    new_name = params.get("new_name")

    try:
        obj = bpy.data.objects.get(old_name)
        if obj is None:
            raise ValueError(f"Object '{old_name}' not found")

        obj.name = new_name
        if obj.data:
            obj.data.name = new_name

        return {
            "old_name": old_name,
            "new_name": obj.name,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to rename object '{old_name}': {e}")


def handle_select_objects(params: dict) -> dict:
    """Select objects by name."""
    names = params.get("names", [])
    deselect_others = params.get("deselect_others", True)

    try:
        if deselect_others:
            bpy.ops.object.select_all(action="DESELECT")

        selected = []
        not_found = []
        for name in names:
            obj = bpy.data.objects.get(name)
            if obj is None:
                not_found.append(name)
            else:
                obj.select_set(True)
                selected.append(name)

        # Set the first object as active
        if selected:
            bpy.context.view_layer.objects.active = bpy.data.objects[selected[0]]

        result = {"selected": selected}
        if not_found:
            result["not_found"] = not_found
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to select objects: {e}")


def handle_get_object_info(params: dict) -> dict:
    """Get detailed information about an object."""
    name = params.get("name")

    try:
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise ValueError(f"Object '{name}' not found")

        modifiers = [{"name": m.name, "type": m.type} for m in obj.modifiers]
        materials = [{"name": m.name, "index": i} for i, m in enumerate(obj.data.material_slots) if m.material] if hasattr(obj, "data") and obj.data and hasattr(obj.data, "material_slots") else []  # noqa: F841

        # Get material slot names directly from object
        mat_slots = []
        for i, slot in enumerate(obj.material_slots):
            mat_slots.append({
                "index": i,
                "name": slot.material.name if slot.material else None,
            })

        return {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation_euler": list(obj.rotation_euler),
            "rotation_mode": obj.rotation_mode,
            "scale": list(obj.scale),
            "dimensions": list(obj.dimensions),
            "modifiers": modifiers,
            "materials": mat_slots,
            "parent": obj.parent.name if obj.parent else None,
            "children": [child.name for child in obj.children],
            "visible_viewport": not obj.hide_viewport,
            "visible_render": not obj.hide_render,
            "visible_get": obj.visible_get(),
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to get object info for '{name}': {e}")


def handle_list_objects(params: dict) -> list:
    """List all objects, optionally filtered by type."""
    type_filter = params.get("type_filter", "")

    try:
        objects = []
        for obj in bpy.data.objects:
            if type_filter and obj.type != type_filter:
                continue
            objects.append({
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
            })
        return objects
    except Exception as e:
        raise RuntimeError(f"Failed to list objects: {e}")


def handle_set_object_visibility(params: dict) -> dict:
    """Set object visibility in viewport and/or render."""
    name = params.get("name")
    visible = params.get("visible")
    viewport = params.get("viewport", True)
    render = params.get("render", True)

    try:
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise ValueError(f"Object '{name}' not found")

        if viewport:
            obj.hide_viewport = not visible
        if render:
            obj.hide_render = not visible

        return {
            "name": name,
            "hide_viewport": obj.hide_viewport,
            "hide_render": obj.hide_render,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set visibility for '{name}': {e}")


def handle_parent_objects(params: dict) -> dict:
    """Set parent-child relationship between objects."""
    child_name = params.get("child")
    parent_name = params.get("parent")

    try:
        child = bpy.data.objects.get(child_name)
        if child is None:
            raise ValueError(f"Child object '{child_name}' not found")

        parent = bpy.data.objects.get(parent_name)
        if parent is None:
            raise ValueError(f"Parent object '{parent_name}' not found")

        child.parent = parent
        child.matrix_parent_inverse = parent.matrix_world.inverted()

        return {
            "child": child.name,
            "parent": parent.name,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to parent objects: {e}")


def handle_join_objects(params: dict) -> dict:
    """Join multiple mesh objects into one."""
    names = params.get("names", [])

    try:
        if len(names) < 2:
            raise ValueError("At least 2 objects are required to join")

        # Deselect all first
        bpy.ops.object.select_all(action="DESELECT")

        objects = []
        for name in names:
            obj = bpy.data.objects.get(name)
            if obj is None:
                raise ValueError(f"Object '{name}' not found")
            objects.append(obj)

        # Select all objects and make the first one active
        for obj in objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]

        bpy.ops.object.join()

        result_obj = bpy.context.active_object
        return {
            "name": result_obj.name,
            "joined_count": len(names),
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to join objects: {e}")


def _select_only(obj):
    """Deselect all and select only the given object, making it active."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _get_object(name):
    """Get a Blender object by name, raising if not found."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    return obj


def handle_set_origin(params: dict) -> dict:
    """Set the origin point of an object."""
    object_name = params.get("object_name")
    origin_type = params.get("type", "ORIGIN_GEOMETRY")

    try:
        obj = _get_object(object_name)
        _select_only(obj)
        bpy.ops.object.origin_set(type=origin_type)

        return {
            "name": obj.name,
            "type": origin_type,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set origin for '{object_name}': {e}")


def handle_convert_object(params: dict) -> dict:
    """Convert an object to a different type."""
    object_name = params.get("object_name")
    target = params.get("target", "MESH")

    try:
        obj = _get_object(object_name)
        _select_only(obj)
        bpy.ops.object.convert(target=target)

        result_obj = bpy.context.active_object
        return {
            "name": result_obj.name,
            "type": result_obj.type,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to convert object '{object_name}': {e}")


def handle_shade_auto_smooth(params: dict) -> dict:
    """Apply angle-based auto-smooth shading to an object."""
    object_name = params.get("object_name")
    angle = params.get("angle", 0.523599)

    try:
        obj = _get_object(object_name)
        _select_only(obj)

        if bpy.app.version >= (4, 1, 0):
            bpy.ops.object.shade_smooth_by_angle(angle=angle)
        else:
            bpy.ops.object.shade_smooth()
            obj.data.use_auto_smooth = True
            obj.data.auto_smooth_angle = angle

        return {
            "name": obj.name,
            "angle": angle,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to shade auto smooth '{object_name}': {e}")


def handle_make_single_user(params: dict) -> dict:
    """Make an object's data single-user."""
    object_name = params.get("object_name")
    obj_flag = params.get("object", True)
    data_flag = params.get("data", True)

    try:
        obj = _get_object(object_name)
        _select_only(obj)
        bpy.ops.object.make_single_user(object=obj_flag, obdata=data_flag)

        return {
            "name": obj.name,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to make single user for '{object_name}': {e}")


def register():
    """Register object handlers with the dispatcher."""
    dispatcher.register_handler("create_object", handle_create_object)
    dispatcher.register_handler("delete_object", handle_delete_object)
    dispatcher.register_handler("duplicate_object", handle_duplicate_object)
    dispatcher.register_handler("rename_object", handle_rename_object)
    dispatcher.register_handler("select_objects", handle_select_objects)
    dispatcher.register_handler("get_object_info", handle_get_object_info)
    dispatcher.register_handler("list_objects", handle_list_objects)
    dispatcher.register_handler("set_object_visibility", handle_set_object_visibility)
    dispatcher.register_handler("parent_objects", handle_parent_objects)
    dispatcher.register_handler("join_objects", handle_join_objects)
    dispatcher.register_handler("set_origin", handle_set_origin)
    dispatcher.register_handler("convert_object", handle_convert_object)
    dispatcher.register_handler("shade_auto_smooth", handle_shade_auto_smooth)
    dispatcher.register_handler("make_single_user", handle_make_single_user)
