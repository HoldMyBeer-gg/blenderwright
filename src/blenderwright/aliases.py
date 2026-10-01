"""Keep a renamed parameter's old spelling working.

The same concept was spelled two ways. 75 tools took `object_name` for "which
object"; 15 took a bare `name`, as did three tools referring to a collection
or a scene. A caller reading one tool's schema could not predict the next, and
strict.py turns a wrong guess into an error rather than a silent no-op, so
each mismatch cost a round trip out of a fixed budget.

Those 18 were renamed to the typed spelling the rest of the codebase already
used -- `object_name`, `collection_name`, `scene_name`, alongside the existing
`material_name`, `curve_name`, `node_name`. Renaming alone would break
anything already calling with `name`, so the old spelling stays valid as a
pydantic validation alias: the published schema advertises the new name only,
and both are accepted.

Nothing downstream changed. The function still receives the value under its
own parameter name, and the wire payload sent to the addon still uses its
original keys, so no handler needed editing.

`name` is deliberately NOT aliased on the create_* tools. There it means the
thing being made, which is a different concept, and accepting `object_name`
for it would be a lie.
"""

from typing import Any

from pydantic import AliasChoices

# Tool -> the parameter that replaced its bare `name`. Held as data so the
# tests can assert against the same list rather than a second copy of it.
RENAMED_FROM_NAME: dict[str, str] = {
    # transforms
    "set_location": "object_name",
    "set_rotation": "object_name",
    "set_scale": "object_name",
    "apply_transforms": "object_name",
    "set_origin": "object_name",
    "snap_to_grid": "object_name",
    # objects
    "delete_object": "object_name",
    "duplicate_object": "object_name",
    "get_object_info": "object_name",
    "set_object_visibility": "object_name",
    # lighting
    "set_light_property": "object_name",
    "delete_light": "object_name",
    "set_shadow_settings": "object_name",
    # camera
    "set_camera_property": "object_name",
    "set_active_camera": "object_name",
    # collections and scenes: not objects, so typed to what they refer to
    "set_collection_visibility": "collection_name",
    "delete_collection": "collection_name",
    "delete_scene": "scene_name",
}

LEGACY_SPELLING = "name"


def attach_legacy_aliases(server: Any) -> int:
    """Accept each renamed parameter's previous spelling.

    Args:
        server: A FastMCP instance whose registered tools should also accept
            the older parameter name.

    Returns:
        The number of tools given an alias. Tools already aliased are not
        counted, so calling this twice reports zero the second time.
    """
    count = 0
    for tool_name, canonical in sorted(RENAMED_FROM_NAME.items()):
        tool = server._tool_manager._tools.get(tool_name)
        if tool is None:
            continue
        model = tool.fn_metadata.arg_model
        field = model.model_fields.get(canonical)
        if field is None or field.validation_alias is not None:
            continue
        # Canonical first: pydantic publishes the first choice in the JSON
        # Schema, so the schema shows one name and only one.
        field.validation_alias = AliasChoices(canonical, LEGACY_SPELLING)
        model.model_config["populate_by_name"] = True
        model.model_rebuild(force=True)
        count += 1
    return count
