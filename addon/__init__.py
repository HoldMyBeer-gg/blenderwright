"""blend-ai: MCP Server addon for Blender.

This addon runs a TCP socket server inside Blender that receives
commands from the blend-ai MCP server and executes them using
Blender's Python API.
"""

bl_info = {
    "name": "blend-ai",
    "author": "blend-ai",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > blend-ai",
    "description": "MCP Server integration for AI-assisted 3D workflows",
    "category": "Interface",
}


def register():
    from . import ui_panel
    from . import handlers

    ui_panel.register()
    handlers.register()


def unregister():
    from . import ui_panel
    from . import server as addon_server
    from . import handlers

    addon_server.stop_server()
    handlers.unregister()
    ui_panel.unregister()


if __name__ == "__main__":
    register()
