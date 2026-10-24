"""Blender handlers for animation operations."""

import re

import bpy
from bpy_extras import anim_utils
from .. import dispatcher

# Driver safety, mirroring blenderwright.validators: Blender's simple-expression
# subset only, so no driver can ever need Python to evaluate
DRIVER_FUNCTIONS = frozenset({
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sqrt", "abs", "fabs", "floor",
    "ceil", "trunc", "round", "int", "min", "max", "radians", "degrees", "exp", "log", "pow",
    "fmod", "lerp", "clamp", "smoothstep",
})
DRIVER_WORDS = frozenset({"frame", "pi", "True", "False", "and", "or", "not", "if", "else"})
_DRIVER_TOKEN = re.compile(
    r" +|(?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<op>==|!=|<=|>=|//|[-+*/%(),<>])"
)
_PATH_SEGMENT = r"(?!__)[A-Za-z_][A-Za-z0-9_]*"
DATA_PATH_PATTERN = re.compile(
    rf'^{_PATH_SEGMENT}(?:\.{_PATH_SEGMENT}|\["[A-Za-z0-9_ .\-]{{1,63}}"\])*$')
DRIVER_TYPES = {"SCRIPTED", "AVERAGE", "SUM", "MIN", "MAX"}


def _get_object(name):
    """Get a Blender object by name, raising if not found."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    return obj


def _action_fcurves(obj):
    """F-curves in the object's assigned action slot, or [] if it has none."""
    adt = obj.animation_data
    channelbag = anim_utils.action_get_channelbag_for_slot(adt.action, adt.action_slot)
    return channelbag.fcurves if channelbag is not None else []


def _parse_data_path(data_path):
    """Parse a data_path like 'location[0]' into (base_path, index).

    Returns:
        Tuple of (base_path, index) where index is None for full-vector paths.
    """
    if "[" in data_path and data_path.endswith("]"):
        bracket_pos = data_path.index("[")
        base = data_path[:bracket_pos]
        index = int(data_path[bracket_pos + 1:-1])
        return base, index
    return data_path, None


def handle_insert_keyframe(params):
    """Insert a keyframe on an object property."""
    obj = _get_object(params["object_name"])
    data_path = params["data_path"]
    frame = params["frame"]
    value = params.get("value")

    base_path, index = _parse_data_path(data_path)

    # Set value if provided
    if value is not None:
        prop = getattr(obj, base_path)
        if index is not None:
            prop[index] = value
        else:
            if isinstance(value, (list, tuple)):
                for i, v in enumerate(value):
                    prop[i] = v
            else:
                setattr(obj, base_path, value)

    # Insert keyframe
    if index is not None:
        obj.keyframe_insert(data_path=base_path, index=index, frame=frame)
    else:
        obj.keyframe_insert(data_path=base_path, frame=frame)

    return {
        "object": obj.name,
        "data_path": data_path,
        "frame": frame,
    }


def handle_delete_keyframe(params):
    """Delete a keyframe from an object property."""
    obj = _get_object(params["object_name"])
    data_path = params["data_path"]
    frame = params["frame"]

    base_path, index = _parse_data_path(data_path)

    bpy.context.scene.frame_set(frame)

    if index is not None:
        obj.keyframe_delete(data_path=base_path, index=index, frame=frame)
    else:
        obj.keyframe_delete(data_path=base_path, frame=frame)

    return {
        "object": obj.name,
        "data_path": data_path,
        "frame": frame,
    }


def handle_set_frame(params):
    """Set the current frame."""
    frame = params["frame"]
    bpy.context.scene.frame_set(frame)
    return {"frame": bpy.context.scene.frame_current}


def handle_set_frame_range(params):
    """Set the start and end frames."""
    start = params["start"]
    end = params["end"]

    bpy.context.scene.frame_start = start
    bpy.context.scene.frame_end = end

    return {
        "frame_start": bpy.context.scene.frame_start,
        "frame_end": bpy.context.scene.frame_end,
    }


