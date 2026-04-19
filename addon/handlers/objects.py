"""Blender addon handlers for object operations."""

import math

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


def handle_create_polygon_prism(params: dict) -> dict:
    """Create an N-sided regular prism via primitive_cylinder_add(vertices=N)."""
    sides = int(params.get("sides", 6))
    radius = float(params.get("radius", 1.0))
    depth = float(params.get("depth", 2.0))
    name = params.get("name", "")
    location = tuple(params.get("location", (0, 0, 0)))
    rotation = tuple(params.get("rotation", (0, 0, 0)))
    scale = tuple(params.get("scale", (1, 1, 1)))

    try:
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=sides,
            radius=radius,
            depth=depth,
            location=location,
            rotation=rotation,
            scale=scale,
        )
        obj = bpy.context.active_object
        if name:
            obj.name = name
            if obj.data:
                obj.data.name = name

        return {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "sides": sides,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to create polygon prism: {e}")


def handle_create_threaded_shaft(params: dict) -> dict:
    """Create a threaded cylindrical shaft: solid core + helical V-ridge union.

    The Screw modifier revolves a 2D profile along a helix. Feeding it a filled
    profile does NOT create a solid revolved body — it creates a thick-walled
    helical tube, because adjacent rotation steps are connected only by side
    walls. That leaves the interior hollow.

    Correct construction:
    1. Create a solid cylinder at minor_r spanning the full length (the shaft core).
    2. Sweep a small 3-vertex triangular profile (the thread V cross-section)
       via Screw modifier, producing a helical triangular prism.
    3. Fill the two open triangular faces at helix start and end with fill_holes
       so the ridge is a closed manifold solid.
    4. Boolean-UNION the ridge into the core (exact solver).
    5. Clean up duplicate verts and recompute normals.

    Result is a truly solid, watertight threaded cylinder ready for further
    boolean ops (e.g., a button-head union) and 3D printing.
    """
    diameter = float(params.get("diameter"))
    length = float(params.get("length"))
    pitch = float(params.get("pitch"))
    thread_depth = float(params.get("thread_depth", 0.0))
    segments = int(params.get("segments", 32))
    thread_runout = float(params.get("thread_runout", -1.0))
    name = params.get("name") or "ThreadedShaft"
    location = tuple(params.get("location", (0, 0, 0)))

    if thread_depth <= 0:
        thread_depth = pitch * 0.54
    # thread_runout < 0 is "auto" — threads go as high as they fit. For a
    # printed fastener this is what you want structurally: threads continue
    # up to ~z=length, where a boolean-unioned head overlaps them, giving
    # one continuous stress path. A smooth-cylinder runout leaves a
    # thin-walled neck at minor_r which snaps under torque in FDM prints.
    # If the head has a deep hex socket whose bottom reaches below z=length,
    # pass an explicit thread_runout to clear it.
    if thread_runout < 0:
        thread_runout = 0.0

    major_r = diameter / 2.0
    minor_r = major_r - thread_depth
    half_base = thread_depth * math.tan(math.radians(30.0))

    try:
        # --- 1) Solid core cylinder at exactly [0, length] ---
        # Thread ridges will overhang by half_base (~0.156 of pitch) on each
        # end — cosmetic, real screws have ragged thread ends anyway. Keeping
        # the core at exact length means no trim-boolean is needed, which
        # avoided a class of Blender boolean-solver failures that collapsed
        # the mesh or erased thread peaks.
        core_depth = length
        core_center = (
            location[0],
            location[1],
            location[2] + length / 2.0,
        )
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=segments,
            radius=minor_r,
            depth=core_depth,
            location=core_center,
        )
        core = bpy.context.active_object
        core.name = name
        if core.data:
            core.data.name = name + "_mesh"

        # --- 2) Helical ridge from a triangular profile ---
        # Edges-only closed triangle in the XZ plane, centered around pitch/2.
        # A filled face would make the Screw modifier stamp the face at every
        # rotation step, creating internal divider faces that break manifoldness.
        # With edges only, the sweep produces just the 3 outer walls of a
        # triangular tube — which fill_holes then caps to close the volume.
        ridge_verts = [
            (minor_r, 0.0, pitch / 2.0 - half_base),  # lower minor corner
            (major_r, 0.0, pitch / 2.0),              # V peak
            (minor_r, 0.0, pitch / 2.0 + half_base),  # upper minor corner
        ]
        ridge_edges = [(0, 1), (1, 2), (2, 0)]
        ridge_mesh = bpy.data.meshes.new(name + "_ridge_mesh")
        ridge_mesh.from_pydata(ridge_verts, ridge_edges, [])
        ridge_mesh.update()
        ridge = bpy.data.objects.new(name + "_ridge", ridge_mesh)
        bpy.context.collection.objects.link(ridge)
        ridge.location = location

        # Thread iterations: cap N so the sweep's topmost geometry ends below
        # (length - thread_runout). The Screw modifier places the profile's
        # upper tip at z = N*pitch + pitch/2 + half_base after N iterations.
        # Solve N*pitch + pitch/2 + half_base ≤ length - thread_runout.
        max_top = length - thread_runout
        allowed = (max_top - pitch / 2.0 - half_base) / pitch
        iterations = max(1, int(math.floor(allowed))) if allowed >= 1 else 1
        screw = ridge.modifiers.new(name="Screw", type="SCREW")
        screw.axis = "Z"
        screw.angle = 2.0 * math.pi
        screw.screw_offset = pitch
        screw.iterations = iterations
        screw.steps = segments
        screw.render_steps = segments
        screw.use_merge_vertices = True
        screw.merge_threshold = 1e-5
        screw.use_normal_calculate = True

        bpy.context.view_layer.objects.active = ridge
        bpy.ops.object.select_all(action="DESELECT")
        ridge.select_set(True)
        bpy.ops.object.modifier_apply(modifier=screw.name)

        # --- 3) Close the two open triangle ends so the ridge is manifold. ---
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.mesh.select_non_manifold()
        bpy.ops.mesh.fill_holes(sides=3)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")

        # --- 4) Boolean UNION ridge into core ---
        bpy.ops.object.select_all(action="DESELECT")
        core.select_set(True)
        bpy.context.view_layer.objects.active = core
        bool_mod = core.modifiers.new(name="Threads", type="BOOLEAN")
        bool_mod.operation = "UNION"
        bool_mod.object = ridge
        bool_mod.solver = "EXACT"
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)

        # Ridge is consumed — remove the now-unused helper object.
        bpy.data.objects.remove(ridge, do_unlink=True)

        # --- 5) Final cleanup: merge tight duplicates, recalc normals. ---
        # Trim-booleans were removed: they were numerically unstable and
        # either collapsed the mesh or erased thread peaks. Thread overhang
        # past z=0 and z=length (~half_base per end) is cosmetic and matches
        # how real fastener threads terminate.
        bpy.ops.object.select_all(action="DESELECT")
        core.select_set(True)
        bpy.context.view_layer.objects.active = core
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=1e-5)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")

        obj = core

        return {
            "name": obj.name,
            "diameter": diameter,
            "length": iterations * pitch,
            "pitch": pitch,
            "thread_depth": thread_depth,
            "iterations": iterations,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to create threaded shaft: {e}")


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
    dispatcher.register_handler("create_polygon_prism", handle_create_polygon_prism)
    dispatcher.register_handler("create_threaded_shaft", handle_create_threaded_shaft)
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
