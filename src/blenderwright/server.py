"""MCP Server entry point for blenderwright."""

from mcp.server.fastmcp import FastMCP

from blenderwright.connection import BlenderConnection

# Create the MCP server
mcp = FastMCP(
    "blenderwright",
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
from blenderwright.tools import (  # noqa: E402, F401
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
    selection,
    booltool,
    mesh_editing,
    mesh_quality,
    gpencil,
    sweep,
    print3d,
    sequencer,
)

# Import resources and prompts
from blenderwright.resources import scene_info  # noqa: E402, F401
from blenderwright.prompts import workflows  # noqa: E402, F401


from blenderwright.strict import forbid_unknown_parameters  # noqa: E402
from blenderwright.enum_hints import attach_enum_hints  # noqa: E402
from blenderwright.aliases import attach_legacy_aliases  # noqa: E402

forbid_unknown_parameters(mcp)
attach_enum_hints(mcp)
attach_legacy_aliases(mcp)


def main():
    """Run the MCP server.

    --toolsets or BLENDERWRIGHT_TOOLSETS trims the tool list for clients with
    small context windows. Unset means every tool; see toolsets.py.
    """
    import argparse
    import os
    import sys

    from blenderwright.toolsets import ToolsetError, apply_toolsets

    parser = argparse.ArgumentParser(prog="blenderwright")
    parser.add_argument(
        "--toolsets",
        default=None,
        help="all (default), auto, core, or a comma-separated list of toolsets. "
             "Overrides BLENDERWRIGHT_TOOLSETS.",
    )
    args = parser.parse_args()
    spec = args.toolsets if args.toolsets is not None else os.environ.get("BLENDERWRIGHT_TOOLSETS")
    try:
        apply_toolsets(mcp, spec)
    except ToolsetError as exc:
        print(f"blenderwright: {exc}", file=sys.stderr)
        sys.exit(2)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
