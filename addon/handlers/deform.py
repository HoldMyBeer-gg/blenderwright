"""Blender handlers for vertex groups (weights) and shape keys (blend shapes)."""

import bpy
from .. import dispatcher

ASSIGN_MODES = {"REPLACE", "ADD", "SUBTRACT", "REMOVE"}

# Operation -> (operator name, tool parameter -> operator keyword, fixed keywords)
GROUP_OPERATIONS = {
    "NORMALIZE": ("vertex_group_normalize", {}, {}),
    "NORMALIZE_ALL": ("vertex_group_normalize_all", {},
                      {"group_select_mode": "ALL", "lock_active": False}),
    "INVERT": ("vertex_group_invert", {}, {"group_select_mode": "ACTIVE"}),
    "CLEAN": ("vertex_group_clean", {"threshold": "limit"}, {"group_select_mode": "ACTIVE"}),
    "SMOOTH": ("vertex_group_smooth", {"factor": "factor", "repeat": "repeat"},
               {"group_select_mode": "ACTIVE"}),
    "LEVELS": ("vertex_group_levels", {"offset": "offset", "gain": "gain"},
               {"group_select_mode": "ACTIVE"}),
    "LIMIT_TOTAL": ("vertex_group_limit_total", {"max_groups": "limit"},
                    {"group_select_mode": "ALL"}),
    "MIRROR": ("vertex_group_mirror", {}, {}),
    "QUANTIZE": ("vertex_group_quantize", {"steps": "steps"}, {"group_select_mode": "ACTIVE"}),
}


