"""MCP tools for vertex groups (weights), shape keys (blend shapes) and color attributes."""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_color,
    validate_enum,
    validate_indices,
    validate_int,
    validate_new_name,
    validate_numeric_range,
    validate_object_name,
    ValidationError,
)

ALLOWED_ASSIGN_MODES = {"REPLACE", "ADD", "SUBTRACT", "REMOVE"}
ALLOWED_SELECTION_MODES = {"ALL", "CURRENT"}
ALLOWED_GROUP_OPERATIONS = {
    "NORMALIZE", "NORMALIZE_ALL", "INVERT", "CLEAN", "SMOOTH", "LEVELS",
    "LIMIT_TOTAL", "MIRROR", "QUANTIZE",
}
ALLOWED_COLOR_DOMAINS = {"POINT", "CORNER"}
ALLOWED_COLOR_TYPES = {"BYTE_COLOR", "FLOAT_COLOR"}
ALLOWED_LATTICE_INTERPOLATIONS = {"KEY_LINEAR", "KEY_CARDINAL", "KEY_CATMULL_ROM",
                                  "KEY_BSPLINE"}
ALLOWED_AXES = {"X", "Y", "Z"}
ALLOWED_SIDES = {"POS", "NEG", "ALIGN"}
MAX_LATTICE_POINTS_PER_AXIS = 64
MAX_LATTICE_OFFSET = 10_000.0
MAX_LATTICE_SCALE = 100.0
MAX_SHAPE_OFFSET = 1000.0
SLIDER_LIMIT = 10.0
MAX_FRAME = 1_048_574


def _send(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def assign_vertex_group(
    object_name: str,
    group_name: str,
    vertex_indices: list[int] | None = None,
    weight: float = 1.0,
    mode: str = "REPLACE",
    selection: str = "ALL",
) -> dict[str, Any]:
    """Put vertices into a vertex group with a weight, creating the group if needed.

    Vertex groups drive armature skinning, and limit modifiers (Displace,
    Solidify, Mask) and shape keys to part of a mesh.

    Args:
        object_name: Mesh object.
        group_name: Vertex group; created if it does not exist.
        vertex_indices: Vertices to change. Omit to use the whole mesh, or
            the edit-mode selection with selection="CURRENT".
        weight: 0.0 to 1.0.
        mode: REPLACE sets the weight, ADD and SUBTRACT change it, REMOVE
            takes the vertices out of the group.
        selection: When vertex_indices is omitted: ALL vertices, or CURRENT
            for the ones selected in edit mode (use the select_* tools first).

    Returns:
        Dict with the group name, its index and how many vertices changed.
    """
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "group_name": validate_object_name(group_name),
        "weight": validate_numeric_range(weight, min_val=0.0, max_val=1.0, name="weight"),
        "mode": validate_enum(mode, ALLOWED_ASSIGN_MODES, name="mode"),
        "selection": validate_enum(selection, ALLOWED_SELECTION_MODES, name="selection"),
    }
    if vertex_indices is not None:
        params["vertex_indices"] = validate_indices(vertex_indices)
    return _send("assign_vertex_group", params)


@mcp.tool()
def list_vertex_groups(object_name: str) -> dict[str, Any]:
    """List an object's vertex groups with vertex counts and weight ranges.

    Args:
        object_name: Mesh object.

    Returns:
        Dict with each group's name, index, vertex count, min and max weight.
    """
    return _send("list_vertex_groups", {"object_name": validate_object_name(object_name)})


@mcp.tool()
def remove_vertex_group(object_name: str, group_name: str) -> dict[str, Any]:
    """Delete a vertex group and every weight in it.

    Args:
        object_name: Mesh object.
        group_name: Vertex group to delete.

    Returns:
        Dict with the removed group and the groups left.
    """
    return _send("remove_vertex_group", {
        "object_name": validate_object_name(object_name),
        "group_name": validate_object_name(group_name),
    })


