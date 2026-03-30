"""Blender addon handlers for armature and rigging commands."""

import bpy
import mathutils
from .. import dispatcher

# Allowed bone properties
ALLOWED_BONE_PROPERTIES = {
    "roll",
    "length",
    "use_connect",
    "use_deform",
    "envelope_distance",
    "head_radius",
    "tail_radius",
    "use_inherit_rotation",
    "use_local_location",
}

# Constraint properties that reference objects by name
CONSTRAINT_TARGET_PROPERTIES = {"target", "pole_target"}


def _ensure_mode(obj, mode):
    """Ensure the given object is in the specified mode."""
    if bpy.context.view_layer.objects.active != obj:
        bpy.context.view_layer.objects.active = obj
    if obj.mode != mode:
        bpy.ops.object.mode_set(mode=mode)


def handle_create_armature(params: dict) -> dict:
    """Create a new armature object."""
    name = params.get("name", "Armature")
    location = params.get("location", [0, 0, 0])

    try:
        # Create armature data and object
        armature_data = bpy.data.armatures.new(name=name)
        armature_obj = bpy.data.objects.new(name=name, object_data=armature_data)
        armature_obj.location = tuple(location)

        # Link to scene
        bpy.context.collection.objects.link(armature_obj)
        bpy.context.view_layer.objects.active = armature_obj

        return {
            "name": armature_obj.name,
            "location": list(armature_obj.location),
            "success": True,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to create armature '{name}': {e}")


def handle_add_bone(params: dict) -> dict:
    """Add a bone to an armature. Enters edit mode automatically."""
    armature_name = params.get("armature_name")
    bone_name = params.get("bone_name")
    head = params.get("head", [0, 0, 0])
    tail = params.get("tail", [0, 0, 1])
    parent_bone = params.get("parent_bone", "")

    try:
        armature_obj = bpy.data.objects.get(armature_name)
        if armature_obj is None:
            raise ValueError(f"Armature '{armature_name}' not found")
        if armature_obj.type != 'ARMATURE':
            raise ValueError(f"Object '{armature_name}' is not an armature")

        # Store previous mode and active object
        prev_active = bpy.context.view_layer.objects.active
        prev_mode = prev_active.mode if prev_active else 'OBJECT'  # noqa: F841

        # Ensure we're in object mode first, then switch to edit mode
        if bpy.context.view_layer.objects.active and bpy.context.view_layer.objects.active.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        bpy.context.view_layer.objects.active = armature_obj
        armature_obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')

        # Create the bone
        edit_bone = armature_obj.data.edit_bones.new(bone_name)
        edit_bone.head = mathutils.Vector(head)
        edit_bone.tail = mathutils.Vector(tail)

        # Set parent if specified
        if parent_bone:
            parent = armature_obj.data.edit_bones.get(parent_bone)
            if parent is None:
                raise ValueError(f"Parent bone '{parent_bone}' not found")
            edit_bone.parent = parent

        actual_name = edit_bone.name

        # Return to object mode
        bpy.ops.object.mode_set(mode='OBJECT')

        return {
            "bone_name": actual_name,
            "head": list(head),
            "tail": list(tail),
            "parent": parent_bone or None,
            "success": True,
        }
    except ValueError:
        # Ensure we return to object mode on error
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
        raise
    except Exception as e:
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
        raise RuntimeError(f"Failed to add bone '{bone_name}': {e}")


def handle_set_bone_property(params: dict) -> dict:
    """Set a property on a bone."""
    armature_name = params.get("armature_name")
    bone_name = params.get("bone_name")
    prop = params.get("property")
    value = params.get("value")

    if prop not in ALLOWED_BONE_PROPERTIES:
        raise ValueError(f"Property '{prop}' not allowed. Allowed: {sorted(ALLOWED_BONE_PROPERTIES)}")

    try:
        armature_obj = bpy.data.objects.get(armature_name)
        if armature_obj is None:
            raise ValueError(f"Armature '{armature_name}' not found")
        if armature_obj.type != 'ARMATURE':
            raise ValueError(f"Object '{armature_name}' is not an armature")

        # Enter edit mode to modify bone properties
        if bpy.context.view_layer.objects.active and bpy.context.view_layer.objects.active.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        bpy.context.view_layer.objects.active = armature_obj
        armature_obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')

        edit_bone = armature_obj.data.edit_bones.get(bone_name)
        if edit_bone is None:
            bpy.ops.object.mode_set(mode='OBJECT')
            raise ValueError(f"Bone '{bone_name}' not found in armature '{armature_name}'")

        setattr(edit_bone, prop, value)

        bpy.ops.object.mode_set(mode='OBJECT')

        return {
            "bone_name": bone_name,
            "property": prop,
            "value": value,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
        raise RuntimeError(f"Failed to set bone property: {e}")


def handle_add_constraint(params: dict) -> dict:
    """Add a constraint to an object or pose bone."""
    object_name = params.get("object_name")
    bone_name = params.get("bone_name", "")
    constraint_type = params.get("constraint_type")
    properties = params.get("properties", {})

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")

        if bone_name:
            # Bone constraint - need pose mode
            if obj.type != 'ARMATURE':
                raise ValueError(f"Object '{object_name}' is not an armature")

            pose_bone = obj.pose.bones.get(bone_name)
            if pose_bone is None:
                raise ValueError(f"Pose bone '{bone_name}' not found")

            constraint = pose_bone.constraints.new(type=constraint_type)
        else:
            # Object constraint
            constraint = obj.constraints.new(type=constraint_type)

        # Set constraint properties
        for prop_name, prop_value in properties.items():
            if prop_name in CONSTRAINT_TARGET_PROPERTIES:
                # Resolve object references by name
                target_obj = bpy.data.objects.get(prop_value)
                if target_obj is None:
                    raise ValueError(f"Target object '{prop_value}' not found")
                setattr(constraint, prop_name, target_obj)
            else:
                setattr(constraint, prop_name, prop_value)

        return {
            "constraint_name": constraint.name,
            "constraint_type": constraint_type,
            "object": object_name,
            "bone": bone_name or None,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to add constraint: {e}")


def handle_parent_mesh_to_armature(params: dict) -> dict:
    """Parent a mesh to an armature with automatic weights or other methods."""
    mesh_name = params.get("mesh_name")
    armature_name = params.get("armature_name")
    parent_type = params.get("type", "ARMATURE_AUTO")

    try:
        mesh_obj = bpy.data.objects.get(mesh_name)
        if mesh_obj is None:
            raise ValueError(f"Mesh object '{mesh_name}' not found")

        armature_obj = bpy.data.objects.get(armature_name)
        if armature_obj is None:
            raise ValueError(f"Armature '{armature_name}' not found")
        if armature_obj.type != 'ARMATURE':
            raise ValueError(f"Object '{armature_name}' is not an armature")

        # Ensure object mode
        if bpy.context.view_layer.objects.active and bpy.context.view_layer.objects.active.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Deselect all, then select mesh and armature
        bpy.ops.object.select_all(action='DESELECT')
        mesh_obj.select_set(True)
        armature_obj.select_set(True)
        bpy.context.view_layer.objects.active = armature_obj

        bpy.ops.object.parent_set(type=parent_type)

        return {
            "mesh": mesh_name,
            "armature": armature_name,
            "type": parent_type,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to parent mesh to armature: {e}")


def handle_set_pose(params: dict) -> dict:
    """Set bone pose transforms."""
    armature_name = params.get("armature_name")
    bone_name = params.get("bone_name")
    location = params.get("location")
    rotation = params.get("rotation")
    scale = params.get("scale")

    try:
        armature_obj = bpy.data.objects.get(armature_name)
        if armature_obj is None:
            raise ValueError(f"Armature '{armature_name}' not found")
        if armature_obj.type != 'ARMATURE':
            raise ValueError(f"Object '{armature_name}' is not an armature")

        # Enter pose mode
        if bpy.context.view_layer.objects.active and bpy.context.view_layer.objects.active.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        bpy.context.view_layer.objects.active = armature_obj
        armature_obj.select_set(True)
        bpy.ops.object.mode_set(mode='POSE')

        pose_bone = armature_obj.pose.bones.get(bone_name)
        if pose_bone is None:
            bpy.ops.object.mode_set(mode='OBJECT')
            raise ValueError(f"Pose bone '{bone_name}' not found")

        result = {
            "armature": armature_name,
            "bone": bone_name,
        }

        if location is not None:
            pose_bone.location = mathutils.Vector(location)
            result["location"] = list(pose_bone.location)

        if rotation is not None:
            pose_bone.rotation_euler = mathutils.Euler(rotation)
            result["rotation"] = list(pose_bone.rotation_euler)

        if scale is not None:
            pose_bone.scale = mathutils.Vector(scale)
            result["scale"] = list(pose_bone.scale)

        bpy.ops.object.mode_set(mode='OBJECT')

        result["success"] = True
        return result
    except ValueError:
        raise
    except Exception as e:
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
        raise RuntimeError(f"Failed to set pose: {e}")


def register():
    """Register armature handlers with the dispatcher."""
    dispatcher.register_handler("create_armature", handle_create_armature)
    dispatcher.register_handler("add_bone", handle_add_bone)
    dispatcher.register_handler("set_bone_property", handle_set_bone_property)
    dispatcher.register_handler("add_constraint", handle_add_constraint)
    dispatcher.register_handler("parent_mesh_to_armature", handle_parent_mesh_to_armature)
    dispatcher.register_handler("set_pose", handle_set_pose)
