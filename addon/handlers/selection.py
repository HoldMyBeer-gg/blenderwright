"""Handlers for selecting part of a mesh.

Selection lives on the mesh data as select flags, so it persists once set:
across leaving edit mode, across deselecting the object, and into the saved
.blend. These handlers set those flags, directly where that is deterministic
and via Blender's operators where the logic is Blender's.
"""

import bmesh
import bpy

from .. import dispatcher

_ELEMENT_ATTR = {
    "VERTEX": "vertices",
    "EDGE": "edges",
    "FACE": "polygons",
}

_SELECT_MODE = {"VERTEX": "VERT", "EDGE": "EDGE", "FACE": "FACE"}


def _get_mesh(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{name}' is not a mesh (type: {obj.type})")
    return obj


def _activate(obj):
    """Make obj the active object, in object mode."""
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _counts(obj):
    mesh = obj.data
    return {
        "vertices": {"selected": sum(1 for v in mesh.vertices if v.select),
                     "total": len(mesh.vertices)},
        "edges": {"selected": sum(1 for e in mesh.edges if e.select),
                  "total": len(mesh.edges)},
        "faces": {"selected": sum(1 for p in mesh.polygons if p.select),
                  "total": len(mesh.polygons)},
    }


def handle_select_all_geometry(params):
    """Select, deselect or invert everything."""
    obj = _get_mesh(params["object_name"])
    action = params.get("action", "SELECT")
    _activate(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.mesh.select_all(action=action)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    return {"object_name": obj.name, "action": action, **_counts(obj)}


def handle_select_by_index(params):
    """Set select flags directly. No operator, so nothing can misfire."""
    obj = _get_mesh(params["object_name"])
    element = params["element"]
    indices = params["indices"]
    extend = params.get("extend", False)

    _activate(obj)
    mesh = obj.data
    collection = getattr(mesh, _ELEMENT_ATTR[element])

    out_of_range = [i for i in indices if i >= len(collection)]
    if out_of_range:
        raise ValueError(
            f"{element.lower()} index out of range: {sorted(out_of_range)[:5]}. "
            f"This mesh has {len(collection)}."
        )

    # The select mode must match, or Blender maps the flags on the next mode
    # switch and the selection appears to change on its own.
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type=_SELECT_MODE[element])
    if not extend:
        bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")

    for index in indices:
        collection[index].select = True

    return {
        "object_name": obj.name,
        "element": element,
        "requested": len(indices),
        **_counts(obj),
    }


def handle_select_by_axis(params):
    """Select geometry on one side of the object.

    Two things this needs that are easy to miss, both found by running it:
    select_axis compares against the *active* element, and an element is made
    active through the bmesh select_history, not by setting its select flag.
    And the result lands on vertices, so it must be flushed up to edges and
    faces or a caller asking for "the top" sees no faces selected at all.
    """
    obj = _get_mesh(params["object_name"])
    axis = params.get("axis", "Z")
    sign = params.get("sign", "POS")
    extend = params.get("extend", False)

    _activate(obj)
    mesh = obj.data
    if not mesh.vertices:
        raise ValueError(f"Object '{obj.name}' has no geometry")

    component = "XYZ".index(axis)
    direction = -1 if sign == "NEG" else 1
    index = max(range(len(mesh.vertices)),
                key=lambda i: mesh.vertices[i].co[component] * direction)

    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.mesh.select_mode(type="VERT")
        if not extend:
            bpy.ops.mesh.select_all(action="DESELECT")

        bm = bmesh.from_edit_mesh(mesh)
        bm.verts.ensure_lookup_table()
        seed = bm.verts[index]
        seed.select = True
        bm.select_history.clear()
        bm.select_history.add(seed)
        bmesh.update_edit_mesh(mesh)

        bpy.ops.mesh.select_axis(axis=axis, sign=sign)

        bm = bmesh.from_edit_mesh(mesh)
        bm.select_flush(True)
        bmesh.update_edit_mesh(mesh)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    return {"object_name": obj.name, "axis": axis, "sign": sign, **_counts(obj)}


def handle_select_similar(params):
    """Grow the selection to geometry resembling what is already selected."""
    obj = _get_mesh(params["object_name"])
    similar_type = params.get("type", "FACE_AREA")
    threshold = float(params.get("threshold", 0.0))

    _activate(obj)
    mesh = obj.data
    if not any(v.select for v in mesh.vertices):
        raise ValueError(
            "nothing is selected, and select_similar compares against the "
            "current selection. Select something first, with select_by_index "
            "or select_by_axis."
        )

    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.mesh.select_similar(type=similar_type, threshold=threshold)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    return {"object_name": obj.name, "type": similar_type, **_counts(obj)}


def handle_select_faces_by_sides(params):
    """Select faces by side count: ngons, triangles, quads."""
    obj = _get_mesh(params["object_name"])
    number = int(params.get("number", 4))
    comparison = params.get("comparison", "EQUAL")
    extend = params.get("extend", False)

    _activate(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.mesh.select_mode(type="FACE")
        if not extend:
            bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.mesh.select_face_by_sides(number=number, type=comparison,
                                          extend=True)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    return {
        "object_name": obj.name,
        "number": number,
        "comparison": comparison,
        **_counts(obj),
    }


def handle_get_selection(params):
    """Report what is selected, with sample indices."""
    obj = _get_mesh(params["object_name"])
    mesh = obj.data
    return {
        "object_name": obj.name,
        **_counts(obj),
        "selected_vertex_indices": [v.index for v in mesh.vertices if v.select][:50],
        "selected_edge_indices": [e.index for e in mesh.edges if e.select][:50],
        "selected_face_indices": [p.index for p in mesh.polygons if p.select][:50],
    }


def register():
    dispatcher.register_handler("select_all_geometry", handle_select_all_geometry)
    dispatcher.register_handler("select_by_index", handle_select_by_index)
    dispatcher.register_handler("select_by_axis", handle_select_by_axis)
    dispatcher.register_handler("select_similar", handle_select_similar)
    dispatcher.register_handler("select_faces_by_sides", handle_select_faces_by_sides)
    dispatcher.register_handler("get_selection", handle_get_selection)
