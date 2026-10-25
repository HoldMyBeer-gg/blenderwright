"""Blender addon handlers for collection management commands."""

import bpy
from .. import dispatcher


def _find_collection_parent(target_collection, root=None):
    """Find the parent collection of a given collection."""
    if root is None:
        root = bpy.context.scene.collection

    for child in root.children:
        if child == target_collection:
            return root
        result = _find_collection_parent(target_collection, child)
        if result is not None:
            return result
    return None


def handle_create_collection(params: dict) -> dict:
    """Create a new collection, optionally nested under a parent."""
    name = params.get("name")
    parent_name = params.get("parent", "")

    try:
        new_collection = bpy.data.collections.new(name=name)

        if parent_name:
            parent_collection = bpy.data.collections.get(parent_name)
            if parent_collection is None:
                raise ValueError(f"Parent collection '{parent_name}' not found")
            parent_collection.children.link(new_collection)
        else:
            bpy.context.scene.collection.children.link(new_collection)

        return {
            "name": new_collection.name,
            "parent": parent_name or "Scene Collection",
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to create collection '{name}': {e}")


def handle_move_to_collection(params: dict) -> dict:
    """Move objects to a collection."""
    object_names = params.get("object_names", [])
    collection_name = params.get("collection_name")

    try:
        target_collection = bpy.data.collections.get(collection_name)
        if target_collection is None:
            raise ValueError(f"Collection '{collection_name}' not found")

        moved = []
        for obj_name in object_names:
            obj = bpy.data.objects.get(obj_name)
            if obj is None:
                raise ValueError(f"Object '{obj_name}' not found")

            # Unlink from all current collections
            for col in obj.users_collection:
                col.objects.unlink(obj)

            # Also unlink from scene collection if present
            if obj.name in bpy.context.scene.collection.objects:
                bpy.context.scene.collection.objects.unlink(obj)

            # Link to target collection
            target_collection.objects.link(obj)
            moved.append(obj_name)

        return {
            "moved_objects": moved,
            "collection": collection_name,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to move objects to collection: {e}")


def handle_set_collection_visibility(params: dict) -> dict:
    """Set collection visibility."""
    name = params.get("name")
    visible = params.get("visible")
    affect_viewport = params.get("viewport", True)
    affect_render = params.get("render", True)

    try:
        collection = bpy.data.collections.get(name)
        if collection is None:
            raise ValueError(f"Collection '{name}' not found")

        if affect_render:
            collection.hide_render = not visible

        # For viewport visibility, we need to set it on the view layer's layer collection
        if affect_viewport:
            # Find the layer collection corresponding to this collection
            def find_layer_collection(layer_col, target_name):
                if layer_col.collection.name == target_name:
                    return layer_col
                for child in layer_col.children:
                    result = find_layer_collection(child, target_name)
                    if result is not None:
                        return result
                return None

            view_layer = bpy.context.view_layer
            layer_col = find_layer_collection(view_layer.layer_collection, name)
            if layer_col is not None:
                layer_col.exclude = not visible
            else:
                # Fallback: set hide_viewport on the collection itself
                collection.hide_viewport = not visible

        return {
            "name": name,
            "visible": visible,
            "viewport": affect_viewport,
            "render": affect_render,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set collection visibility: {e}")


def handle_delete_collection(params: dict) -> dict:
    """Delete a collection."""
    name = params.get("name")
    delete_objects = params.get("delete_objects", False)

    try:
        collection = bpy.data.collections.get(name)
        if collection is None:
            raise ValueError(f"Collection '{name}' not found")

        if delete_objects:
            # Delete all objects in the collection
            for obj in list(collection.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
        else:
            # Move objects to the scene's root collection before removing
            scene_collection = bpy.context.scene.collection
            for obj in list(collection.objects):
                if obj.name not in scene_collection.objects:
                    scene_collection.objects.link(obj)
                collection.objects.unlink(obj)

        # Remove the collection
        bpy.data.collections.remove(collection)

        return {
            "name": name,
            "objects_deleted": delete_objects,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to delete collection '{name}': {e}")


def _activate(obj):
    """obj as the only selected, active object, in object mode."""
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def handle_create_collection_instance(params: dict) -> dict:
    """Place a collection as an instance empty."""
    name = params.get("collection_name")
    collection = bpy.data.collections.get(name)
    if collection is None:
        raise ValueError(f"Collection '{name}' not found")
    inst = bpy.data.objects.new(params.get("name") or collection.name, None)
    inst.instance_type = "COLLECTION"
    inst.instance_collection = collection
    inst.location = params.get("location", [0, 0, 0])
    inst.rotation_euler = params.get("rotation", [0, 0, 0])
    inst.scale = params.get("scale", [1, 1, 1])
    bpy.context.scene.collection.objects.link(inst)
    return {"name": inst.name, "collection": collection.name}


def handle_make_instances_real(params: dict) -> dict:
    """Turn a collection instance into real objects."""
    name = params.get("object_name")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.instance_type != "COLLECTION" or obj.instance_collection is None:
        raise ValueError(f"'{name}' is not a collection instance")
    _activate(obj)
    result = bpy.ops.object.duplicates_make_real(
        use_base_parent=False, use_hierarchy=bool(params.get("keep_hierarchy", False)))
    if result != {"FINISHED"}:
        raise RuntimeError(f"Could not make '{name}' real: {result}")
    return {"instance": name, "objects": [o.name for o in bpy.context.selected_objects]}


LAYER_COLLECTION_FLAGS = ("exclude", "holdout", "indirect_only")


def _active_view_layer():
    window = bpy.context.window
    return window.view_layer if window is not None else bpy.context.view_layer


def _get_view_layer(name):
    layers = bpy.context.scene.view_layers
    layer = layers.get(name)
    if layer is None:
        raise ValueError(f"No view layer '{name}'; there are {[v.name for v in layers]}")
    return layer


def _view_layers():
    active = _active_view_layer()
    return [{"name": v.name, "active": v == active, "use_for_render": v.use,
             "material_override": v.material_override.name if v.material_override else None,
             "world_override": v.world_override.name if v.world_override else None}
            for v in bpy.context.scene.view_layers]


def _override(source, name, label):
    if name == "":
        return None
    target = source.get(name)
    if target is None:
        raise ValueError(f"{label} '{name}' not found")
    return target


def handle_manage_view_layer(params):
    scene = bpy.context.scene
    action = params.get("action")
    name = params.get("view_layer")
    if action == "ADD":
        if scene.view_layers.get(name) is not None:
            raise ValueError(f"A view layer '{name}' already exists")
        scene.view_layers.new(name)
    elif action == "REMOVE":
        layer = _get_view_layer(name)
        if len(scene.view_layers) == 1:
            raise ValueError("Cannot remove the last view layer")
        scene.view_layers.remove(layer)
    elif action == "RENAME":
        _get_view_layer(name).name = params["new_name"]
    elif action == "SET_ACTIVE":
        layer = _get_view_layer(name)
        if bpy.context.window is None:
            raise RuntimeError("No window to switch the active view layer in")
        bpy.context.window.view_layer = layer
    elif action == "SET":
        layer = _get_view_layer(name)
        if "material_override" in params:
            layer.material_override = _override(bpy.data.materials,
                                                params["material_override"], "Material")
        if "world_override" in params:
            layer.world_override = _override(bpy.data.worlds, params["world_override"], "World")
        if "use_for_render" in params:
            layer.use = bool(params["use_for_render"])
    elif action != "LIST":
        raise ValueError(f"Unknown action {action!r}")
    return {"view_layers": _view_layers()}


def _find_layer_collection(layer_col, name):
    if layer_col.collection.name == name:
        return layer_col
    for child in layer_col.children:
        found = _find_layer_collection(child, name)
        if found is not None:
            return found
    return None


def handle_set_layer_collection(params):
    layer = (_get_view_layer(params["view_layer"]) if params.get("view_layer")
             else _active_view_layer())
    name = params.get("collection_name")
    layer_col = _find_layer_collection(layer.layer_collection, name)
    if layer_col is None:
        raise ValueError(f"Collection '{name}' is not in view layer '{layer.name}'")
    for key in LAYER_COLLECTION_FLAGS:
        if key in params:
            setattr(layer_col, key, bool(params[key]))
    return {"collection": name, "view_layer": layer.name,
            **{key: getattr(layer_col, key) for key in LAYER_COLLECTION_FLAGS}}


def register():
    """Register collection handlers with the dispatcher."""
    dispatcher.register_handler("create_collection", handle_create_collection)
    dispatcher.register_handler("move_to_collection", handle_move_to_collection)
    dispatcher.register_handler("set_collection_visibility", handle_set_collection_visibility)
    dispatcher.register_handler("delete_collection", handle_delete_collection)
    dispatcher.register_handler("create_collection_instance", handle_create_collection_instance)
    dispatcher.register_handler("make_instances_real", handle_make_instances_real)
    dispatcher.register_handler("manage_view_layer", handle_manage_view_layer)
    dispatcher.register_handler("set_layer_collection", handle_set_layer_collection)
