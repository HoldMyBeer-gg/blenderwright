"""Blender addon handlers for sculpting commands."""

import bpy
from .. import dispatcher

ESSENTIALS_SCULPT_BRUSHES = "brushes/essentials_brushes-mesh_sculpt.blend"

# Tool brush types mapped to Essentials sculpt brush asset names
BRUSH_ASSETS = {
    "DRAW": "Draw",
    "CLAY": "Clay",
    "CLAY_STRIPS": "Clay Strips",
    "INFLATE": "Inflate/Deflate",
    "GRAB": "Grab",
    "SMOOTH": "Smooth",
    "FLATTEN": "Flatten/Contrast",
    "FILL": "Fill/Deepen",
    "SCRAPE": "Scrape/Fill",
    "PINCH": "Pinch/Magnify",
    "CREASE": "Crease Polish",
    "BLOB": "Blob",
    "MASK": "Mask",
    "MULTIRES_DISPLACEMENT_SMEAR": "Smear Multires Displacement",
}


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
        # Sculpt brushes are assets in the Essentials library
        asset_name = BRUSH_ASSETS.get(brush_type)
        if asset_name is None:
            raise ValueError(f"Unknown brush type: {brush_type}")

        result = bpy.ops.brush.asset_activate(
            asset_library_type="ESSENTIALS",
            relative_asset_identifier=f"{ESSENTIALS_SCULPT_BRUSHES}/Brush/{asset_name}",
        )
        if result != {"FINISHED"}:
            raise RuntimeError(f"Brush asset '{asset_name}' did not activate: {result}")

        return {
            "brush_type": brush_type,
            "brush": asset_name,
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
        elif prop == "stroke_method":
            ALLOWED_STROKE_METHODS = {
                "DOTS", "DRAG_DOT", "SPACE", "AIRBRUSH",
                "ANCHORED", "LINE", "CURVE",
            }
            if value not in ALLOWED_STROKE_METHODS:
                raise ValueError(
                    f"stroke_method '{value}' not in "
                    f"{sorted(ALLOWED_STROKE_METHODS)}"
                )
            brush.stroke_method = value
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


# Voxel remesh builds a grid across the object's bounding box. Blender accepts
# any size and then grinds: a 2m object at 0.001 is 2000^3 cells, which takes
# longer than the caller's socket will wait, so the call dies on a timeout that
# explains nothing. Only this layer knows the object's size, so the budget
# lives here.
MAX_VOXEL_GRID_CELLS = 40_000_000


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

        applied_voxel_size = None
        if mode == "VOXEL":
            size = float(voxel_size)
            dims = [max(float(d), 1e-6) for d in obj.dimensions]
            cells = 1.0
            for d in dims:
                cells *= d / size
            if cells > MAX_VOXEL_GRID_CELLS:
                workable = (
                    (dims[0] * dims[1] * dims[2]) / MAX_VOXEL_GRID_CELLS
                ) ** (1.0 / 3.0)
                raise ValueError(
                    f"voxel_size {size:g} on an object measuring "
                    f"{dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} needs about "
                    f"{cells:,.0f} voxels, which hangs Blender rather than "
                    f"failing. Use {workable:.3f} or larger."
                )
            obj.data.remesh_voxel_size = size
            bpy.ops.object.voxel_remesh()
            applied_voxel_size = size
        else:
            # SHARP, SMOOTH and BLOCKS use the remesh modifier, which has no
            # voxel size at all. It was previously accepted and ignored while
            # the result reported success.
            mod = obj.modifiers.new(name="Remesh", type='REMESH')
            mod.mode = mode
            mod.octree_depth = 6
            bpy.ops.object.modifier_apply(modifier=mod.name)

        vertex_count = len(obj.data.vertices)

        return {
            "object_name": obj.name,
            "mode": mode,
            "voxel_size": applied_voxel_size,
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


def handle_set_sculpt_symmetry(params: dict) -> dict:
    """Set sculpt symmetry axes."""
    try:
        sculpt = bpy.context.tool_settings.sculpt
        if sculpt is None:
            raise ValueError("Sculpt settings not available. Enter sculpt mode first.")

        sculpt.use_symmetry_x = params.get("use_x", True)
        sculpt.use_symmetry_y = params.get("use_y", False)
        sculpt.use_symmetry_z = params.get("use_z", False)

        return {
            "use_x": sculpt.use_symmetry_x,
            "use_y": sculpt.use_symmetry_y,
            "use_z": sculpt.use_symmetry_z,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to set sculpt symmetry: {e}")


def handle_enable_dyntopo(params: dict) -> dict:
    """Enable dynamic topology for sculpting."""
    object_name = params.get("object_name")
    detail_size = params.get("detail_size", 12.0)
    detail_mode = params.get("detail_mode", "RELATIVE")

    try:
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            raise ValueError(f"Object '{object_name}' not found")
        if obj.type != "MESH":
            raise ValueError(f"Object '{object_name}' is not a mesh")

        # Select and make active
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Enter sculpt mode if not already in it
        if obj.mode != "SCULPT":
            bpy.ops.object.mode_set(mode="SCULPT")

        # Enable dyntopo if not already active
        if not bpy.context.sculpt_object.use_dynamic_topology_sculpting:
            bpy.ops.sculpt.dynamic_topology_toggle()

        bpy.context.tool_settings.sculpt.detail_size = float(detail_size)
        bpy.context.tool_settings.sculpt.detail_type_method = detail_mode

        return {
            "object_name": obj.name,
            "dyntopo": True,
            "detail_size": detail_size,
            "detail_mode": detail_mode,
            "success": True,
        }
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to enable dyntopo: {e}")


MASK_ATTRIBUTE = ".sculpt_mask"
FACE_SET_ATTRIBUTE = ".sculpt_face_set"


def _get_mesh(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{name}' is not a mesh (type: {obj.type})")
    return obj


def _select_only(obj):
    bpy.context.view_layer.objects.active = obj


def _check_range(indices, count, what):
    bad = [i for i in indices if not 0 <= i < count]
    if bad:
        raise ValueError(f"{what} index {bad[0]} is out of range (0 to {count - 1})")


def _in_object_mode(obj, write):
    """Sculpt mode caches mesh data, so leave it, write the attributes, and
    go back. Plain attribute writes: the mask operators crash headless 5.2.3."""
    mode = obj.mode
    if mode != "OBJECT":
        _select_only(obj)
        bpy.ops.object.mode_set(mode="OBJECT")
    try:
        return write()
    finally:
        if mode != "OBJECT":
            bpy.ops.object.mode_set(mode=mode)


def _attribute(mesh, name, data_type, domain):
    attr = mesh.attributes.get(name)
    return attr if attr is not None else mesh.attributes.new(name, data_type, domain)


def handle_set_sculpt_mask(params):
    obj = _get_mesh(params.get("object_name"))
    mesh = obj.data

    def write():
        if params.get("clear"):
            attr = mesh.attributes.get(MASK_ATTRIBUTE)
            if attr is not None:
                mesh.attributes.remove(attr)
            return {"object": obj.name, "masked": 0, "vertex_count": len(mesh.vertices)}
        attr = _attribute(mesh, MASK_ATTRIBUTE, "FLOAT", "POINT")
        data = attr.data
        if params.get("invert"):
            for item in data:
                item.value = 1.0 - item.value
        else:
            value = float(params.get("value", 1.0))
            if params.get("vertex_group"):
                vg = obj.vertex_groups.get(params["vertex_group"])
                if vg is None:
                    raise ValueError(f"'{obj.name}' has no vertex group "
                                     f"'{params['vertex_group']}'")
                for v in mesh.vertices:
                    weight = next((g.weight for g in v.groups if g.group == vg.index), 0.0)
                    data[v.index].value = value * weight
            elif params.get("vertex_indices") is not None:
                indices = list(params["vertex_indices"])
                _check_range(indices, len(mesh.vertices), "Vertex")
                for i in indices:
                    data[i].value = value
            else:
                for item in data:
                    item.value = value
        return {"object": obj.name, "masked": sum(1 for item in data if item.value > 0.0),
                "vertex_count": len(mesh.vertices)}

    return _in_object_mode(obj, write)


def _loose_parts(mesh):
    parent = {}

    def find(v):
        while parent.setdefault(v, v) != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for poly in mesh.polygons:
        first = find(poly.vertices[0])
        for v in poly.vertices[1:]:
            parent[find(v)] = first
    ids = {}
    return [ids.setdefault(find(poly.vertices[0]), len(ids) + 1) for poly in mesh.polygons]


def handle_set_face_sets(params):
    obj = _get_mesh(params.get("object_name"))
    mesh = obj.data
    mode = params.get("mode")
    if mode not in {"LOOSE_PARTS", "MATERIALS", "ASSIGN", "CLEAR"}:
        raise ValueError(f"Unknown mode {mode!r}")

    def write():
        if mode == "CLEAR":
            attr = mesh.attributes.get(FACE_SET_ATTRIBUTE)
            if attr is not None:
                mesh.attributes.remove(attr)
            return {"object": obj.name, "face_sets": 0}
        attr = _attribute(mesh, FACE_SET_ATTRIBUTE, "INT", "FACE")
        if mode == "ASSIGN":
            indices = list(params.get("face_indices") or [])
            _check_range(indices, len(mesh.polygons), "Face")
            if not any(item.value for item in attr.data):
                for item in attr.data:
                    item.value = 1
            for i in indices:
                attr.data[i].value = int(params.get("face_set", 1))
        else:
            values = (_loose_parts(mesh) if mode == "LOOSE_PARTS"
                      else [poly.material_index + 1 for poly in mesh.polygons])
            for item, value in zip(attr.data, values):
                item.value = value
        return {"object": obj.name, "face_sets": len({item.value for item in attr.data})}

    return _in_object_mode(obj, write)


def register():
    """Register sculpting handlers with the dispatcher."""
    dispatcher.register_handler("enter_sculpt_mode", handle_enter_sculpt_mode)
    dispatcher.register_handler("exit_sculpt_mode", handle_exit_sculpt_mode)
    dispatcher.register_handler("set_sculpt_brush", handle_set_sculpt_brush)
    dispatcher.register_handler("set_brush_property", handle_set_brush_property)
    dispatcher.register_handler("remesh", handle_remesh)
    dispatcher.register_handler("add_multires_modifier", handle_add_multires_modifier)
    dispatcher.register_handler("set_sculpt_symmetry", handle_set_sculpt_symmetry)
    dispatcher.register_handler("enable_dyntopo", handle_enable_dyntopo)
    dispatcher.register_handler("set_sculpt_mask", handle_set_sculpt_mask)
    dispatcher.register_handler("set_face_sets", handle_set_face_sets)
