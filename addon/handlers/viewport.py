"""Blender addon handlers for viewport commands."""

import bpy
from .. import dispatcher

# Allowed shading modes
ALLOWED_SHADING_MODES = {"WIREFRAME", "SOLID", "MATERIAL", "RENDERED"}

# Allowed overlay properties
ALLOWED_OVERLAYS = {
    "show_wireframes",
    "show_face_orientation",
    "show_floor",
    "show_axis_x",
    "show_axis_y",
    "show_axis_z",
    "show_cursor",
    "show_object_origins",
    "show_relationship_lines",
    "show_stats",
}


def _get_3d_viewport_area():
    """Find the first 3D Viewport area and its space."""
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    return area, space
    return None, None


def handle_set_viewport_shading(params: dict) -> dict:
    """Set the viewport shading mode."""
    mode = params.get("mode")

    if mode not in ALLOWED_SHADING_MODES:
        raise ValueError(
            f"Shading mode '{mode}' not allowed. Allowed: {sorted(ALLOWED_SHADING_MODES)}"
        )

    try:
        area, space = _get_3d_viewport_area()
        if space is None:
            raise RuntimeError("No 3D Viewport found")

        space.shading.type = mode

        return {
            "mode": mode,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set viewport shading: {e}")


def handle_set_viewport_overlay(params: dict) -> dict:
    """Toggle a viewport overlay setting."""
    overlay = params.get("overlay")
    enabled = params.get("enabled")

    if overlay not in ALLOWED_OVERLAYS:
        raise ValueError(
            f"Overlay '{overlay}' not allowed. Allowed: {sorted(ALLOWED_OVERLAYS)}"
        )

    try:
        area, space = _get_3d_viewport_area()
        if space is None:
            raise RuntimeError("No 3D Viewport found")

        setattr(space.overlay, overlay, bool(enabled))

        return {
            "overlay": overlay,
            "enabled": bool(enabled),
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set viewport overlay: {e}")


def handle_focus_on_object(params: dict) -> dict:
    """Focus the viewport on a specific object."""
    object_name = params.get("object_name")

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        # Deselect all, select target, make active
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Frame selected in all 3D viewports
        area, space = _get_3d_viewport_area()
        if area is not None:
            # Override context to target the 3D viewport
            with bpy.context.temp_override(area=area, region=area.regions[-1]):
                bpy.ops.view3d.view_selected()

        return {
            "object_name": object_name,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to focus on object '{object_name}': {e}")


def register():
    """Register viewport handlers with the dispatcher."""
    dispatcher.register_handler("set_viewport_shading", handle_set_viewport_shading)
    dispatcher.register_handler("set_viewport_overlay", handle_set_viewport_overlay)
    dispatcher.register_handler("focus_on_object", handle_focus_on_object)
