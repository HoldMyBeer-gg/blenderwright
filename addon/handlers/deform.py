"""Blender handlers for vertex groups (weights) and shape keys (blend shapes)."""

import bpy
from mathutils import Vector
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


COLOR_DOMAINS = {"POINT", "CORNER"}
COLOR_TYPES = {"BYTE_COLOR", "FLOAT_COLOR"}


def handle_paint_color_attribute(params):
    obj = _get_mesh(params.get("object_name"))
    if obj.mode != "OBJECT":
        _activate(obj)  # edit-mode data would overwrite the paint on exit
    mesh = obj.data
    if params.get("vertex_indices") is not None:
        chosen = set(_check_indices(obj, list(params["vertex_indices"])))
    elif params.get("selection", "ALL") == "CURRENT":
        chosen = {v.index for v in mesh.vertices if v.select}
    else:
        chosen = None

    attrs = mesh.color_attributes
    name = params.get("attribute_name", "Color")
    attr = attrs.get(name)
    created = attr is None
    if created:
        domain = params.get("domain", "CORNER")
        data_type = params.get("data_type", "BYTE_COLOR")
        if domain not in COLOR_DOMAINS or data_type not in COLOR_TYPES:
            raise ValueError(f"Unknown domain {domain!r} or data_type {data_type!r}")
        attr = attrs.new(name, data_type, domain)

    if attr.domain == "POINT":
        targets = range(len(attr.data)) if chosen is None else sorted(chosen)
    else:
        targets = [lp.index for lp in mesh.loops if chosen is None or lp.vertex_index in chosen]
    color = tuple(float(c) for c in params["color"])
    for i in targets:
        attr.data[i].color = color

    attrs.active_color = attr
    attrs.render_color_index = attrs.active_color_index
    return {"attribute": attr.name, "domain": attr.domain, "data_type": attr.data_type,
            "created": created, "painted": len(targets),
            "color_attributes": [a.name for a in attrs]}


def handle_remove_color_attribute(params):
    obj = _get_mesh(params.get("object_name"))
    name = params.get("attribute_name")
    attrs = obj.data.color_attributes
    attr = attrs.get(name)
    if attr is None:
        raise ValueError(f"'{obj.name}' has no color attribute '{name}'; "
                         f"it has {[a.name for a in attrs]}")
    attrs.remove(attr)
    return {"removed": name, "color_attributes": [a.name for a in attrs]}


LATTICE_INTERPOLATIONS = {"KEY_LINEAR", "KEY_CARDINAL", "KEY_CATMULL_ROM", "KEY_BSPLINE"}


def _world_bounds(obj):
    bpy.context.view_layer.update()  # matrix_world is stale after a transform
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return ([min(c[i] for c in corners) for i in range(3)],
            [max(c[i] for c in corners) for i in range(3)])


def _span(values):
    return max(values) - min(values)


def handle_create_lattice(params):
    obj = bpy.data.objects.get(params.get("object_name"))
    if obj is None:
        raise ValueError(f"Object '{params.get('object_name')}' not found")
    if not hasattr(obj, "modifiers") or obj.type == "LATTICE":
        raise ValueError(f"'{obj.name}' cannot be deformed by a lattice")
    interpolation = params.get("interpolation", "KEY_LINEAR")
    if interpolation not in LATTICE_INTERPOLATIONS:
        raise ValueError(f"Unknown interpolation {interpolation!r}")
    u, v, w = (int(n) for n in params.get("resolution", (2, 2, 2)))
    name = params.get("lattice_name") or f"{obj.name} Lattice"

    low, high = _world_bounds(obj)
    data = bpy.data.lattices.new(name)
    data.points_u, data.points_v, data.points_w = u, v, w
    data.interpolation_type_u = data.interpolation_type_v = interpolation
    data.interpolation_type_w = interpolation
    cage = bpy.data.objects.new(name, data)
    (obj.users_collection[0] if obj.users_collection
     else bpy.context.scene.collection).objects.link(cage)
    # Points sit in lattice space; size the object so they land on the bounds
    cage.location = [(a + b) / 2 for a, b in zip(low, high)]
    cage.scale = [max(b - a, 1e-4) / (_span([p.co[i] for p in data.points]) or 1.0)
                  for i, (a, b) in enumerate(zip(low, high))]
    modifier = obj.modifiers.new(name="Lattice", type="LATTICE")
    modifier.object = cage
    bpy.context.view_layer.update()
    return {"lattice": cage.name, "points": len(data.points), "modifier": modifier.name,
            "object": obj.name}


def handle_move_lattice_points(params):
    from .selection import _on_side

    cage = bpy.data.objects.get(params.get("lattice_name"))
    if cage is None or cage.type != "LATTICE":
        raise ValueError(f"No lattice object '{params.get('lattice_name')}'")
    points = cage.data.points
    if params.get("reset"):
        for point in points:
            point.co_deform = point.co
        bpy.context.view_layer.update()
        return {"lattice": cage.name, "moved": len(points), "points": len(points)}

    if params.get("point_indices") is not None:
        indices = list(params["point_indices"])
        bad = [i for i in indices if not 0 <= i < len(points)]
        if bad:
            raise ValueError(f"Point index {bad[0]} is out of range (0 to {len(points) - 1})")
    elif params.get("axis"):
        component = "XYZ".index(params["axis"])
        chosen = _on_side([p.co[component] for p in points], params.get("sign", "POS"))
        indices = [i for i, picked in enumerate(chosen) if picked]
    else:
        indices = list(range(len(points)))

    centre = [(min(p.co[i] for p in points) + max(p.co[i] for p in points)) / 2
              for i in range(3)]
    scale = params.get("scale") or (1.0, 1.0, 1.0)
    # The offset is in world units; points live in lattice space
    bpy.context.view_layer.update()
    offset = cage.matrix_world.inverted().to_3x3() @ Vector(params.get("offset") or (0, 0, 0))
    for i in indices:
        current = points[i].co_deform
        points[i].co_deform = [centre[a] + (current[a] - centre[a]) * scale[a] + offset[a]
                               for a in range(3)]
    bpy.context.view_layer.update()
    return {"lattice": cage.name, "moved": len(indices), "points": len(points)}


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
    dispatcher.register_handler("paint_color_attribute", handle_paint_color_attribute)
    dispatcher.register_handler("create_lattice", handle_create_lattice)
    dispatcher.register_handler("move_lattice_points", handle_move_lattice_points)
    dispatcher.register_handler("remove_color_attribute", handle_remove_color_attribute)
