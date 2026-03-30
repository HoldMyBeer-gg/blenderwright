"""Blender handlers for camera operations."""

import base64
import os
import tempfile

import bpy
from .. import dispatcher


def _get_camera_object(name: str):
    """Get a camera object by name or raise."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.type != 'CAMERA':
        raise ValueError(f"Object '{name}' is not a camera (type: {obj.type})")
    return obj


def handle_create_camera(params: dict) -> dict:
    """Create a new camera."""
    try:
        name = params.get("name", "Camera")
        location = tuple(params.get("location", (0, 0, 0)))
        rotation = tuple(params.get("rotation", (0, 0, 0)))
        lens = params.get("lens", 50.0)

        # Create camera data
        cam_data = bpy.data.cameras.new(name=name)
        cam_data.lens = lens

        # Create camera object
        cam_obj = bpy.data.objects.new(name=name, object_data=cam_data)
        cam_obj.location = location
        cam_obj.rotation_euler = rotation

        # Link to active collection
        bpy.context.collection.objects.link(cam_obj)

        return {
            "name": cam_obj.name,
            "lens": cam_data.lens,
            "location": list(cam_obj.location),
            "rotation": list(cam_obj.rotation_euler),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to create camera: {e}")


def handle_set_camera_property(params: dict) -> dict:
    """Set a property on a camera."""
    try:
        name = params["name"]
        prop = params["property"]
        value = params["value"]

        obj = _get_camera_object(name)
        cam = obj.data

        if prop == "lens":
            cam.lens = value
        elif prop == "clip_start":
            cam.clip_start = value
        elif prop == "clip_end":
            cam.clip_end = value
        elif prop == "sensor_width":
            cam.sensor_width = value
        elif prop == "sensor_height":
            cam.sensor_height = value
        elif prop == "dof.use_dof":
            cam.dof.use_dof = value
        elif prop == "dof.focus_distance":
            cam.dof.focus_distance = value
        elif prop == "dof.aperture_fstop":
            cam.dof.aperture_fstop = value
        elif prop == "ortho_scale":
            cam.ortho_scale = value
        elif prop == "shift_x":
            cam.shift_x = value
        elif prop == "shift_y":
            cam.shift_y = value
        elif prop == "type":
            cam.type = value
        elif prop == "sensor_fit":
            cam.sensor_fit = value
        else:
            raise ValueError(f"Unknown camera property: '{prop}'")

        return {"camera": obj.name, "property": prop, "value": value}
    except Exception as e:
        raise RuntimeError(f"Failed to set camera property: {e}")


def handle_set_active_camera(params: dict) -> dict:
    """Set the active scene camera."""
    try:
        name = params["name"]
        obj = _get_camera_object(name)
        bpy.context.scene.camera = obj
        return {"active_camera": obj.name}
    except Exception as e:
        raise RuntimeError(f"Failed to set active camera: {e}")


def handle_point_camera_at(params: dict) -> dict:
    """Point camera at an object or location using Track To constraint."""
    try:
        camera_name = params["camera_name"]
        cam_obj = _get_camera_object(camera_name)

        # Remove existing Track To constraints named "BlendAI_TrackTo"
        for c in cam_obj.constraints:
            if c.name == "BlendAI_TrackTo":
                cam_obj.constraints.remove(c)

        if "target" in params and params["target"]:
            target_name = params["target"]
            target_obj = bpy.data.objects.get(target_name)
            if target_obj is None:
                raise ValueError(f"Target object '{target_name}' not found")

            constraint = cam_obj.constraints.new(type='TRACK_TO')
            constraint.name = "BlendAI_TrackTo"
            constraint.target = target_obj
            constraint.track_axis = 'TRACK_NEGATIVE_Z'
            constraint.up_axis = 'UP_Y'

            return {
                "camera": cam_obj.name,
                "tracking": target_name,
                "method": "track_to_constraint",
            }
        elif "location" in params and params["location"] is not None:
            target_loc = tuple(params["location"])

            # Create an empty at the target location to track
            empty = bpy.data.objects.new("BlendAI_CameraTarget", None)
            empty.location = target_loc
            empty.empty_display_size = 0.25
            empty.empty_display_type = 'PLAIN_AXES'
            bpy.context.collection.objects.link(empty)

            constraint = cam_obj.constraints.new(type='TRACK_TO')
            constraint.name = "BlendAI_TrackTo"
            constraint.target = empty
            constraint.track_axis = 'TRACK_NEGATIVE_Z'
            constraint.up_axis = 'UP_Y'

            return {
                "camera": cam_obj.name,
                "tracking_location": list(target_loc),
                "tracking_empty": empty.name,
                "method": "track_to_empty",
            }
        else:
            raise ValueError("Must provide 'target' or 'location'")
    except Exception as e:
        raise RuntimeError(f"Failed to point camera: {e}")


def handle_capture_viewport(params: dict) -> dict:
    """Render viewport to file or return base64."""
    try:
        filepath = params.get("filepath", "")
        width = params.get("width", 1920)
        height = params.get("height", 1080)

        scene = bpy.context.scene

        # Store original settings
        orig_x = scene.render.resolution_x
        orig_y = scene.render.resolution_y
        orig_percentage = scene.render.resolution_percentage
        orig_filepath = scene.render.filepath
        orig_file_format = scene.render.image_settings.file_format

        # Set render resolution
        scene.render.resolution_x = width
        scene.render.resolution_y = height
        scene.render.resolution_percentage = 100

        use_temp = not filepath
        if use_temp:
            temp_dir = tempfile.mkdtemp()
            filepath = os.path.join(temp_dir, "viewport_capture.png")

        scene.render.filepath = filepath
        scene.render.image_settings.file_format = 'PNG'

        # Render
        bpy.ops.render.render(write_still=True)

        result = {"width": width, "height": height}

        if use_temp:
            # Read file and encode as base64
            with open(filepath, "rb") as f:
                image_data = f.read()
            result["base64"] = base64.b64encode(image_data).decode("ascii")
            result["format"] = "png"
            # Clean up temp file
            try:
                os.remove(filepath)
                os.rmdir(temp_dir)
            except OSError:
                pass
        else:
            result["filepath"] = filepath

        # Restore original settings
        scene.render.resolution_x = orig_x
        scene.render.resolution_y = orig_y
        scene.render.resolution_percentage = orig_percentage
        scene.render.filepath = orig_filepath
        scene.render.image_settings.file_format = orig_file_format

        return result
    except Exception as e:
        raise RuntimeError(f"Failed to capture viewport: {e}")


def handle_fast_viewport_capture(params: dict) -> dict:
    """Capture viewport using OpenGL render (fast, no render cycle)."""
    width = params.get("width", 1920)
    height = params.get("height", 1080)

    scene = bpy.context.scene

    # Store original settings
    orig_x = scene.render.resolution_x
    orig_y = scene.render.resolution_y
    orig_pct = scene.render.resolution_percentage

    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100

    try:
        # Find a 3D viewport for context
        found = False
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    with bpy.context.temp_override(window=window, area=area):
                        bpy.ops.render.opengl(write_still=True)
                    found = True
                    break
            if found:
                break

        if not found:
            raise RuntimeError("No 3D viewport found for fast capture")

        # Save render result to temp file
        img = bpy.data.images.get("Render Result")
        if img is None:
            raise RuntimeError("No render result after viewport capture")

        temp_dir = tempfile.mkdtemp()
        filepath = os.path.join(temp_dir, "viewport_fast.png")

        img.save_render(filepath)

        with open(filepath, "rb") as f:
            image_data = f.read()

        result = {
            "base64": base64.b64encode(image_data).decode("ascii"),
            "format": "png",
            "width": width,
            "height": height,
            "mode": "fast",
        }

        try:
            os.remove(filepath)
            os.rmdir(temp_dir)
        except OSError:
            pass

        return result
    finally:
        scene.render.resolution_x = orig_x
        scene.render.resolution_y = orig_y
        scene.render.resolution_percentage = orig_pct


def handle_set_camera_from_view(params: dict) -> dict:
    """Match camera to current 3D viewport."""
    try:
        # Find a 3D viewport
        area = None
        for a in bpy.context.screen.areas:
            if a.type == 'VIEW_3D':
                area = a
                break

        if area is None:
            raise ValueError("No 3D viewport found")

        cam_obj = bpy.context.scene.camera
        if cam_obj is None:
            raise ValueError("No active camera in scene")

        # Get the 3D view's region_3d
        region_3d = None
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                region_3d = space.region_3d
                break

        if region_3d is None:
            raise ValueError("Could not access 3D view region")

        # Copy view matrix to camera
        view_matrix = region_3d.view_matrix.inverted()
        cam_obj.matrix_world = view_matrix

        return {
            "camera": cam_obj.name,
            "location": list(cam_obj.location),
            "rotation": list(cam_obj.rotation_euler),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to set camera from view: {e}")


def register():
    """Register all camera handlers with the dispatcher."""
    dispatcher.register_handler("create_camera", handle_create_camera)
    dispatcher.register_handler("set_camera_property", handle_set_camera_property)
    dispatcher.register_handler("set_active_camera", handle_set_active_camera)
    dispatcher.register_handler("point_camera_at", handle_point_camera_at)
    dispatcher.register_handler("capture_viewport", handle_capture_viewport)
    dispatcher.register_handler("fast_viewport_capture", handle_fast_viewport_capture)
    dispatcher.register_handler("set_camera_from_view", handle_set_camera_from_view)
