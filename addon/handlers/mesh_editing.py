"""Blender handlers for edit-mode mesh operations."""

import bpy
from .. import dispatcher


def _ensure_object_mode():
    """Ensure we are in object mode."""
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _select_only(obj):
    """Deselect all and select only the given object, making it active."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _get_mesh_object(name):
    """Get a Blender mesh object by name, raising if not found or not a mesh."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{name}' is not a mesh")
    return obj


def _enter_edit_select_all(obj):
    """Select object, enter edit mode, and select all geometry."""
    _select_only(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")


def handle_inset_faces(params):
    """Inset all faces of a mesh."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])
    thickness = params.get("thickness", 0.1)
    depth = params.get("depth", 0.0)

    _enter_edit_select_all(obj)
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.mesh.inset(thickness=thickness, depth=depth)
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name, "thickness": thickness, "depth": depth}


def handle_fill_faces(params):
    """Fill selected edges with a face."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])

    _enter_edit_select_all(obj)
    bpy.ops.mesh.fill()
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name}


def handle_grid_fill(params):
    """Fill a closed edge loop with a grid of quads."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])
    span = params.get("span", 1)
    offset = params.get("offset", 0)

    _enter_edit_select_all(obj)
    bpy.ops.mesh.fill_grid(span=span, offset=offset)
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name, "span": span, "offset": offset}


def handle_mark_seam(params):
    """Mark or clear UV seams on all edges."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])
    clear = params.get("clear", False)

    _enter_edit_select_all(obj)
    bpy.ops.mesh.select_mode(type="EDGE")
    bpy.ops.mesh.mark_seam(clear=clear)
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name, "clear": clear}


def handle_mark_sharp(params):
    """Mark or clear sharp edges."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])
    clear = params.get("clear", False)

    _enter_edit_select_all(obj)
    bpy.ops.mesh.select_mode(type="EDGE")
    bpy.ops.mesh.mark_sharp(clear=clear)
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name, "clear": clear}


def handle_recalculate_normals(params):
    """Recalculate face normals to be consistent."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])
    inside = params.get("inside", False)

    _enter_edit_select_all(obj)
    bpy.ops.mesh.normals_make_consistent(inside=inside)
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name, "inside": inside}


def handle_flip_normals(params):
    """Flip all face normals."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])

    _enter_edit_select_all(obj)
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name}


def handle_quads_to_tris(params):
    """Convert all quad faces to triangles."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])

    _enter_edit_select_all(obj)
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name}


def handle_tris_to_quads(params):
    """Convert adjacent triangles to quads."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])

    _enter_edit_select_all(obj)
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.mesh.tris_convert_to_quads()
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name}


def handle_dissolve_faces(params):
    """Dissolve all faces."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])

    _enter_edit_select_all(obj)
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.mesh.dissolve_faces()
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name}


def handle_dissolve_edges(params):
    """Dissolve all edges."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])

    _enter_edit_select_all(obj)
    bpy.ops.mesh.select_mode(type="EDGE")
    bpy.ops.mesh.dissolve_edges()
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name}


def handle_dissolve_verts(params):
    """Dissolve all vertices."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])

    _enter_edit_select_all(obj)
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.dissolve_verts()
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name}


def handle_knife_project(params):
    """Project a cutter object onto a mesh."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])

    cutter_name = params["cutter_name"]
    cutter = bpy.data.objects.get(cutter_name)
    if cutter is None:
        raise ValueError(f"Cutter object '{cutter_name}' not found")

    # Bool Tool pattern: cutter selected, target active in edit mode
    bpy.ops.object.select_all(action="DESELECT")
    cutter.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.knife_project()
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name, "cutter": cutter.name}


def handle_spin_mesh(params):
    """Spin mesh geometry around an axis."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])
    angle = params.get("angle", 6.283185307179586)
    steps = params.get("steps", 12)
    axis = tuple(params.get("axis", (0, 0, 1)))
    center = tuple(params.get("center", (0, 0, 0)))

    _enter_edit_select_all(obj)
    bpy.ops.mesh.spin(angle=angle, steps=steps, axis=axis, center=center)
    bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "object": obj.name,
        "angle": angle,
        "steps": steps,
        "axis": list(axis),
        "center": list(center),
    }


def handle_set_edge_crease(params):
    """Set edge crease on all edges."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])
    value = params.get("value", 1.0)

    _enter_edit_select_all(obj)
    bpy.ops.mesh.select_mode(type="EDGE")
    bpy.ops.transform.edge_crease(value=value)
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name, "value": value}


def handle_select_linked(params):
    """Select all linked geometry."""
    _ensure_object_mode()
    obj = _get_mesh_object(params["object_name"])

    _enter_edit_select_all(obj)
    bpy.ops.mesh.select_linked()
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"object": obj.name}


def register():
    """Register all mesh editing handlers with the dispatcher."""
    dispatcher.register_handler("inset_faces", handle_inset_faces)
    dispatcher.register_handler("fill_faces", handle_fill_faces)
    dispatcher.register_handler("grid_fill", handle_grid_fill)
    dispatcher.register_handler("mark_seam", handle_mark_seam)
    dispatcher.register_handler("mark_sharp", handle_mark_sharp)
    dispatcher.register_handler("recalculate_normals", handle_recalculate_normals)
    dispatcher.register_handler("flip_normals", handle_flip_normals)
    dispatcher.register_handler("quads_to_tris", handle_quads_to_tris)
    dispatcher.register_handler("tris_to_quads", handle_tris_to_quads)
    dispatcher.register_handler("dissolve_faces", handle_dissolve_faces)
    dispatcher.register_handler("dissolve_edges", handle_dissolve_edges)
    dispatcher.register_handler("dissolve_verts", handle_dissolve_verts)
    dispatcher.register_handler("knife_project", handle_knife_project)
    dispatcher.register_handler("spin_mesh", handle_spin_mesh)
    dispatcher.register_handler("set_edge_crease", handle_set_edge_crease)
    dispatcher.register_handler("select_linked", handle_select_linked)