def handle_set_interpolation(params):
    """Set interpolation type for keyframes on a property."""
    obj = _get_object(params["object_name"])
    data_path = params["data_path"]
    interpolation = params.get("interpolation", "BEZIER")

    base_path, index = _parse_data_path(data_path)

    if obj.animation_data is None or obj.animation_data.action is None:
        raise ValueError(f"Object '{obj.name}' has no animation data")

    changed = 0

    for fcurve in _action_fcurves(obj):
        if fcurve.data_path == base_path:
            if index is not None and fcurve.array_index != index:
                continue
            for keyframe_point in fcurve.keyframe_points:
                keyframe_point.interpolation = interpolation
                changed += 1

    if changed == 0:
        raise ValueError(
            f"No keyframes found for data_path '{data_path}' on '{obj.name}'"
        )

    return {
        "object": obj.name,
        "data_path": data_path,
        "interpolation": interpolation,
        "keyframes_updated": changed,
    }


def handle_create_animation_path(params):
    """Create a Follow Path constraint on an object."""
    obj = _get_object(params["object_name"])
    path_obj = _get_object(params["path_object"])

    if path_obj.type != "CURVE":
        raise ValueError(f"Path object '{path_obj.name}' is not a curve")

    constraint = obj.constraints.new(type="FOLLOW_PATH")
    constraint.target = path_obj
    constraint.use_curve_follow = True

    # Animate the offset to move along the path
    path_obj.data.use_path = True

    return {
        "object": obj.name,
        "path_object": path_obj.name,
        "constraint": constraint.name,
    }


def handle_list_keyframes(params):
    """List all keyframes on an object."""
    obj = _get_object(params["object_name"])

    if obj.animation_data is None or obj.animation_data.action is None:
        return []

    keyframes = []

    for fcurve in _action_fcurves(obj):
        data_path = fcurve.data_path
        array_index = fcurve.array_index

        for kp in fcurve.keyframe_points:
            keyframes.append({
                "data_path": data_path,
                "array_index": array_index,
                "frame": kp.co[0],
                "value": kp.co[1],
                "interpolation": kp.interpolation,
            })

    # Sort by frame
    keyframes.sort(key=lambda k: k["frame"])
    return keyframes


def handle_clear_animation(params):
    """Remove all animation data from an object."""
    obj = _get_object(params["object_name"])

    if obj.animation_data is not None:
        obj.animation_data_clear()

    return {"object": obj.name, "cleared": True}


def _check_expression(expression, names):
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 256 \
            or "**" in expression.replace(" ", ""):
        raise ValueError("Driver expression must be a short simple expression")
    pos = 0
    while pos < len(expression):
        match = _DRIVER_TOKEN.match(expression, pos)
        if match is None or match.end() == pos:
            raise ValueError(f"Driver expression has {expression[pos]!r}, which simple "
                             f"expressions do not allow")
        name = match.group("name")
        if name is not None and name not in names and name not in DRIVER_FUNCTIONS \
                and name not in DRIVER_WORDS:
            raise ValueError(f"Driver expression uses unknown name {name!r}")
        pos = match.end()


def _check_path(path):
    if not isinstance(path, str) or len(path) > 256 or not DATA_PATH_PATTERN.match(path):
        raise ValueError(f"Not a property path: {path!r}")
    return path


_PATH_PIECE = re.compile(r'(?:^|\.)([A-Za-z_][A-Za-z0-9_]*)|(\["[^"]*"\])')


def _driver_owner(obj, path):
    """The data block that owns the property, and the path relative to it.

    driver_add refuses paths that cross into another data block, so
    "data.energy" on a light object becomes "energy" on its Light data.
    A data block is its own id_data; a nested struct is not.
    """
    pieces = [m.group(1) or m.group(2) for m in _PATH_PIECE.finditer(path)]
    owner, start = obj, 0
    for i in range(len(pieces) - 1):
        prefix = _join_path(pieces[start:i + 1])
        try:
            value = owner.path_resolve(prefix, False)
        except ValueError:
            break
        if getattr(value, "id_data", None) is value:
            owner, start = value, i + 1
    return owner, _join_path(pieces[start:])


def _join_path(pieces):
    out = ""
    for piece in pieces:
        out += piece if piece.startswith("[") or not out else "." + piece
    return out


def _variable_objects(variables):
    """Look up every object a variable names before anything is created."""
    found = {}
    for var in variables:
        for key in ("object", "object_2"):
            name = var.get(key)
            if name and name not in found:
                obj = bpy.data.objects.get(name)
                if obj is None:
                    raise ValueError(f"Driver variable object '{name}' not found")
                found[name] = obj
        if var.get("type") == "SINGLE_PROP":
            _check_path(var.get("data_path"))
    return found


