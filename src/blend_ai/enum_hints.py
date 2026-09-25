"""Publish each tool's accepted values as a JSON Schema enum.

27 parameters were enforced against an ALLOWED_* set and documented with
nothing, or with two examples and an "e.g.". A model reading the schema had no
way to know what was acceptable, so it guessed, and every wrong guess cost a
round trip out of a fixed budget.

Rather than hand-write 27 lists into docstrings, where they would drift from
the constants exactly as the tool count drifted from the code, the pairing is
read out of the source: `validate_enum(param, ALLOWED_THING)` says that
`param` accepts `ALLOWED_THING`. The constant remains the single definition.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
from typing import Any

# validate_enum(value, ALLOWED_X, ...) inside a tool function body.
_ENUM_CALL = re.compile(r"validate_enum\(\s*(\w+)\s*,\s*(ALLOWED_\w+)")


def _enum_pairs(module: Any) -> dict[str, dict[str, list[str]]]:
    """Map tool name -> parameter -> accepted values, for one tool module.

    Args:
        module: An imported module from blend_ai.tools.

    Returns:
        Nested mapping of function name to parameter to sorted values. A
        parameter checked against more than one set is omitted, because the
        choice depends on another argument and a single enum would be a lie.
    """
    try:
        source = inspect.getsource(module)
    except (OSError, TypeError):
        return {}

    found: dict[str, dict[str, set[str]]] = {}
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = ast.get_source_segment(source, node) or ""
        for param, const_name in _ENUM_CALL.findall(body):
            const = getattr(module, const_name, None)
            if not isinstance(const, (set, frozenset, list, tuple)):
                continue
            if not all(isinstance(v, str) for v in const):
                continue
            found.setdefault(node.name, {}).setdefault(param, set())
            found[node.name][param] |= {"", *const} - {""}

    result: dict[str, dict[str, list[str]]] = {}
    for func, params in found.items():
        for param, values in params.items():
            body = None
            # A parameter validated against two different sets (the value of
            # set_curve_property depends on which property) cannot be one enum.
            if sum(1 for p, c in _ENUM_CALL.findall(
                    ast.get_source_segment(source, next(
                        n for n in ast.walk(tree)
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and n.name == func)) or "") if p == param) > 1:
                continue
            result.setdefault(func, {})[param] = sorted(values)
            del body
    return result


def attach_enum_hints(server: Any) -> int:
    """Attach accepted values to every tool parameter that has a fixed set.

    Args:
        server: A FastMCP instance with tools already registered.

    Returns:
        The number of parameters given an enum.
    """
    modules: dict[str, dict[str, dict[str, list[str]]]] = {}
    attached = 0

    for tool in server._tool_manager._tools.values():
        module_name = getattr(tool.fn, "__module__", "")
        if not module_name.startswith("blend_ai.tools."):
            continue
        if module_name not in modules:
            try:
                modules[module_name] = _enum_pairs(importlib.import_module(module_name))
            except Exception:
                modules[module_name] = {}

        params = modules[module_name].get(tool.fn.__name__, {})
        if not params:
            continue

        model = tool.fn_metadata.arg_model
        changed = False
        for param, values in params.items():
            field = model.model_fields.get(param)
            if field is None or (field.json_schema_extra or {}).get("enum"):
                continue
            extra = dict(field.json_schema_extra or {})
            extra["enum"] = values
            field.json_schema_extra = extra
            changed = True
            attached += 1
        if changed:
            model.model_rebuild(force=True)
            # FastMCP caches the JSON schema on the tool at registration, and
            # that cached copy is what list_tools() serves. Rebuilding the
            # model alone would leave clients reading the old one.
            tool.parameters = model.model_json_schema()

    return attached
