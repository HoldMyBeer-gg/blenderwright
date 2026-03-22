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


def register():
    """Register collection handlers with the dispatcher."""
    dispatcher.register_handler("create_collection", handle_create_collection)
    dispatcher.register_handler("move_to_collection", handle_move_to_collection)
    dispatcher.register_handler("set_collection_visibility", handle_set_collection_visibility)
    dispatcher.register_handler("delete_collection", handle_delete_collection)
