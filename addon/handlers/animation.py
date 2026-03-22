"""Blender handlers for animation operations."""

import bpy
from .. import dispatcher


def _get_object(name):
    """Get a Blender object by name, raising if not found."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    return obj


def _parse_data_path(data_path):
    """Parse a data_path like 'location[0]' into (base_path, index).

    Returns:
        Tuple of (base_path, index) where index is None for full-vector paths.
    """
    if "[" in data_path and data_path.endswith("]"):
        bracket_pos = data_path.index("[")
        base = data_path[:bracket_pos]
        index = int(data_path[bracket_pos + 1:-1])
        return base, index
    return data_path, None


def handle_insert_keyframe(params):
    """Insert a keyframe on an object property."""
    obj = _get_object(params["object_name"])
    data_path = params["data_path"]
    frame = params["frame"]
    value = params.get("value")

    base_path, index = _parse_data_path(data_path)

    # Set value if provided
    if value is not None:
        prop = getattr(obj, base_path)
        if index is not None:
            prop[index] = value
        else:
            if isinstance(value, (list, tuple)):
                for i, v in enumerate(value):
                    prop[i] = v
            else:
                setattr(obj, base_path, value)

    # Insert keyframe
    if index is not None:
        obj.keyframe_insert(data_path=base_path, index=index, frame=frame)
    else:
        obj.keyframe_insert(data_path=base_path, frame=frame)

    return {
        "object": obj.name,
        "data_path": data_path,
        "frame": frame,
    }


def handle_delete_keyframe(params):
    """Delete a keyframe from an object property."""
    obj = _get_object(params["object_name"])
    data_path = params["data_path"]
    frame = params["frame"]

    base_path, index = _parse_data_path(data_path)

    bpy.context.scene.frame_set(frame)

    if index is not None:
        obj.keyframe_delete(data_path=base_path, index=index, frame=frame)
    else:
        obj.keyframe_delete(data_path=base_path, frame=frame)

    return {
        "object": obj.name,
        "data_path": data_path,
        "frame": frame,
    }


def handle_set_frame(params):
    """Set the current frame."""
    frame = params["frame"]
    bpy.context.scene.frame_set(frame)
    return {"frame": bpy.context.scene.frame_current}


def handle_set_frame_range(params):
    """Set the start and end frames."""
    start = params["start"]
    end = params["end"]

    bpy.context.scene.frame_start = start
    bpy.context.scene.frame_end = end

    return {
        "frame_start": bpy.context.scene.frame_start,
        "frame_end": bpy.context.scene.frame_end,
    }


def handle_set_interpolation(params):
    """Set interpolation type for keyframes on a property."""
    obj = _get_object(params["object_name"])
    data_path = params["data_path"]
    interpolation = params.get("interpolation", "BEZIER")

    base_path, index = _parse_data_path(data_path)

    if obj.animation_data is None or obj.animation_data.action is None:
        raise ValueError(f"Object '{obj.name}' has no animation data")

    action = obj.animation_data.action
    changed = 0

    for fcurve in action.fcurves:
        if fcurve.data_path == base_path:
            if index is not None and fcurve.array_index != index:
                continue
            for keyframe_point in fcurve.keyframe_points:
                keyframe_point.interpolation = interpolation
                changed += 1

    if changed == 0:
        raise ValueError(
            f"No keyframes found for data_path '{data_path}' on '{obj.name}'"
        )

    return {
        "object": obj.name,
        "data_path": data_path,
        "interpolation": interpolation,
        "keyframes_updated": changed,
    }


def handle_create_animation_path(params):
    """Create a Follow Path constraint on an object."""
    obj = _get_object(params["object_name"])
    path_obj = _get_object(params["path_object"])

    if path_obj.type != "CURVE":
        raise ValueError(f"Path object '{path_obj.name}' is not a curve")

    constraint = obj.constraints.new(type="FOLLOW_PATH")
    constraint.target = path_obj
    constraint.use_curve_follow = True

    # Animate the offset to move along the path
    path_obj.data.use_path = True

    return {
        "object": obj.name,
        "path_object": path_obj.name,
        "constraint": constraint.name,
    }


def handle_list_keyframes(params):
    """List all keyframes on an object."""
    obj = _get_object(params["object_name"])

    if obj.animation_data is None or obj.animation_data.action is None:
        return []

    action = obj.animation_data.action
    keyframes = []

    for fcurve in action.fcurves:
        data_path = fcurve.data_path
        array_index = fcurve.array_index

        for kp in fcurve.keyframe_points:
            keyframes.append({
                "data_path": data_path,
                "array_index": array_index,
                "frame": kp.co[0],
                "value": kp.co[1],
                "interpolation": kp.interpolation,
            })

    # Sort by frame
    keyframes.sort(key=lambda k: k["frame"])
    return keyframes


def handle_clear_animation(params):
    """Remove all animation data from an object."""
    obj = _get_object(params["object_name"])

    if obj.animation_data is not None:
        obj.animation_data_clear()

    return {"object": obj.name, "cleared": True}


def register():
    """Register all animation handlers with the dispatcher."""
    dispatcher.register_handler("insert_keyframe", handle_insert_keyframe)
    dispatcher.register_handler("delete_keyframe", handle_delete_keyframe)
    dispatcher.register_handler("set_frame", handle_set_frame)
    dispatcher.register_handler("set_frame_range", handle_set_frame_range)
    dispatcher.register_handler("set_interpolation", handle_set_interpolation)
    dispatcher.register_handler("create_animation_path", handle_create_animation_path)
    dispatcher.register_handler("list_keyframes", handle_list_keyframes)
    dispatcher.register_handler("clear_animation", handle_clear_animation)
