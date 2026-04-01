"""Registry that extracts tool definitions from FastMCP for use with Ollama."""

import asyncio
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

        clean_props: dict[str, Any] = {}
        for name, prop in properties.items():
            clean_prop: dict[str, Any] = {
                "type": _map_json_type(prop.get("type", "string")),
            }
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