def _get_mesh(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{name}' is not a mesh (type: {obj.type})")
    return obj


def _get_group(obj, name):
    vg = obj.vertex_groups.get(name)
    if vg is None:
        raise ValueError(f"'{obj.name}' has no vertex group '{name}'")
    return vg


def _activate(obj):
    """Make obj the only selected, active object, in object mode."""
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for other in bpy.context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _check_indices(obj, indices):
    count = len(obj.data.vertices)
    bad = [i for i in indices if not 0 <= i < count]
    if bad:
        raise ValueError(f"Vertex index {bad[0]} is out of range; '{obj.name}' has "
                         f"{count} vertices (0 to {count - 1})")
    return indices


def _weights(obj, vg):
    """Weights of the vertices in a group, by vertex index."""
    out = {}
    for v in obj.data.vertices:
        try:
            out[v.index] = vg.weight(v.index)
        except RuntimeError:
            continue
    return out


def _group_summary(obj, vg):
    weights = list(_weights(obj, vg).values())
    return {
        "name": vg.name,
        "index": vg.index,
        "vertex_count": len(weights),
        "min_weight": round(min(weights), 4) if weights else None,
        "max_weight": round(max(weights), 4) if weights else None,
    }


def handle_assign_vertex_group(params):
    obj = _get_mesh(params.get("object_name"))
    mode = params.get("mode", "REPLACE")
    if mode not in ASSIGN_MODES:
        raise ValueError(f"Unknown mode {mode!r}; use one of {sorted(ASSIGN_MODES)}")
    if obj.mode != "OBJECT":
        _activate(obj)  # weights cannot change in edit mode, and selection syncs on exit

    if params.get("vertex_indices") is not None:
        indices = _check_indices(obj, list(params["vertex_indices"]))
    elif params.get("selection", "ALL") == "CURRENT":
        indices = [v.index for v in obj.data.vertices if v.select]
    else:
        indices = [v.index for v in obj.data.vertices]

    name = params.get("group_name")
    vg = obj.vertex_groups.get(name)
    created = vg is None
    if created:
        vg = obj.vertex_groups.new(name=name)
    if mode == "REMOVE":
        vg.remove(indices)
    else:
        vg.add(indices, float(params.get("weight", 1.0)), mode)
    obj.vertex_groups.active_index = vg.index
    return {"group": vg.name, "index": vg.index, "created": created, "changed": len(indices),
            "vertex_count": _group_summary(obj, vg)["vertex_count"]}


def handle_list_vertex_groups(params):
    obj = _get_mesh(params.get("object_name"))
    return {"groups": [_group_summary(obj, vg) for vg in obj.vertex_groups]}


def handle_remove_vertex_group(params):
    obj = _get_mesh(params.get("object_name"))
    vg = _get_group(obj, params.get("group_name"))
    name = vg.name
    obj.vertex_groups.remove(vg)
    return {"removed": name, "groups": [g.name for g in obj.vertex_groups]}


def handle_vertex_group_operation(params):
    obj = _get_mesh(params.get("object_name"))
    operation = params.get("operation")
    spec = GROUP_OPERATIONS.get(operation)
    if spec is None:
        raise ValueError(f"Unknown vertex group operation {operation!r}")
    op_name, mapping, fixed = spec
    vg = _get_group(obj, params.get("group_name"))
    _activate(obj)
    obj.vertex_groups.active_index = vg.index
    kwargs = {op_kw: params[key] for key, op_kw in mapping.items() if key in params}
    kwargs.update(fixed)

    operator = getattr(bpy.ops.object, op_name)
    if operation == "SMOOTH":
        # Smooth only runs in edit or weight paint mode, on selected vertices
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        try:
            result = operator(**kwargs)
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
    else:
        result = operator(**kwargs)
    if result != {"FINISHED"}:
        raise RuntimeError(f"{op_name} did not finish: {result}")
    return {"operation": operation, **_group_summary(obj, vg)}


def _key_blocks(obj):
    keys = obj.data.shape_keys
    return keys.key_blocks if keys is not None else []


def _get_key(obj, name):
    kb = next((k for k in _key_blocks(obj) if k.name == name), None)
    if kb is None:
        raise ValueError(f"'{obj.name}' has no shape key '{name}'")
    return kb


def _key_names(obj):
    return [k.name for k in _key_blocks(obj)]


def handle_add_shape_key(params):
    obj = _get_mesh(params.get("object_name"))
    name = params.get("key_name")
    if name in _key_names(obj):
        raise ValueError(f"'{obj.name}' already has a shape key '{name}'")
    if obj.mode != "OBJECT":
        _activate(obj)
    if not _key_names(obj):
        obj.shape_key_add(name="Basis", from_mix=False)
    kb = obj.shape_key_add(name=name, from_mix=bool(params.get("from_mix", False)))
    return {"key": kb.name, "keys": _key_names(obj)}


def _check_in_slider(kb, value):
    if not kb.slider_min <= value <= kb.slider_max:
        raise ValueError(f"Value {value} is outside the slider range "
                         f"{kb.slider_min} to {kb.slider_max}; widen it with slider_min/max")


def _key_summary(kb):
    return {
        "name": kb.name, "value": kb.value, "slider_min": kb.slider_min,
        "slider_max": kb.slider_max, "mute": kb.mute, "vertex_group": kb.vertex_group,
        "relative_key": kb.relative_key.name if kb.relative_key is not None else None,
    }


def handle_set_shape_key(params):
    obj = _get_mesh(params.get("object_name"))
    kb = _get_key(obj, params.get("key_name"))
    if "slider_min" in params:
        kb.slider_min = params["slider_min"]
    if "slider_max" in params:
        kb.slider_max = params["slider_max"]
    if "value" in params:
        _check_in_slider(kb, params["value"])
        kb.value = params["value"]
    if "mute" in params:
        kb.mute = params["mute"]
    if "vertex_group" in params:
        group = params["vertex_group"]
        if group:
            _get_group(obj, group)
        kb.vertex_group = group
    if params.get("relative_key"):
        kb.relative_key = _get_key(obj, params["relative_key"])
    return _key_summary(kb)


def handle_move_shape_key_vertices(params):
    obj = _get_mesh(params.get("object_name"))
    kb = _get_key(obj, params.get("key_name"))
    # Compare by name: Blender returns a new wrapper object on every access
    if kb.name == obj.data.shape_keys.reference_key.name:
        raise ValueError(f"'{kb.name}' is the Basis; move vertices in another shape key")
    if obj.mode != "OBJECT":
        _activate(obj)  # edit mode would overwrite the key on exit
    dx, dy, dz = (float(v) for v in params.get("offset", (0, 0, 0)))

    if params.get("vertex_indices") is not None:
        factors = {i: 1.0 for i in _check_indices(obj, list(params["vertex_indices"]))}
    elif params.get("vertex_group"):
        factors = _weights(obj, _get_group(obj, params["vertex_group"]))
    else:
        factors = {i: 1.0 for i in range(len(kb.data))}

    moved = 0
    for i, f in factors.items():
        if f == 0.0:
            continue
        co = kb.data[i].co
        co[0] += dx * f
        co[1] += dy * f
        co[2] += dz * f
        moved += 1
    return {"key": kb.name, "moved": moved}


def handle_list_shape_keys(params):
    obj = _get_mesh(params.get("object_name"))
    keys = obj.data.shape_keys
    if keys is None:
        return {"reference": None, "keys": []}
    ref = keys.reference_key
    return {"reference": ref.name if ref is not None else None,
            "keys": [_key_summary(kb) for kb in keys.key_blocks]}


def handle_remove_shape_key(params):
    obj = _get_mesh(params.get("object_name"))
    kb = _get_key(obj, params.get("key_name"))
    name = kb.name
    obj.shape_key_remove(kb)
    return {"removed": name, "keys": _key_names(obj)}


def handle_keyframe_shape_key(params):
    obj = _get_mesh(params.get("object_name"))
    kb = _get_key(obj, params.get("key_name"))
    if "value" in params:
        _check_in_slider(kb, params["value"])
        kb.value = params["value"]
    frame = int(params["frame"])
    if not kb.keyframe_insert("value", frame=frame):
        raise RuntimeError(f"Could not keyframe shape key '{kb.name}'")
    return {"key": kb.name, "frame": frame, "value": kb.value}


def register():
    dispatcher.register_handler("assign_vertex_group", handle_assign_vertex_group)
    dispatcher.register_handler("list_vertex_groups", handle_list_vertex_groups)
    dispatcher.register_handler("remove_vertex_group", handle_remove_vertex_group)
    dispatcher.register_handler("vertex_group_operation", handle_vertex_group_operation)
    dispatcher.register_handler("add_shape_key", handle_add_shape_key)
    dispatcher.register_handler("set_shape_key", handle_set_shape_key)
    dispatcher.register_handler("move_shape_key_vertices", handle_move_shape_key_vertices)
    dispatcher.register_handler("list_shape_keys", handle_list_shape_keys)
    dispatcher.register_handler("remove_shape_key", handle_remove_shape_key)
    dispatcher.register_handler("keyframe_shape_key", handle_keyframe_shape_key)