def _fill_variable(driver, var, objects):
    v = driver.variables.new()
    v.name = var["name"]
    v.type = var["type"]
    target = v.targets[0]
    if var["type"] == "TRANSFORMS":
        target.id = objects[var["object"]]
        target.transform_type = var.get("transform_type", "LOC_X")
        target.transform_space = var.get("transform_space", "WORLD_SPACE")
    elif var["type"] == "SINGLE_PROP":
        target.id_type = "OBJECT"
        target.id = objects[var["object"]]
        target.data_path = var["data_path"]
    else:
        target.id = objects[var["object"]]
        v.targets[1].id = objects[var["object_2"]]


def handle_add_driver(params):
    """Add a driver using only Blender's simple, Python-free expressions."""
    obj = _get_object(params["object_name"])
    path = _check_path(params["data_path"])
    index = int(params.get("index", -1))
    driver_type = params.get("driver_type", "SCRIPTED")
    if driver_type not in DRIVER_TYPES:
        raise ValueError(f"Unknown driver type {driver_type!r}")
    variables = list(params.get("variables", []))
    names = {v.get("name") for v in variables}
    expression = params.get("expression", "")
    if driver_type == "SCRIPTED":
        _check_expression(expression, names)
    objects = _variable_objects(variables)
    try:
        obj.path_resolve(path)
    except ValueError:
        raise ValueError(f"'{obj.name}' has no property '{path}'") from None

    owner, owner_path = _driver_owner(obj, path)
    added = owner.driver_add(owner_path, index)
    curves = added if isinstance(added, list) else [added]
    try:
        for fcurve in curves:
            driver = fcurve.driver
            driver.type = driver_type
            for var in variables:
                _fill_variable(driver, var, objects)
            if driver_type == "SCRIPTED":
                driver.expression = expression
                # Blender's own verdict: a non-simple expression would need Python
                if not driver.is_simple_expression:
                    raise ValueError(f"'{expression}' is not a simple expression; "
                                     f"Blender would need Python to run it")
    except Exception:
        owner.driver_remove(owner_path, index)
        raise
    return {"object": obj.name, "owner": owner.name, "data_path": path, "index": index,
            "driver_type": driver_type, "expression": expression,
            "variables": [v["name"] for v in variables], "drivers_added": len(curves)}


def handle_remove_driver(params):
    obj = _get_object(params["object_name"])
    path = _check_path(params["data_path"])
    owner, owner_path = _driver_owner(obj, path)
    removed = owner.driver_remove(owner_path, int(params.get("index", -1)))
    return {"object": obj.name, "data_path": path, "removed": bool(removed)}


def handle_list_drivers(params):
    """Drivers on the object and on the data blocks it uses (its data, shape keys)."""
    obj = _get_object(params["object_name"])
    owners = [("", obj)]
    data = getattr(obj, "data", None)
    if data is not None and getattr(data, "id_data", None) is data:
        owners.append(("data.", data))
        keys = getattr(data, "shape_keys", None)
        if keys is not None:
            owners.append(("data.shape_keys.", keys))
    drivers = []
    for prefix, owner in owners:
        adt = getattr(owner, "animation_data", None)
        for fcurve in (adt.drivers if adt is not None else []):
            d = fcurve.driver
            drivers.append({
                "data_path": prefix + fcurve.data_path, "index": fcurve.array_index,
                "type": d.type, "expression": d.expression if d.type == "SCRIPTED" else "",
                "valid": d.is_valid,
                "variables": [{"name": v.name, "type": v.type} for v in d.variables],
            })
    return {"object": obj.name, "drivers": drivers}


KEYFRAME_TARGETS = {"OBJECT", "WORLD", "SCENE"}


def _keyframe_root(params):
    target = params.get("target", "OBJECT")
    if target not in KEYFRAME_TARGETS:
        raise ValueError(f"Unknown keyframe target {target!r}")
    if target == "OBJECT":
        return _get_object(params.get("object_name"))
    scene = bpy.context.scene
    if target == "SCENE":
        return scene
    if scene.world is None:
        raise ValueError("The scene has no world to keyframe")
    return scene.world


def _set_by_path(owner, path, value, index):
    """Assign through an RNA path: resolve the container, set the last piece."""
    pieces = [m.group(1) or m.group(2) for m in _PATH_PIECE.finditer(path)]
    container_path, last = _join_path(pieces[:-1]), pieces[-1]
    container = owner.path_resolve(container_path, False) if container_path else owner
    if last.startswith("["):
        container[last[2:-2]] = value
    elif index >= 0:
        getattr(container, last)[index] = value
    else:
        setattr(container, last, value)


