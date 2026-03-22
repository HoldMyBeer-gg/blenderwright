"""Blender addon handlers for curve and text commands."""

import bpy
from .. import dispatcher


def handle_create_curve(params: dict) -> dict:
    """Create a new curve object."""
    curve_type = params.get("type", "BEZIER")
    name = params.get("name", "")
    location = tuple(params.get("location", (0, 0, 0)))

    try:
        if curve_type == "BEZIER":
            bpy.ops.curve.primitive_bezier_curve_add(location=location)
        elif curve_type == "NURBS":
            bpy.ops.curve.primitive_nurbs_curve_add(location=location)
        elif curve_type == "PATH":
            bpy.ops.curve.primitive_nurbs_path_add(location=location)
        else:
            raise ValueError(f"Unsupported curve type: {curve_type}")

        obj = bpy.context.active_object
        if name:
            obj.name = name
            obj.data.name = name

        return {
            "name": obj.name,
            "type": curve_type,
            "location": list(obj.location),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to create curve: {e}")


def handle_add_curve_point(params: dict) -> dict:
    """Add a control point to an existing curve."""
    curve_name = params.get("curve_name")
    location = tuple(params.get("location", (0, 0, 0)))
    handle_type = params.get("handle_type", "AUTO")

    try:
        obj = bpy.data.objects.get(curve_name)
        if obj is None:
            raise ValueError(f"Object '{curve_name}' not found")
        if obj.type != "CURVE":
            raise ValueError(f"Object '{curve_name}' is not a curve (type: {obj.type})")

        curve_data = obj.data
        if len(curve_data.splines) == 0:
            raise ValueError(f"Curve '{curve_name}' has no splines")

        spline = curve_data.splines[0]

        if spline.type == "BEZIER":
            spline.bezier_points.add(1)
            point = spline.bezier_points[-1]
            point.co = location
            point.handle_left_type = handle_type
            point.handle_right_type = handle_type
            point_count = len(spline.bezier_points)
        elif spline.type in ("NURBS", "POLY"):
            spline.points.add(1)
            point = spline.points[-1]
            point.co = (location[0], location[1], location[2], 1.0)
            point_count = len(spline.points)
        else:
            raise ValueError(f"Unsupported spline type: {spline.type}")

        return {
            "curve_name": obj.name,
            "point_count": point_count,
            "location": list(location),
            "handle_type": handle_type,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to add curve point: {e}")


def handle_set_curve_property(params: dict) -> dict:
    """Set a property on a curve object."""
    curve_name = params.get("curve_name")
    prop = params.get("property")
    value = params.get("value")

    try:
        obj = bpy.data.objects.get(curve_name)
        if obj is None:
            raise ValueError(f"Object '{curve_name}' not found")
        if obj.type != "CURVE":
            raise ValueError(f"Object '{curve_name}' is not a curve (type: {obj.type})")

        curve_data = obj.data

        if prop == "resolution_u":
            curve_data.resolution_u = int(value)
        elif prop == "fill_mode":
            curve_data.fill_mode = value
        elif prop == "bevel_depth":
            curve_data.bevel_depth = float(value)
        elif prop == "bevel_resolution":
            curve_data.bevel_resolution = int(value)
        elif prop == "extrude":
            curve_data.extrude = float(value)
        elif prop == "twist_mode":
            curve_data.twist_mode = value
        elif prop == "use_fill_caps":
            curve_data.use_fill_caps = bool(value)
        else:
            raise ValueError(f"Unknown curve property: {prop}")

        return {
            "curve_name": obj.name,
            "property": prop,
            "value": value,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set curve property: {e}")


def handle_convert_curve_to_mesh(params: dict) -> dict:
    """Convert a curve object to a mesh."""
    curve_name = params.get("curve_name")

    try:
        obj = bpy.data.objects.get(curve_name)
        if obj is None:
            raise ValueError(f"Object '{curve_name}' not found")
        if obj.type != "CURVE":
            raise ValueError(f"Object '{curve_name}' is not a curve (type: {obj.type})")

        # Select and make active
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        bpy.ops.object.convert(target='MESH')

        converted = bpy.context.active_object
        return {
            "name": converted.name,
            "type": converted.type,
            "vertex_count": len(converted.data.vertices),
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to convert curve to mesh: {e}")


def handle_create_text(params: dict) -> dict:
    """Create a 3D text object."""
    text = params.get("text", "Text")
    name = params.get("name", "")
    location = tuple(params.get("location", (0, 0, 0)))
    size = params.get("size", 1.0)
    font_path = params.get("font", "")

    try:
        bpy.ops.object.text_add(location=location)
        obj = bpy.context.active_object

        if name:
            obj.name = name
            obj.data.name = name

        obj.data.body = text
        obj.data.size = float(size)

        if font_path:
            font = bpy.data.fonts.load(font_path)
            obj.data.font = font

        return {
            "name": obj.name,
            "text": text,
            "size": size,
            "location": list(obj.location),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to create text: {e}")


def register():
    """Register curve handlers with the dispatcher."""
    dispatcher.register_handler("create_curve", handle_create_curve)
    dispatcher.register_handler("add_curve_point", handle_add_curve_point)
    dispatcher.register_handler("set_curve_property", handle_set_curve_property)
    dispatcher.register_handler("convert_curve_to_mesh", handle_convert_curve_to_mesh)
    dispatcher.register_handler("create_text", handle_create_text)