@mcp.tool()
def vertex_group_operation(
    object_name: str,
    group_name: str,
    operation: str,
    factor: float = 0.5,
    repeat: int = 1,
    threshold: float = 0.0,
    offset: float = 0.0,
    gain: float = 1.0,
    max_groups: int = 4,
    steps: int = 4,
) -> dict[str, Any]:
    """Clean up or reshape the weights in a vertex group.

    Args:
        object_name: Mesh object.
        group_name: Vertex group to work on.
        operation: One of:
            NORMALIZE (scale so the highest weight is 1),
            NORMALIZE_ALL (make each vertex's weights across all groups sum
                to 1, as armatures expect),
            INVERT (weight becomes 1 - weight), CLEAN (drop weights at or
            below threshold), SMOOTH (blur weights with neighbours: factor,
            repeat), LEVELS (weight * gain + offset), LIMIT_TOTAL (keep at
            most max_groups groups per vertex, as game engines need),
            MIRROR (mirror the weights across X), QUANTIZE (snap weights to
            steps levels).
        factor: SMOOTH strength, 0.0 to 1.0.
        repeat: SMOOTH passes, 1 to 200.
        threshold: CLEAN cut-off, 0.0 to 1.0.
        offset: LEVELS offset, -1.0 to 1.0.
        gain: LEVELS gain, 0.0 to 10.0.
        max_groups: LIMIT_TOTAL groups per vertex, 1 to 32.
        steps: QUANTIZE levels, 1 to 1000.

    Returns:
        Dict with the group's vertex count and weight range afterwards.
    """
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "group_name": validate_object_name(group_name),
        "operation": validate_enum(operation, ALLOWED_GROUP_OPERATIONS, name="operation"),
    }
    if operation == "SMOOTH":
        params["factor"] = validate_numeric_range(factor, min_val=0.0, max_val=1.0, name="factor")
        params["repeat"] = validate_int(repeat, 1, 200, name="repeat")
    elif operation == "CLEAN":
        params["threshold"] = validate_numeric_range(
            threshold, min_val=0.0, max_val=1.0, name="threshold")
    elif operation == "LEVELS":
        params["offset"] = validate_numeric_range(offset, min_val=-1.0, max_val=1.0, name="offset")
        params["gain"] = validate_numeric_range(gain, min_val=0.0, max_val=10.0, name="gain")
    elif operation == "LIMIT_TOTAL":
        params["max_groups"] = validate_int(max_groups, 1, 32, name="max_groups")
    elif operation == "QUANTIZE":
        params["steps"] = validate_int(steps, 1, 1000, name="steps")
    return _send("vertex_group_operation", params)


@mcp.tool()
def add_shape_key(object_name: str, key_name: str, from_mix: bool = False) -> dict[str, Any]:
    """Add a shape key (blend shape). The first call also creates the Basis.

    Shape keys store alternative vertex positions blended by a 0-1 value:
    facial expressions, morphs, corrective shapes. Shape it with
    move_shape_key_vertices, blend with set_shape_key, animate with
    keyframe_shape_key.

    Args:
        object_name: Mesh object.
        key_name: Name for the new shape key.
        from_mix: Start from the current blend of all keys instead of the Basis.

    Returns:
        Dict with the new key and every key on the object.
    """
    return _send("add_shape_key", {
        "object_name": validate_object_name(object_name),
        "key_name": validate_object_name(key_name),
        "from_mix": bool(from_mix),
    })


@mcp.tool()
def set_shape_key(
    object_name: str,
    key_name: str,
    value: float | None = None,
    slider_min: float | None = None,
    slider_max: float | None = None,
    mute: bool | None = None,
    vertex_group: str | None = None,
    relative_key: str = "",
) -> dict[str, Any]:
    """Set how strongly a shape key applies, and its options.

    Args:
        object_name: Mesh object.
        key_name: Shape key.
        value: Blend amount, normally 0.0 to 1.0, within the slider range.
        slider_min: Lowest allowed value, -10.0 to 10.0 (0.0 by default).
            Negative values let a "smile" key also frown.
        slider_max: Highest allowed value, -10.0 to 10.0 (1.0 by default).
        mute: Switch the key off without losing its value.
        vertex_group: Limit the key to this vertex group's weights; "" clears it.
        relative_key: Key this one is measured against (the Basis by default).

    Returns:
        Dict with the key's settings after the change.
    """
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "key_name": validate_object_name(key_name),
    }
    for name, val in (("value", value), ("slider_min", slider_min), ("slider_max", slider_max)):
        if val is not None:
            params[name] = validate_numeric_range(val, min_val=-SLIDER_LIMIT,
                                                  max_val=SLIDER_LIMIT, name=name)
    if "slider_min" in params and "slider_max" in params and (
            params["slider_min"] >= params["slider_max"]):
        raise ValidationError("slider_min must be below slider_max")
    if mute is not None:
        params["mute"] = bool(mute)
    if vertex_group is not None:
        params["vertex_group"] = validate_object_name(vertex_group) if vertex_group else ""
    if relative_key:
        params["relative_key"] = validate_object_name(relative_key)
    return _send("set_shape_key", params)


