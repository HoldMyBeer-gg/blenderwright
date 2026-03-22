"""Blender addon handlers for sculpting commands."""

import bpy
from .. import dispatcher


def handle_enter_sculpt_mode(params: dict) -> dict:
    """Enter sculpt mode for a mesh object."""
    object_name = params.get("object_name")

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

        # Enter sculpt mode
        bpy.ops.object.mode_set(mode='SCULPT')

        return {
            "object_name": obj.name,
            "mode": "SCULPT",
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to enter sculpt mode: {e}")


def handle_exit_sculpt_mode(params: dict) -> dict:
    """Exit sculpt mode and return to object mode."""
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
        return {
            "mode": "OBJECT",
            "success": True,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to exit sculpt mode: {e}")


def handle_set_sculpt_brush(params: dict) -> dict:
    """Set the active sculpt brush."""
    brush_type = params.get("brush_type")

    try:
        # Map brush type to Blender's sculpt tool names
        brush_map = {
            "DRAW": "DRAW",
            "CLAY": "CLAY",
            "CLAY_STRIPS": "CLAY_STRIPS",
            "INFLATE": "INFLATE",
            "GRAB": "GRAB",
            "SMOOTH": "SMOOTH",
            "FLATTEN": "FLATTEN",
            "FILL": "FILL",
            "SCRAPE": "SCRAPE",
            "PINCH": "PINCH",
            "CREASE": "CREASE",
            "BLOB": "BLOB",
            "MASK": "MASK",
            "MULTIRES_DISPLACEMENT_SMEAR": "MULTIRES_DISPLACEMENT_SMEAR",
        }

        tool_type = brush_map.get(brush_type)
        if tool_type is None:
            raise ValueError(f"Unknown brush type: {brush_type}")

        # Set the sculpt tool
        bpy.ops.wm.tool_set_by_id(name=f"builtin_brush.{tool_type}")

        return {
            "brush_type": brush_type,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set sculpt brush: {e}")


def handle_set_brush_property(params: dict) -> dict:
    """Set a property on the active sculpt brush."""
    prop = params.get("property")
    value = params.get("value")

    try:
        brush = bpy.context.tool_settings.sculpt.brush
        if brush is None:
            raise ValueError("No active sculpt brush. Enter sculpt mode first.")

        if prop == "size":
            brush.size = int(value)
        elif prop == "strength":
            brush.strength = float(value)
        elif prop == "auto_smooth_factor":
            brush.auto_smooth_factor = float(value)
        elif prop == "use_frontface":
            brush.use_frontface = bool(value)
        else:
            raise ValueError(f"Unknown brush property: {prop}")

        return {
            "property": prop,
            "value": value,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set brush property: {e}")


def handle_remesh(params: dict) -> dict:
    """Remesh an object."""
    object_name = params.get("object_name")
    voxel_size = params.get("voxel_size", 0.1)
    mode = params.get("mode", "VOXEL")

    original_mode = None
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
        original_mode = obj.mode

        # Ensure we are in object mode for remesh
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode='OBJECT')

        if mode == "VOXEL":
            obj.data.remesh_voxel_size = float(voxel_size)
            bpy.ops.object.voxel_remesh()
        else:
            # Use remesh modifier for SHARP, SMOOTH, BLOCKS
            mod = obj.modifiers.new(name="Remesh", type='REMESH')
            mod.mode = mode
            mod.octree_depth = 6
            bpy.ops.object.modifier_apply(modifier=mod.name)

        vertex_count = len(obj.data.vertices)

        return {
            "object_name": obj.name,
            "mode": mode,
            "vertex_count": vertex_count,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to remesh: {e}")
    finally:
        if original_mode and original_mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode=original_mode)
            except Exception:
                pass


def handle_add_multires_modifier(params: dict) -> dict:
    """Add a Multiresolution modifier for sculpting."""
    object_name = params.get("object_name")
    levels = params.get("levels", 2)

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

        # Ensure object mode for modifier operations
        original_mode = obj.mode
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode='OBJECT')

        try:
            mod = obj.modifiers.new(name="Multires", type='MULTIRES')

            # Subdivide the requested number of times
            for _ in range(int(levels)):
                bpy.ops.object.multires_subdivide(modifier=mod.name, mode='CATMULL_CLARK')

            return {
                "object_name": obj.name,
                "modifier_name": mod.name,
                "levels": levels,
                "sculpt_levels": mod.sculpt_levels,
                "success": True,
            }
        finally:
            if original_mode != "OBJECT":
                try:
                    bpy.ops.object.mode_set(mode=original_mode)
                except Exception:
                    pass
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to add multires modifier: {e}")


def register():
    """Register sculpting handlers with the dispatcher."""
    dispatcher.register_handler("enter_sculpt_mode", handle_enter_sculpt_mode)
    dispatcher.register_handler("exit_sculpt_mode", handle_exit_sculpt_mode)
    dispatcher.register_handler("set_sculpt_brush", handle_set_sculpt_brush)
    dispatcher.register_handler("set_brush_property", handle_set_brush_property)
    dispatcher.register_handler("remesh", handle_remesh)
    dispatcher.register_handler("add_multires_modifier", handle_add_multires_modifier)