def _plain(value):
    return list(value) if hasattr(value, "__len__") and not isinstance(value, str) else value


def handle_keyframe_property(params):
    """Keyframe any animatable property, on whichever data block owns it."""
    root = _keyframe_root(params)
    path = _check_path(params.get("data_path"))
    frame = int(params["frame"])
    index = int(params.get("index", -1))
    try:
        root.path_resolve(path, False)
    except ValueError:
        raise ValueError(f"'{root.name}' has no property '{path}'") from None
    owner, owner_path = _driver_owner(root, path)
    if "value" in params:
        _set_by_path(owner, owner_path, params["value"], index)
    try:
        keyed = owner.keyframe_insert(owner_path, index=index, frame=frame)
    except TypeError:
        keyed = False
    if not keyed:
        raise ValueError(f"'{path}' cannot be animated; Blender does not allow keyframes "
                         f"on it")
    return {"owner": owner.name, "data_path": owner_path, "frame": frame, "index": index,
            "value": _plain(owner.path_resolve(owner_path, False))}


ACTION_OPERATIONS = {"LIST", "NEW", "ASSIGN", "UNASSIGN", "PUSH_DOWN"}
NLA_BLEND_TYPES = {"REPLACE", "COMBINE", "ADD", "SUBTRACT", "MULTIPLY"}
NLA_EXTRAPOLATIONS = {"NOTHING", "HOLD", "HOLD_FORWARD"}
FCURVE_MODIFIERS = {"CYCLES", "NOISE", "STEPPED", "SMOOTH"}
SETTABLE_RNA_TYPES = {"BOOLEAN", "INT", "FLOAT", "ENUM", "STRING"}


def _get_action(name):
    action = bpy.data.actions.get(name)
    if action is None:
        raise ValueError(f"Action '{name}' not found")
    return action


def _slot_for(action, obj):
    """The action's slot for this object: its own by name, else the first
    object slot (so several objects can share one action), else a new one."""
    own = "OB" + obj.name
    for slot in action.slots:
        if slot.identifier == own:
            return slot
    for slot in action.slots:
        if getattr(slot, "id_type", "OBJECT") == "OBJECT":
            return slot
    return action.slots.new(id_type="OBJECT", name=obj.name)


def _action_summary(obj):
    adt = obj.animation_data
    action = adt.action if adt is not None else None
    slot = adt.action_slot if adt is not None and action is not None else None
    return {"object": obj.name, "action": action.name if action else None,
            "slot": slot.identifier if slot else None,
            "actions": sorted(a for a in bpy.data.actions.keys())}


def handle_manage_action(params):
    obj = _get_object(params["object_name"])
    operation = params.get("operation")
    if operation not in ACTION_OPERATIONS:
        raise ValueError(f"Unknown action operation {operation!r}")
    if operation == "LIST":
        return _action_summary(obj)
    adt = obj.animation_data or obj.animation_data_create()
    if operation == "NEW":
        name = params["action_name"]
        if bpy.data.actions.get(name) is not None:
            raise ValueError(f"An action named '{name}' already exists; ASSIGN it instead")
        adt.action = bpy.data.actions.new(name)
    elif operation == "ASSIGN":
        action = _get_action(params["action_name"])
        adt.action = action
        adt.action_slot = _slot_for(action, obj)
    elif operation == "UNASSIGN":
        adt.action = None
    else:  # PUSH_DOWN
        action = adt.action
        if action is None:
            raise ValueError(f"'{obj.name}' has no active action to push down")
        slot = adt.action_slot or _slot_for(action, obj)
        track = adt.nla_tracks.new()
        strip = track.strips.new(action.name, int(action.frame_range[0]), action)
        strip.action_slot = slot
        adt.action = None
    return _action_summary(obj)


def _strip_summary(strip):
    return {"name": strip.name, "action": strip.action.name if strip.action else None,
            "frame_start": strip.frame_start, "frame_end": strip.frame_end,
            "blend_type": strip.blend_type, "repeat": strip.repeat, "scale": strip.scale,
            "extrapolation": strip.extrapolation}


