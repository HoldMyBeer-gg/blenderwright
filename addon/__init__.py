"""blend-ai: MCP Server addon for Blender.

This addon runs a TCP socket server inside Blender that receives
commands from the blend-ai MCP server and executes them using
Blender's Python API.
"""

bl_info = {
    "name": "blend-ai",
    "author": "blend-ai",
    "version": (1, 2, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > blend-ai",
    "description": "MCP Server integration for AI-assisted 3D workflows",
    "category": "Interface",
}

# Module-level reference set in register() — holds the @persistent load_post handler
_clear_render_guard_on_load = None


def _purge_submodules_from_cache(pkg_name: str, modules: dict | None = None) -> list[str]:
    """Remove pkg_name's submodules from the module cache.

    Blender's addon disable/enable calls register()/unregister() but does not
    evict cached submodules. Without this purge, editing e.g. handlers/objects.py
    and re-enabling the addon returns the pre-edit bytecode from sys.modules —
    a trap for anyone iterating on handler code. Purging submodules forces a
    fresh import on the next `from . import ...` inside register().

    Important subtlety: clearing sys.modules alone is NOT sufficient. After a
    package is imported, its submodules are also set as attributes on the
    parent package object (e.g. `blend_ai.handlers` as an attribute of the
    `blend_ai` module). The `from . import handlers` statement prefers the
    parent's attribute over a fresh import when both exist — so we must also
    delete the submodule attributes from the parent module, otherwise disable/
    enable keeps returning the cached bytecode.

    The package's own __init__ entry is deliberately left in place; deleting
    the currently-executing module from its own code path is unsafe, and
    re-importing only the children is sufficient for iterative development.

    Args:
        pkg_name: Top-level package name (typically __name__ from the caller).
        modules: Module dict to purge. Defaults to sys.modules.

    Returns:
        List of module names that were removed, for logging/testing.
    """
    import sys as _sys
    if modules is None:
        modules = _sys.modules
    prefix = pkg_name + "."
    to_remove = [name for name in modules if name.startswith(prefix)]
    parent = modules.get(pkg_name)
    for name in to_remove:
        # Also strip the submodule attribute from the parent package, if the
        # submodule is a direct child (e.g. "blend_ai.handlers" but not
        # "blend_ai.handlers.objects" — deeper children hang off intermediate
        # packages that are themselves being purged).
        suffix = name[len(prefix):]
        if parent is not None and "." not in suffix and hasattr(parent, suffix):
            try:
                delattr(parent, suffix)
            except AttributeError:
                pass
        del modules[name]
    return to_remove


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

    # Purge cached submodules so disable → edit → enable picks up edited code.
    _purge_submodules_from_cache(__name__)


if __name__ == "__main__":
    register()