@mcp.tool()
def move_shape_key_vertices(
    object_name: str,
    key_name: str,
    offset: list[float],
    vertex_indices: list[int] | None = None,
    vertex_group: str = "",
) -> dict[str, Any]:
    """Move vertices inside a shape key, building the blend shape.

    The offset is in the object's local space. With a vertex group, each
    vertex moves by offset times its weight, which gives soft falloff:
    weight the cheeks, then move them out to puff them.

    Args:
        object_name: Mesh object.
        key_name: Shape key to edit (not the Basis).
        offset: [x, y, z] distance to move, each -1000 to 1000.
        vertex_indices: Vertices to move. Leave out to use vertex_group, or
            neither to move the whole mesh.
        vertex_group: Move by this group's weights instead of by index.

    Returns:
        Dict with the number of vertices moved.
    """
    if not isinstance(offset, (list, tuple)) or len(offset) != 3:
        raise ValidationError("offset must be [x, y, z]")
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "key_name": validate_object_name(key_name),
        "offset": [float(validate_numeric_range(v, min_val=-MAX_SHAPE_OFFSET,
                                                max_val=MAX_SHAPE_OFFSET, name="offset"))
                   for v in offset],
    }
    if vertex_indices is not None and vertex_group:
        raise ValidationError("Give vertex_indices or vertex_group, not both")
    if vertex_indices is not None:
        params["vertex_indices"] = validate_indices(vertex_indices)
    if vertex_group:
        params["vertex_group"] = validate_object_name(vertex_group)
    return _send("move_shape_key_vertices", params)


@mcp.tool()
def list_shape_keys(object_name: str) -> dict[str, Any]:
    """List an object's shape keys with values, ranges and options.

    Args:
        object_name: Mesh object.

    Returns:
        Dict with the reference key and each key's settings.
    """
    return _send("list_shape_keys", {"object_name": validate_object_name(object_name)})


@mcp.tool()
def remove_shape_key(object_name: str, key_name: str) -> dict[str, Any]:
    """Delete a shape key.

    Args:
        object_name: Mesh object.
        key_name: Shape key to delete.

    Returns:
        Dict with the removed key and the keys left.
    """
    return _send("remove_shape_key", {
        "object_name": validate_object_name(object_name),
        "key_name": validate_object_name(key_name),
    })


@mcp.tool()
def keyframe_shape_key(
    object_name: str,
    key_name: str,
    frame: int,
    value: float | None = None,
) -> dict[str, Any]:
    """Keyframe a shape key's value so the blend shape animates.

    Args:
        object_name: Mesh object.
        key_name: Shape key.
        frame: Frame number.
        value: Value to set before keying; omit to key the current value.

    Returns:
        Dict with the key, frame and keyed value.
    """
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "key_name": validate_object_name(key_name),
        "frame": validate_int(frame, -MAX_FRAME, MAX_FRAME, name="frame"),
    }
    if value is not None:
        params["value"] = validate_numeric_range(value, min_val=-SLIDER_LIMIT,
                                                 max_val=SLIDER_LIMIT, name="value")
    return _send("keyframe_shape_key", params)


@mcp.tool()
def paint_color_attribute(
    object_name: str,
    color: list[float],
    attribute_name: str = "Color",
    domain: str = "CORNER",
    data_type: str = "BYTE_COLOR",
    vertex_indices: list[int] | None = None,
    selection: str = "ALL",
) -> dict[str, Any]:
    """Fill a color attribute (vertex colors) on a mesh, creating it if needed.

    The attribute becomes the active and render color. Read it in a material
    with a ShaderNodeVertexColor node whose layer_name is the attribute name.
    Game engines and glTF export pick it up as vertex color.

    Args:
        object_name: Mesh object.
        color: Linear RGB or RGBA, each 0.0 to 1.0.
        attribute_name: Color attribute; created if it does not exist.
        domain: CORNER (per face corner, allows hard color edges) or POINT
            (per vertex). Used only when creating the attribute.
        data_type: BYTE_COLOR (8-bit) or FLOAT_COLOR. Used only when creating.
        vertex_indices: Vertices to paint. Omit to paint the whole mesh, or
            the edit-mode selection with selection="CURRENT".
        selection: When vertex_indices is omitted: ALL, or CURRENT for the
            vertices selected in edit mode (use the select_* tools first).

    Returns:
        Dict with the attribute, its domain and type, whether it was created,
        how many elements were painted, and all color attribute names.
    """
    rgba = list(validate_color(color))
    if len(rgba) == 3:
        rgba.append(1.0)
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "color": rgba,
        "attribute_name": validate_object_name(attribute_name),
        "domain": validate_enum(domain, ALLOWED_COLOR_DOMAINS, name="domain"),
        "data_type": validate_enum(data_type, ALLOWED_COLOR_TYPES, name="data_type"),
        "selection": validate_enum(selection, ALLOWED_SELECTION_MODES, name="selection"),
    }
    if vertex_indices is not None:
        params["vertex_indices"] = validate_indices(vertex_indices)
    return _send("paint_color_attribute", params)


