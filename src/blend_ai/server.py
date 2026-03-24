"""MCP Server entry point for blend-ai."""

import sys
from mcp.server.fastmcp import FastMCP

from blend_ai.connection import BlenderConnection

# Create the MCP server
mcp = FastMCP(
    "blend-ai",
    instructions="The most intuitive and efficient MCP Server for Blender",
)

# Global connection instance
_connection: BlenderConnection | None = None


def get_connection() -> BlenderConnection:
    """Get or create the global Blender connection."""
    global _connection
    if _connection is None:
        _connection = BlenderConnection()
    return _connection


# Import all tool modules to register them with the MCP server
from blend_ai.tools import (  # noqa: E402, F401
    scene,
    objects,
    transforms,
    modeling,
    materials,
    lighting,
    camera,
    animation,
    rendering,
    curves,
    sculpting,
    uv,
    physics,
    geometry_nodes,
    armature,
    collections,
    file_ops,
    viewport,
    code_exec,
    screenshot,
    booltool,
    mesh_editing,
    mesh_quality,
    gpencil,
)

# Import resources and prompts
from blend_ai.resources import scene_info  # noqa: E402, F401
from blend_ai.prompts import workflows  # noqa: E402, F401


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