def handle_add_nla_strip(params):
    obj = _get_object(params["object_name"])
    blend = params.get("blend_type", "REPLACE")
    extrapolation = params.get("extrapolation", "HOLD_FORWARD")
    if blend not in NLA_BLEND_TYPES or extrapolation not in NLA_EXTRAPOLATIONS:
        raise ValueError("Unknown blend type or extrapolation")
    action = _get_action(params["action_name"])
    adt = obj.animation_data or obj.animation_data_create()
    name = params.get("track_name", "")
    track = next((t for t in adt.nla_tracks if t.name == name), None) if name else None
    if track is None:
        track = adt.nla_tracks.new()
        if name:
            track.name = name
    strip = track.strips.new(action.name, int(params.get("frame_start", 1)), action)
    strip.action_slot = _slot_for(action, obj)
    strip.blend_type = blend
    strip.extrapolation = extrapolation
    strip.scale = float(params.get("scale", 1.0))
    strip.repeat = float(params.get("repeat", 1.0))
    strip.blend_in = float(params.get("blend_in", 0.0))
    strip.blend_out = float(params.get("blend_out", 0.0))
    if "influence" in params:
        # A fixed influence needs use_animated_influence, which creates an
        # influence F-curve keyed at the current value; that curve then wins,
        # so the value goes into its keys
        value = float(params["influence"])
        strip.use_animated_influence = True
        strip.influence = value
        curve = strip.fcurves.find("influence")
        if curve is not None:
            for point in curve.keyframe_points:
                point.co[1] = value
    return {"object": obj.name, "track": track.name, **_strip_summary(strip)}


def handle_list_nla(params):
    obj = _get_object(params["object_name"])
    adt = obj.animation_data
    tracks = list(adt.nla_tracks) if adt is not None else []
    return {"object": obj.name,
            "tracks": [{"name": t.name, "mute": t.mute,
                        "strips": [_strip_summary(s) for s in t.strips]}
                       for t in reversed(tracks)]}


def handle_add_fcurve_modifier(params):
    obj = _get_object(params["object_name"])
    kind = params.get("modifier")
    if kind not in FCURVE_MODIFIERS:
        raise ValueError(f"Unknown F-curve modifier {kind!r}")
    path = _check_path(params["data_path"])
    index = int(params.get("index", -1))
    if obj.animation_data is None or obj.animation_data.action is None:
        raise ValueError(f"'{obj.name}' has no animation; key it first")
    curves = [fc for fc in _action_fcurves(obj)
              if fc.data_path == path and (index < 0 or fc.array_index == index)]
    if not curves:
        raise ValueError(f"'{obj.name}' has no keyframes on '{path}'")
    added = []
    try:
        for fcurve in curves:
            mod = fcurve.modifiers.new(kind)
            added.append((fcurve, mod))
            for key, value in params.get("settings", {}).items():
                rna = mod.bl_rna.properties.get(key)
                if rna is None or rna.is_readonly or rna.type not in SETTABLE_RNA_TYPES:
                    raise ValueError(f"'{key}' is not a setting of the {kind} modifier")
                setattr(mod, key, value)
    except Exception:
        for fcurve, mod in added:
            fcurve.modifiers.remove(mod)
        raise
    return {"object": obj.name, "data_path": path, "modifier": kind, "curves": len(curves)}


def register():
    """Register all animation handlers with the dispatcher."""
    dispatcher.register_handler("insert_keyframe", handle_insert_keyframe)
    dispatcher.register_handler("delete_keyframe", handle_delete_keyframe)
    dispatcher.register_handler("set_frame", handle_set_frame)
    dispatcher.register_handler("set_frame_range", handle_set_frame_range)
    dispatcher.register_handler("set_interpolation", handle_set_interpolation)
    dispatcher.register_handler("create_animation_path", handle_create_animation_path)
    dispatcher.register_handler("list_keyframes", handle_list_keyframes)
    dispatcher.register_handler("clear_animation", handle_clear_animation)
    dispatcher.register_handler("add_driver", handle_add_driver)
    dispatcher.register_handler("remove_driver", handle_remove_driver)
    dispatcher.register_handler("list_drivers", handle_list_drivers)
    dispatcher.register_handler("keyframe_property", handle_keyframe_property)
    dispatcher.register_handler("manage_action", handle_manage_action)
    dispatcher.register_handler("add_nla_strip", handle_add_nla_strip)
    dispatcher.register_handler("list_nla", handle_list_nla)
    dispatcher.register_handler("add_fcurve_modifier", handle_add_fcurve_modifier)
