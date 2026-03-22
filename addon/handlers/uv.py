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

        bpy.ops.uv.pack_islands(margin=float(margin))

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


def register():
    """Register UV handlers with the dispatcher."""
    dispatcher.register_handler("smart_uv_project", handle_smart_uv_project)
    dispatcher.register_handler("uv_unwrap", handle_uv_unwrap)
    dispatcher.register_handler("set_uv_projection", handle_set_uv_projection)
    dispatcher.register_handler("pack_uv_islands", handle_pack_uv_islands)
