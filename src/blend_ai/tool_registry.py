"""Registry that extracts tool definitions from FastMCP for use with Ollama."""

import asyncio
import re
from typing import Any


def get_ollama_tools(mcp_server: Any) -> list[dict[str, Any]]:
    """Convert all registered MCP tools to Ollama tool-call format.

    Args:
        mcp_server: A FastMCP server instance with registered tools.

    Returns:
        List of tool definitions in Ollama's format.
    """
    mcp_tools = asyncio.run(mcp_server.list_tools())
    ollama_tools: list[dict[str, Any]] = []

    for tool in mcp_tools:
        schema = tool.inputSchema
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        arg_docs = _parse_arg_docs(tool.description or "")
        clean_props: dict[str, Any] = {}
        for name, prop in properties.items():
            prop = _flatten_optional(prop)
            clean_prop: dict[str, Any] = {}
            # Absent "type" means Any, not string. Claiming string sends a model
            # looking for quotes: a colour published as string invites "red".
            if "type" in prop:
                clean_prop["type"] = _map_json_type(prop["type"])
            if "description" in prop:
                clean_prop["description"] = prop["description"]
            if "title" in prop:
                clean_prop["title"] = prop["title"]
            if "default" in prop:
                clean_prop["default"] = prop["default"]
            if "enum" in prop:
                clean_prop["enum"] = prop["enum"]
            if "items" in prop:
                clean_prop["items"] = prop["items"]
            # A length stated in the annotation is authoritative; keep it.
            for constraint in ("minItems", "maxItems", "minimum", "maximum"):
                if constraint in prop:
                    clean_prop[constraint] = prop[constraint]

            # The docstring documents each parameter, but that text reaches the
            # model as one blob attached to the tool rather than as structure on
            # the parameter it describes. Models follow the schema, so put it
            # where they look.
            if "description" not in clean_prop and name in arg_docs:
                clean_prop["description"] = arg_docs[name]

            # A three-element default is the codebase's way of saying "this is
            # an XYZ vector". Say so in the schema: without it a model guesses
            # the length, and a wrong guess costs a whole round trip.
            default = clean_prop.get("default")
            if clean_prop.get("type") == "array" and isinstance(default, list):
                if len(default) == 3 and all(
                    isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in default
                ):
                    clean_prop["minItems"] = 3
                    clean_prop["maxItems"] = 3

            clean_props[name] = clean_prop

        ollama_tool: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": {
                    "type": "object",
                    "properties": clean_props,
                    "required": required,
                },
            },
        }
        ollama_tools.append(ollama_tool)

    return ollama_tools


def _flatten_optional(prop: dict[str, Any]) -> dict[str, Any]:
    """Collapse an `X | None` union back to X.

    Pydantic renders an optional parameter as an anyOf with a null branch and
    no top-level type, so anything reading `prop["type"]` sees nothing. Keeping
    the real branch preserves both the type and its items.

    Args:
        prop: A JSON Schema property.

    Returns:
        The property, or its single non-null branch merged with any sibling
        keys such as default and title.
    """
    branches = prop.get("anyOf")
    if not branches:
        return prop
    real = [b for b in branches if b.get("type") != "null"]
    if len(real) != 1:
        # A genuine multi-type union; leave it alone rather than guess.
        return prop
    merged = {k: v for k, v in prop.items() if k != "anyOf"}
    merged.update(real[0])
    return merged


def _parse_arg_docs(description: str) -> dict[str, str]:
    """Pull per-parameter text out of a Google-style Args: section.

    Args:
        description: The tool description, which is the full docstring.

    Returns:
        Mapping of parameter name to its documented description. Entries that
        wrap onto following lines are joined back into one string.
    """
    match = re.search(r"\n\s*Args:\s*\n(.*?)(?:\n\s*(?:Returns|Raises):|\Z)",
                      description, re.S)
    if not match:
        return {}

    docs: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        entry = re.match(r"\s{4}(\w+):\s*(.*)", line)
        if entry:
            if current:
                docs[current] = " ".join(buf).strip()
            current, buf = entry.group(1), [entry.group(2)]
        elif current:
            buf.append(line.strip())
    if current:
        docs[current] = " ".join(buf).strip()
    return docs


def _map_json_type(json_type: str) -> str:
    """Map JSON Schema types to Ollama-compatible types."""
    type_map = {
        "string": "string",
        "integer": "integer",
        "number": "number",
        "boolean": "boolean",
        "array": "array",
        "object": "object",
    }
    return type_map.get(json_type, "string")