@mcp.tool()
def remove_color_attribute(object_name: str, attribute_name: str) -> dict[str, Any]:
    """Delete a color attribute from a mesh.

    Args:
        object_name: Mesh object.
        attribute_name: Color attribute to remove.

    Returns:
        Dict with the removed name and the color attributes left.
    """
    return _send("remove_color_attribute", {
        "object_name": validate_object_name(object_name),
        "attribute_name": validate_object_name(attribute_name),
    })


@mcp.tool()
def create_lattice(
    object_name: str,
    resolution: list[int] | None = None,
    interpolation: str = "KEY_LINEAR",
    lattice_name: str = "",
) -> dict[str, Any]:
    """Wrap an object in a lattice cage and deform it through the cage.

    The lattice is fitted to the object's bounding box and a Lattice modifier
    is added. Then bend, taper or bulge the whole shape with
    move_lattice_points instead of editing vertices.

    Args:
        object_name: Object to deform (mesh, curve, text...).
        resolution: Points along [u, v, w] (the object's X, Y, Z), 2 to 64 each.
            More points give more local control. Default [2, 2, 2].
        interpolation: KEY_LINEAR (default) follows the points exactly: scale
            them to 0.5 and the shape halves. KEY_BSPLINE is smoother but only
            approximates the points (the same move gives about 0.67).
            KEY_CATMULL_ROM and KEY_CARDINAL sit between.
        lattice_name: Name for the lattice object; defaults to "<object> Lattice".

    Returns:
        Dict with the lattice name, its point count and the modifier name.
    """
    resolution = [2, 2, 2] if resolution is None else resolution
    if not isinstance(resolution, list) or len(resolution) != 3:
        raise ValidationError("resolution must be [u, v, w]")
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "resolution": [validate_int(r, 2, MAX_LATTICE_POINTS_PER_AXIS, name="resolution")
                       for r in resolution],
        "interpolation": validate_enum(interpolation, ALLOWED_LATTICE_INTERPOLATIONS,
                                       name="interpolation"),
    }
    if any(isinstance(r, float) and not r.is_integer() for r in resolution):
        raise ValidationError("resolution must be whole numbers")
    if lattice_name:
        params["lattice_name"] = validate_new_name(lattice_name)
    return _send("create_lattice", params)


@mcp.tool()
def move_lattice_points(
    lattice_name: str,
    offset: list[float] | None = None,
    scale: list[float] | None = None,
    axis: str | None = None,
    sign: str = "POS",
    point_indices: list[int] | None = None,
    reset: bool = False,
) -> dict[str, Any]:
    """Move or scale lattice points to deform everything the lattice is bound to.

    Pick points by side (axis and sign, split at the middle of the lattice) or
    by index; with neither, every point moves. Scaling is about the lattice
    centre, per axis: scale [0.2, 0.2, 1] on the top tapers it to a point.

    Args:
        lattice_name: Lattice object from create_lattice.
        offset: [x, y, z] in world units added to the chosen points.
        scale: [x, y, z] factors, 0.01 to 100, about the lattice centre.
        axis: X, Y or Z: choose the points on one side of the lattice.
        sign: POS, NEG, or ALIGN (the middle plane) with axis.
        point_indices: Choose points by index instead (u fastest, then v, then w).
        reset: Put every point back where it started (others ignored).

    Returns:
        Dict with how many points moved and the lattice's point count.
    """
    if not isinstance(reset, bool):
        raise ValidationError(f"reset must be true or false, got {reset!r}")
    params: dict[str, Any] = {"lattice_name": validate_object_name(lattice_name)}
    if reset:
        if offset is not None or scale is not None or axis is not None \
                or point_indices is not None:
            raise ValidationError("reset puts every point back; give nothing else")
        params["reset"] = True
        return _send("move_lattice_points", params)
    if offset is None and scale is None:
        raise ValidationError("Give offset, scale, or reset")
    if offset is not None:
        params["offset"] = [validate_numeric_range(v, min_val=-MAX_LATTICE_OFFSET,
                                                   max_val=MAX_LATTICE_OFFSET, name="offset")
                            for v in _triple(offset, "offset")]
    if scale is not None:
        params["scale"] = [validate_numeric_range(v, min_val=0.01, max_val=MAX_LATTICE_SCALE,
                                                  name="scale")
                           for v in _triple(scale, "scale")]
    if axis is not None and point_indices is not None:
        raise ValidationError("Choose points by axis or by point_indices, not both")
    if axis is not None:
        params["axis"] = validate_enum(axis, ALLOWED_AXES, name="axis")
        params["sign"] = validate_enum(sign, ALLOWED_SIDES, name="sign")
    if point_indices is not None:
        params["point_indices"] = validate_indices(point_indices, "point_indices", "point")
    return _send("move_lattice_points", params)


def _triple(value: Any, name: str) -> list:
    if not isinstance(value, list) or len(value) != 3:
        raise ValidationError(f"{name} must be [x, y, z]")
    return value
