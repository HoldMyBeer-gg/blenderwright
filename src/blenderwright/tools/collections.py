"""MCP tools for Blender collection management."""

from typing import Any

from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_enum,
    validate_new_name,
    validate_numeric_range,
    validate_object_name,
    validate_vector,
    ValidationError,
)

MAX_TRANSFORM = 1_000_000.0
ALLOWED_VIEW_LAYER_ACTIONS = {"LIST", "ADD", "REMOVE", "RENAME", "SET_ACTIVE", "SET"}


@mcp.tool()
def create_collection(
    name: str,
    parent: str = "",
) -> dict[str, Any]:
    """Create a new collection, optionally nested under a parent collection.

    Args:
        name: Name for the new collection.
        parent: Optional name of parent collection to nest under.
                Empty string uses the scene's root collection.

    Returns:
        Dict with the created collection's name and parent.
    """
    name = validate_new_name(name)
    if parent:
        parent = validate_object_name(parent)

    conn = get_connection()
    response = conn.send_command("create_collection", {
        "name": name,
        "parent": parent,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def move_to_collection(
    object_names: list[str],
    collection_name: str,
) -> dict[str, Any]:
    """Move objects to a collection, unlinking them from their current collections.

    Args:
        object_names: List of object names to move.
        collection_name: Name of the destination collection.

    Returns:
        Dict with the moved objects and destination collection.
    """
    if not object_names:
        raise ValidationError("object_names must not be empty")
    validated_names = [validate_object_name(n) for n in object_names]
    collection_name = validate_object_name(collection_name)

    conn = get_connection()
    response = conn.send_command("move_to_collection", {
        "object_names": validated_names,
        "collection_name": collection_name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def set_collection_visibility(
    collection_name: str,
    visible: bool,
    viewport: bool = True,
    render: bool = True,
) -> dict[str, Any]:
    """Set collection visibility in viewport and/or render.

    Args:
        collection_name: Name of the collection.
        visible: Whether the collection should be visible.
        viewport: Apply visibility change to viewport. Defaults to True.
        render: Apply visibility change to render. Defaults to True.

    Returns:
        Confirmation dict with visibility state.
    """
    collection_name = validate_object_name(collection_name)

    conn = get_connection()
    response = conn.send_command("set_collection_visibility", {
        "name": collection_name,
        "visible": visible,
        "viewport": viewport,
        "render": render,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def delete_collection(
    collection_name: str,
    delete_objects: bool = False,
) -> dict[str, Any]:
    """Delete a collection.

    Args:
        collection_name: Name of the collection to delete.
        delete_objects: If True, also delete all objects in the collection.
                       If False, objects are unlinked but kept in the scene.

    Returns:
        Confirmation dict.
    """
    collection_name = validate_object_name(collection_name)

    conn = get_connection()
    response = conn.send_command("delete_collection", {
        "name": collection_name,
        "delete_objects": delete_objects,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _send_collection_command(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _transform(vec: Any, name: str, nonzero: bool = False) -> list[float]:
    validate_vector(vec, size=3, name=name)
    out = [float(validate_numeric_range(v, min_val=-MAX_TRANSFORM, max_val=MAX_TRANSFORM,
                                        name=name)) for v in vec]
    if nonzero and not all(out):
        raise ValidationError(f"{name} components must not be zero")
    return out


@mcp.tool()
def create_collection_instance(
    collection_name: str,
    name: str = "",
    location: list[float] | tuple[float, ...] = (0, 0, 0),
    rotation: list[float] | tuple[float, ...] = (0, 0, 0),
    scale: list[float] | tuple[float, ...] = (1, 1, 1),
) -> dict[str, Any]:
    """Place a collection as a lightweight instance (an empty that shows it).

    Instances share the collection's data, so a hundred trees cost little
    more than one, and editing the collection updates every copy. Works with
    local and linked collections.

    Args:
        collection_name: Collection to instance.
        name: Name for the instance object; empty uses the collection name.
        location: World position [x, y, z].
        rotation: Euler rotation [x, y, z] in radians.
        scale: Scale [x, y, z]; components must not be zero.

    Returns:
        Dict with the instance object's name and its collection.
    """
    return _send_collection_command("create_collection_instance", {
        "collection_name": validate_object_name(collection_name),
        "name": validate_new_name(name) if name else "",
        "location": _transform(location, "location"),
        "rotation": _transform(rotation, "rotation"),
        "scale": _transform(scale, "scale", nonzero=True),
    })


@mcp.tool()
def make_instances_real(object_name: str, keep_hierarchy: bool = False) -> dict[str, Any]:
    """Turn a collection instance into real, separately editable objects.

    Args:
        object_name: The instance object (from create_collection_instance or
            a linked collection).
        keep_hierarchy: Keep the instanced objects' parent links.

    Returns:
        Dict with the names of the new objects.
    """
    return _send_collection_command("make_instances_real", {
        "object_name": validate_object_name(object_name),
        "keep_hierarchy": bool(keep_hierarchy),
    })


def _send_collection_command(command: str, params: dict[str, Any]) -> Any:
    conn = get_connection()
    response = conn.send_command(command, params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


def _optional_flag(params: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, bool):
        raise ValidationError(f"{key} must be true or false, got {value!r}")
    params[key] = value


@mcp.tool()
def manage_view_layer(
    action: str,
    view_layer: str | None = None,
    new_name: str | None = None,
    material_override: str | None = None,
    world_override: str | None = None,
    use_for_render: bool | None = None,
) -> dict[str, Any]:
    """List, add, remove, rename or configure view layers (separate render layers).

    Each view layer renders the scene with its own collection settings
    (see set_layer_collection) and passes, e.g. a foreground layer and a
    background layer composited together, or a clay layer. Pass, light
    group and AOV tools act on the active view layer: SET_ACTIVE first.

    Args:
        action: LIST; ADD (view_layer is the new name); REMOVE; RENAME (to
            new_name); SET_ACTIVE (the layer other tools change); SET (the
            overrides and use_for_render below).
        view_layer: The layer to act on.
        new_name: RENAME only.
        material_override: SET only: render every object with this material
            (a clay render); "" clears it.
        world_override: SET only: world used for this layer; "" clears it.
        use_for_render: SET only: whether this layer renders at all.

    Returns:
        Dict with every view layer (name, active, use_for_render, overrides).
    """
    params: dict[str, Any] = {
        "action": validate_enum(action, ALLOWED_VIEW_LAYER_ACTIONS, name="action"),
    }
    if action != "LIST":
        if view_layer is None:
            raise ValidationError(f"{action} needs view_layer")
        params["view_layer"] = (validate_new_name(view_layer) if action == "ADD"
                                else validate_object_name(view_layer))
    if action == "RENAME":
        if new_name is None:
            raise ValidationError("RENAME needs new_name")
        params["new_name"] = validate_new_name(new_name)
    if action == "SET":
        for key, value in (("material_override", material_override),
                           ("world_override", world_override)):
            if value is not None:
                params[key] = "" if value == "" else validate_object_name(value)
        _optional_flag(params, "use_for_render", use_for_render)
        if len(params) == 2:
            raise ValidationError("SET needs material_override, world_override or "
                                  "use_for_render")
    return _send_collection_command("manage_view_layer", params)


@mcp.tool()
def set_layer_collection(
    collection_name: str,
    view_layer: str | None = None,
    exclude: bool | None = None,
    holdout: bool | None = None,
    indirect_only: bool | None = None,
) -> dict[str, Any]:
    """Set how a collection takes part in one view layer.

    Args:
        collection_name: Collection, at any depth.
        view_layer: View layer to change; omit for the active one.
        exclude: Leave the collection out of this layer entirely.
        holdout: Render it as a transparent cut-out (the objects mask what is
            behind them), for compositing layers back together.
        indirect_only: Cycles: it shows only in reflections, shadows and bounce
            light, not directly to the camera.

    Returns:
        Dict with the collection, the layer and its exclude/holdout/indirect_only.
    """
    params: dict[str, Any] = {"collection_name": validate_object_name(collection_name)}
    if view_layer is not None:
        params["view_layer"] = validate_object_name(view_layer)
    _optional_flag(params, "exclude", exclude)
    _optional_flag(params, "holdout", holdout)
    _optional_flag(params, "indirect_only", indirect_only)
    if not {"exclude", "holdout", "indirect_only"} & params.keys():
        raise ValidationError("Give at least one of exclude, holdout, indirect_only")
    return _send_collection_command("set_layer_collection", params)
