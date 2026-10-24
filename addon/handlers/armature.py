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
# RNA property types a caller may set directly
SETTABLE_RNA_TYPES = {"BOOLEAN", "INT", "FLOAT", "ENUM", "STRING"}
BONE_COLLECTION_ACTIONS = {"CREATE", "DELETE", "ASSIGN", "UNASSIGN", "SHOW", "HIDE"}


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
    armature_name = params["armature_name"]
    bone_name = params["bone_name"]
    head = params.get("head", [0, 0, 0])
    tail = params.get("tail", [0, 0, 1])
    parent_bone = params.get("parent_bone", "")

    try:
        armature_obj = bpy.data.objects.get(armature_name)
        if armature_obj is None:
            raise ValueError(f"Armature '{armature_name}' not found")
        if armature_obj.type != 'ARMATURE':
            raise ValueError(f"Object '{armature_name}' is not an armature")

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
    armature_name = params["armature_name"]
    bone_name = params["bone_name"]
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


def _apply_constraint_settings(constraint, constraint_type, properties):
    """Only settings this constraint type declares in RNA, as plain writable
    values; target objects are looked up by name."""
    for prop_name, prop_value in properties.items():
        if prop_name in CONSTRAINT_TARGET_PROPERTIES:
            target_obj = bpy.data.objects.get(prop_value)
            if target_obj is None:
                raise ValueError(f"Target object '{prop_value}' not found")
            setattr(constraint, prop_name, target_obj)
            continue
        rna = constraint.bl_rna.properties.get(prop_name)
        if rna is None or rna.is_readonly or rna.type not in SETTABLE_RNA_TYPES:
            settable = sorted(
                name for name, p in constraint.bl_rna.properties.items()
                if not p.is_readonly and p.type in SETTABLE_RNA_TYPES)
            raise ValueError(f"'{prop_name}' is not a setting of a "
                             f"{constraint_type} constraint. Settings: "
                             f"{', '.join(settable + sorted(CONSTRAINT_TARGET_PROPERTIES))}")
        setattr(constraint, prop_name, prop_value)


def handle_add_constraint(params: dict) -> dict:
    """Add a constraint to an object or pose bone."""
    object_name = params["object_name"]
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

            owner_constraints = pose_bone.constraints
        else:
            owner_constraints = obj.constraints
        constraint = owner_constraints.new(type=constraint_type)

        try:
            _apply_constraint_settings(constraint, constraint_type, properties)
        except Exception:
            owner_constraints.remove(constraint)
            raise

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
    mesh_name = params["mesh_name"]
    armature_name = params["armature_name"]
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
    armature_name = params["armature_name"]
    bone_name = params["bone_name"]
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


def _get_armature(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Armature '{name}' not found")
    if obj.type != "ARMATURE":
        raise ValueError(f"Object '{name}' is not an armature")
    return obj


def _bone_collection_summary(arm):
    return [{"name": c.name, "visible": c.is_visible, "bones": [b.name for b in c.bones],
             "parent": c.parent.name if c.parent is not None else None}
            for c in arm.data.collections_all.values()]


def handle_manage_bone_collection(params: dict) -> dict:
    """Create, delete, fill, empty, show or hide a bone collection."""
    arm = _get_armature(params["armature_name"])
    action = params.get("action")
    if action not in BONE_COLLECTION_ACTIONS:
        raise ValueError(f"Unknown bone collection action {action!r}")
    name = params["collection_name"]
    bones = []
    for bone_name in params.get("bones", []):
        bone = arm.data.bones.get(bone_name)
        if bone is None:
            raise ValueError(f"Bone '{bone_name}' not found in '{arm.name}'")
        bones.append(bone)

    collections = arm.data.collections
    if action == "CREATE":
        parent = None
        if params.get("parent"):
            parent = arm.data.collections_all.get(params["parent"])
            if parent is None:
                raise ValueError(f"Parent bone collection '{params['parent']}' not found")
        collection = collections.new(name, parent=parent)
    else:
        collection = arm.data.collections_all.get(name)
        if collection is None:
            raise ValueError(f"Bone collection '{name}' not found in '{arm.name}'")
    if action in ("CREATE", "ASSIGN"):
        for bone in bones:
            collection.assign(bone)
    elif action == "UNASSIGN":
        for bone in bones:
            collection.unassign(bone)
    elif action in ("SHOW", "HIDE"):
        collection.is_visible = action == "SHOW"
    elif action == "DELETE":
        collections.remove(collection)
    return {"armature": arm.name, "action": action,
            "collections": _bone_collection_summary(arm)}


def handle_setup_ik_chain(params: dict) -> dict:
    """Add a fully configured IK constraint to the last bone of a chain."""
    arm = _get_armature(params["armature_name"])
    pose_bone = arm.pose.bones.get(params["bone_name"])
    if pose_bone is None:
        raise ValueError(f"Pose bone '{params['bone_name']}' not found")
    target = bpy.data.objects.get(params["target_object"])
    if target is None:
        raise ValueError(f"Target object '{params['target_object']}' not found")
    pole = None
    if params.get("pole_object"):
        pole = bpy.data.objects.get(params["pole_object"])
        if pole is None:
            raise ValueError(f"Pole object '{params['pole_object']}' not found")

    ik = pose_bone.constraints.new(type="IK")
    ik.target = target
    ik.subtarget = params.get("target_bone", "")
    if pole is not None:
        ik.pole_target = pole
        ik.pole_subtarget = params.get("pole_bone", "")
        ik.pole_angle = float(params.get("pole_angle", 0.0))
    ik.chain_count = int(params.get("chain_count", 2))
    ik.use_stretch = bool(params.get("use_stretch", False))
    ik.iterations = int(params.get("iterations", 500))
    return {"armature": arm.name, "bone": pose_bone.name, "constraint": ik.name,
            "target": target.name, "pole": pole.name if pole else None,
            "chain_count": ik.chain_count}


def register():
    """Register armature handlers with the dispatcher."""
    dispatcher.register_handler("create_armature", handle_create_armature)
    dispatcher.register_handler("add_bone", handle_add_bone)
    dispatcher.register_handler("set_bone_property", handle_set_bone_property)
    dispatcher.register_handler("add_constraint", handle_add_constraint)
    dispatcher.register_handler("parent_mesh_to_armature", handle_parent_mesh_to_armature)
    dispatcher.register_handler("set_pose", handle_set_pose)
    dispatcher.register_handler("manage_bone_collection", handle_manage_bone_collection)
    dispatcher.register_handler("setup_ik_chain", handle_setup_ik_chain)
