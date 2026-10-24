"""Blender addon handlers for UV mapping commands."""

import math
import bpy
from .. import dispatcher


def _ensure_edit_mode_all_selected(obj):
    """Enter edit mode and select all faces. Returns the original mode."""
    original_mode = obj.mode

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    if obj.mode != "EDIT":
        bpy.ops.object.mode_set(mode='EDIT')

    bpy.ops.mesh.select_all(action='SELECT')
    return original_mode


def handle_smart_uv_project(params: dict) -> dict:
    """Apply Smart UV Project to a mesh object."""
    object_name = params.get("object_name")
    angle_limit = params.get("angle_limit", 66.0)
    island_margin = params.get("island_margin", 0.0)
    area_weight = params.get("area_weight", 0.0)

    original_mode = None
    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")
        if obj.type != "MESH":
            raise ValueError(f"Object '{object_name}' is not a mesh (type: {obj.type})")

        original_mode = _ensure_edit_mode_all_selected(obj)

        # Smart UV Project expects angle in radians
        angle_rad = math.radians(float(angle_limit))
        bpy.ops.uv.smart_project(
            angle_limit=angle_rad,
            island_margin=float(island_margin),
            area_weight=float(area_weight),
        )

        uv_layers = [layer.name for layer in obj.data.uv_layers]

        return {
            "object_name": obj.name,
            "uv_layers": uv_layers,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to smart UV project: {e}")
    finally:
        if original_mode is not None and original_mode != "EDIT":
            try:
                bpy.ops.object.mode_set(mode=original_mode)
            except Exception:
                pass


def handle_uv_unwrap(params: dict) -> dict:
    """Unwrap a mesh object's UVs."""
    object_name = params.get("object_name")
    method = params.get("method", "ANGLE_BASED")

    original_mode = None
    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")
        if obj.type != "MESH":
            raise ValueError(f"Object '{object_name}' is not a mesh (type: {obj.type})")

        original_mode = _ensure_edit_mode_all_selected(obj)

        bpy.ops.uv.unwrap(method=method, margin=0.001)

        return {
            "object_name": obj.name,
            "method": method,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to UV unwrap: {e}")
    finally:
        if original_mode is not None and original_mode != "EDIT":
            try:
                bpy.ops.object.mode_set(mode=original_mode)
            except Exception:
                pass


def handle_set_uv_projection(params: dict) -> dict:
    """Apply projection-based UV mapping."""
    object_name = params.get("object_name")
    projection = params.get("projection")

    original_mode = None
    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")
        if obj.type != "MESH":
            raise ValueError(f"Object '{object_name}' is not a mesh (type: {obj.type})")

        original_mode = _ensure_edit_mode_all_selected(obj)

        if projection == "CUBE":
            bpy.ops.uv.cube_project()
        elif projection == "CYLINDER":
            bpy.ops.uv.cylinder_project()
        elif projection == "SPHERE":
            bpy.ops.uv.sphere_project()
        else:
            raise ValueError(f"Unknown projection type: {projection}")

        return {
            "object_name": obj.name,
            "projection": projection,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set UV projection: {e}")
    finally:
        if original_mode is not None and original_mode != "EDIT":
            try:
                bpy.ops.object.mode_set(mode=original_mode)
            except Exception:
                pass


def handle_pack_uv_islands(params: dict) -> dict:
    """Pack UV islands."""
    object_name = params.get("object_name")
    margin = params.get("margin", 0.001)

    original_mode = None
    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")
        if obj.type != "MESH":
            raise ValueError(f"Object '{object_name}' is not a mesh (type: {obj.type})")

        original_mode = _ensure_edit_mode_all_selected(obj)

        bpy.ops.uv.pack_islands(
            margin=float(margin),
            rotate=bool(params.get("rotate", True)),
            rotate_method=params.get("rotate_method", "ANY"),
            scale=bool(params.get("scale", True)),
        )

        return {
            "object_name": obj.name,
            "margin": margin,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to pack UV islands: {e}")
    finally:
        if original_mode is not None and original_mode != "EDIT":
            try:
                bpy.ops.object.mode_set(mode=original_mode)
            except Exception:
                pass


UV_ISLAND_OPERATIONS = {
    "AVERAGE_SCALE", "MINIMIZE_STRETCH", "ALIGN_ROTATION", "RANDOMIZE",
    "SEAMS_FROM_ISLANDS", "ARRANGE", "WELD",
}


def _get_uv_mesh(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{name}' is not a mesh (type: {obj.type})")
    return obj


def _enter_uv_edit(obj, selection):
    """Edit mode on obj with everything selected, or the current selection kept."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if obj.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")
    if selection != "CURRENT":
        bpy.ops.mesh.select_all(action="SELECT")


def _island_operator(operation, params):
    """The UV operator and keywords for an island operation."""
    if operation == "AVERAGE_SCALE":
        return bpy.ops.uv.average_islands_scale, {}
    if operation == "MINIMIZE_STRETCH":
        return bpy.ops.uv.minimize_stretch, {"iterations": int(params.get("iterations", 20))}
    if operation == "ALIGN_ROTATION":
        return bpy.ops.uv.align_rotation, {"method": "AUTO"}
    if operation == "RANDOMIZE":
        scale = float(params.get("scale_variation", 0.0))
        offset = float(params.get("offset", 0.0))
        return bpy.ops.uv.randomize_uv_transform, {
            "rot": float(params.get("rotation", 0.0)), "scale": (scale, scale),
            "scale_even": True, "loc": (offset, offset),
            "random_seed": int(params.get("seed", 0))}
    if operation == "SEAMS_FROM_ISLANDS":
        return bpy.ops.uv.seams_from_islands, {}
    if operation == "ARRANGE":
        return bpy.ops.uv.arrange_islands, {"margin": float(params.get("margin", 0.05))}
    return bpy.ops.uv.remove_doubles, {"threshold": float(params.get("threshold", 0.0001))}


def handle_uv_island_operation(params):
    operation = params.get("operation")
    if operation not in UV_ISLAND_OPERATIONS:
        raise ValueError(f"Unknown UV island operation {operation!r}")
    obj = _get_uv_mesh(params.get("object_name"))
    operator, kwargs = _island_operator(operation, params)

    # With UV sync on, UV operators follow the mesh selection, as every other tool does
    settings = bpy.context.scene.tool_settings
    saved_sync = settings.use_uv_select_sync
    original_mode = obj.mode
    try:
        _enter_uv_edit(obj, params.get("selection", "ALL"))
        settings.use_uv_select_sync = True
        result = operator(**kwargs)
    finally:
        settings.use_uv_select_sync = saved_sync
        if original_mode != "EDIT":
            bpy.ops.object.mode_set(mode=original_mode)
    if result != {"FINISHED"}:
        raise RuntimeError(f"UV operation {operation} did not finish: {result}")
    return {"object": obj.name, "operation": operation}


def _world_coords(obj):
    # matrix_world is stale until the scene updates, e.g. right after set_scale
    bpy.context.view_layer.update()
    matrix = obj.matrix_world
    return [matrix @ v.co for v in obj.data.vertices]


def _areas(obj):
    """World surface area and UV area of a mesh, from its active UV map."""
    uv_layer = obj.data.uv_layers.active
    if uv_layer is None:
        raise ValueError(f"'{obj.name}' has no UV map; unwrap it first with smart_uv_project")
    coords = _world_coords(obj)
    uvs = uv_layer.data
    surface = uv_area = 0.0
    for poly in obj.data.polygons:
        pts = [coords[i] for i in poly.vertices]
        ox, oy, oz = pts[0][0], pts[0][1], pts[0][2]
        nx = ny = nz = 0.0
        for a, b in zip(pts[1:-1], pts[2:]):
            ax, ay, az = a[0] - ox, a[1] - oy, a[2] - oz
            bx, by, bz = b[0] - ox, b[1] - oy, b[2] - oz
            nx += ay * bz - az * by
            ny += az * bx - ax * bz
            nz += ax * by - ay * bx
        surface += math.sqrt(nx * nx + ny * ny + nz * nz) / 2
        loop = [uvs[i].uv for i in poly.loop_indices]
        uv_area += abs(sum(p[0] * q[1] - q[0] * p[1]
                           for p, q in zip(loop, loop[1:] + loop[:1]))) / 2
    return surface, uv_area


def _density(surface, uv_area, size):
    return size * math.sqrt(uv_area / surface) if surface > 0 and uv_area > 0 else 0.0


def _object_mode(obj):
    """UV data is only current in object mode; returns the mode to restore."""
    mode = obj.mode
    if mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    return mode


def handle_get_texel_density(params):
    obj = _get_uv_mesh(params.get("object_name"))
    size = int(params.get("texture_size", 1024))
    mode = _object_mode(obj)
    try:
        surface, uv_area = _areas(obj)
    finally:
        if mode != "OBJECT":
            bpy.ops.object.mode_set(mode=mode)
    return {"object": obj.name, "texture_size": size,
            "density": round(_density(surface, uv_area, size), 3),
            "surface_area": round(surface, 6), "uv_coverage": round(uv_area, 6)}


def handle_set_texel_density(params):
    obj = _get_uv_mesh(params.get("object_name"))
    size = int(params.get("texture_size", 1024))
    target = float(params["density"])
    mode = _object_mode(obj)
    try:
        surface, uv_area = _areas(obj)
        before = _density(surface, uv_area, size)
        if before == 0.0:
            raise ValueError(f"'{obj.name}' has no UV area to scale")
        factor = target / before
        data = obj.data.uv_layers.active.data
        us = [d.uv[0] for d in data]
        vs = [d.uv[1] for d in data]
        cu, cv = (min(us) + max(us)) / 2, (min(vs) + max(vs)) / 2
        for d in data:
            d.uv = [cu + (d.uv[0] - cu) * factor, cv + (d.uv[1] - cv) * factor]
        obj.data.update()
        after = _density(*_areas(obj), size)
    finally:
        if mode != "OBJECT":
            bpy.ops.object.mode_set(mode=mode)
    return {"object": obj.name, "texture_size": size, "before": round(before, 3),
            "after": round(after, 3), "scale_factor": round(factor, 6)}


def register():
    """Register UV handlers with the dispatcher."""
    dispatcher.register_handler("smart_uv_project", handle_smart_uv_project)
    dispatcher.register_handler("uv_unwrap", handle_uv_unwrap)
    dispatcher.register_handler("set_uv_projection", handle_set_uv_projection)
    dispatcher.register_handler("pack_uv_islands", handle_pack_uv_islands)
    dispatcher.register_handler("uv_island_operation", handle_uv_island_operation)
    dispatcher.register_handler("get_texel_density", handle_get_texel_density)
    dispatcher.register_handler("set_texel_density", handle_set_texel_density)
