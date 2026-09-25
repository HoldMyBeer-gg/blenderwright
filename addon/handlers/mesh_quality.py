"""Blender addon handler for mesh quality analysis."""

import bpy
import bmesh
from .. import dispatcher

AREA_EPSILON = 1e-8
VERT_DIST = 1e-4
MAX_SAMPLE_INDICES = 50


def handle_analyze_mesh_quality(params: dict) -> dict:
    """Analyze mesh topology quality and return structured defect report.

    Args:
        params: Dict with key 'object_name' specifying the mesh object to analyze.

    Returns:
        Dict with vertex/edge/face counts, defect counts and sample indices,
        and an issues_found boolean.
    """
    object_name = params.get("object_name", "")
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object '{object_name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{object_name}' is not a mesh (type: {obj.type})")

    # Ensure object mode so mesh data is current
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        non_manifold_edges = [e.index for e in bm.edges if not e.is_manifold and not e.is_wire]
        wire_edges = [e.index for e in bm.edges if e.is_wire]
        loose_verts = [v.index for v in bm.verts if not v.link_faces]
        zero_area_faces = [f.index for f in bm.faces if f.calc_area() < AREA_EPSILON]

        dup_result = bmesh.ops.find_doubles(bm, verts=list(bm.verts), dist=VERT_DIST)
        duplicate_vert_count = len(dup_result["targetmap"])

        return {
            "object": obj.name,
            "vertex_count": len(bm.verts),
            "edge_count": len(bm.edges),
            "face_count": len(bm.faces),
            "non_manifold_edge_count": len(non_manifold_edges),
            "non_manifold_edge_indices": non_manifold_edges[:MAX_SAMPLE_INDICES],
            "wire_edge_count": len(wire_edges),
            "loose_vertex_count": len(loose_verts),
            "loose_vertex_indices": loose_verts[:MAX_SAMPLE_INDICES],
            "zero_area_face_count": len(zero_area_faces),
            "zero_area_face_indices": zero_area_faces[:MAX_SAMPLE_INDICES],
            "duplicate_vertex_count": duplicate_vert_count,
            "issues_found": bool(
                non_manifold_edges or loose_verts
                or zero_area_faces or duplicate_vert_count
            ),
        }
    finally:
        bm.free()


def _counts(obj):
    """Vertex, edge and face totals, for reporting the effect of a repair."""
    mesh = obj.data
    return {
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "faces": len(mesh.polygons),
    }


def handle_repair_mesh(params: dict) -> dict:
    """Remove loose geometry, dissolve degenerate faces, and close holes."""
    object_name = params.get("object_name")
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object '{object_name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{object_name}' is not a mesh (type: {obj.type})")

    before = _counts(obj)
    applied = []

    if obj.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.mesh.select_all(action="SELECT")
        if params.get("remove_loose", True):
            bpy.ops.mesh.delete_loose()
            applied.append("remove_loose")
        if params.get("dissolve_degenerate", True):
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.dissolve_degenerate()
            applied.append("dissolve_degenerate")
        if params.get("fill_holes", False):
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.fill_holes(sides=0)
            applied.append("fill_holes")
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    after = _counts(obj)
    return {
        "object_name": obj.name,
        "repairs_applied": applied,
        "before": before,
        "after": after,
        "removed": {k: before[k] - after[k] for k in before},
    }


def handle_decimate_mesh(params: dict) -> dict:
    """Reduce the polygon count with a Decimate modifier, then apply it."""
    object_name = params.get("object_name")
    ratio = float(params.get("ratio", 0.5))
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object '{object_name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{object_name}' is not a mesh (type: {obj.type})")

    before = _counts(obj)

    if obj.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    mod = obj.modifiers.new(name="Decimate", type="DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    bpy.ops.object.modifier_apply(modifier=mod.name)

    after = _counts(obj)
    return {
        "object_name": obj.name,
        "ratio": ratio,
        "before": before,
        "after": after,
    }


dispatcher.register_handler("analyze_mesh_quality", handle_analyze_mesh_quality)
dispatcher.register_handler("repair_mesh", handle_repair_mesh)
dispatcher.register_handler("decimate_mesh", handle_decimate_mesh)
