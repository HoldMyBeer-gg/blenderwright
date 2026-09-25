"""Make tool arguments strict, so a wrong parameter name is an error.

Pydantic ignores unknown fields by default, so a call naming a parameter that
does not exist succeeds, changes nothing, and reports success. The caller gets
no signal at all that it got the name wrong:
create_principled_material(transmission_weight=...) when the parameter is
`transmission`, or base_color=... when it is `color`. Both happened here, once
by a model and once by a person, on the same day.

Silently discarding input is the worst failure mode available. An error at
least costs one round trip and teaches the caller the right name.
"""

from typing import Any


def forbid_unknown_parameters(server: Any) -> int:
    """Switch every tool's argument model to reject undeclared parameters.

    Args:
        server: A FastMCP instance whose registered tools should be hardened.

    Returns:
        The number of argument models changed. Models already strict are not
        counted, so calling this twice reports zero the second time.
    """
    count = 0
    for tool in server._tool_manager._tools.values():
        model = tool.fn_metadata.arg_model
        if model.model_config.get("extra") != "forbid":
            model.model_config["extra"] = "forbid"
            model.model_rebuild(force=True)
            count += 1
    return count
