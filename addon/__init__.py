"""blend-ai: MCP Server addon for Blender.

This addon runs a TCP socket server inside Blender that receives
commands from the blend-ai MCP server and executes them using
Blender's Python API.
"""

bl_info = {
    "name": "blend-ai",
    "author": "blend-ai",
    "version": (1, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > blend-ai",
    "description": "MCP Server integration for AI-assisted 3D workflows",
    "category": "Interface",
}

# Module-level reference set in register() — holds the @persistent load_post handler
_clear_render_guard_on_load = None


def register():
    import bpy
    from bpy.app.handlers import persistent
    from . import ui_panel
    from . import handlers
    from .render_guard import render_guard

    global _clear_render_guard_on_load

    ui_panel.register()
    handlers.register()

    # Track render state so the server can return "busy" during renders
    bpy.app.handlers.render_pre.append(render_guard.on_render_pre)
    bpy.app.handlers.render_complete.append(render_guard.on_render_complete)
    bpy.app.handlers.render_cancel.append(render_guard.on_render_cancel)

    # Clear render guard when a .blend file loads — recovers from crashed renders
    @persistent
    def _on_load_post(filepath):
        render_guard.on_render_complete(None)

    _clear_render_guard_on_load = _on_load_post
    bpy.app.handlers.load_post.append(_clear_render_guard_on_load)


def unregister():
    import bpy
    from . import ui_panel
    from . import server as addon_server
    from . import handlers
    from .render_guard import render_guard

    global _clear_render_guard_on_load

    # Remove render handlers
    if render_guard.on_render_cancel in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.remove(render_guard.on_render_cancel)
    if render_guard.on_render_complete in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.remove(render_guard.on_render_complete)
    if render_guard.on_render_pre in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.remove(render_guard.on_render_pre)

    # Remove load_post handler
    if _clear_render_guard_on_load is not None:
        if _clear_render_guard_on_load in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(_clear_render_guard_on_load)
        _clear_render_guard_on_load = None

    addon_server.stop_server()
    handlers.unregister()
    ui_panel.unregister()


if __name__ == "__main__":
    register()
