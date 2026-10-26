"""blenderwright: MCP Server addon for Blender.

This addon runs a TCP socket server inside Blender that receives
commands from the blenderwright MCP server and executes them using
Blender's Python API.
"""

bl_info = {
    "name": "blenderwright",
    "author": "blenderwright",
    "version": (3, 1, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > blenderwright",
    "description": "MCP Server integration for AI-assisted 3D workflows",
    "category": "Interface",
}

# (bpy.app.handlers list name, callback) pairs added in register()
_app_handlers = []


def _purge_submodules_from_cache(pkg_name: str, modules: dict | None = None) -> list[str]:
    """Remove pkg_name's submodules from the module cache.

    Blender's addon disable/enable calls register()/unregister() but does not
    evict cached submodules. Without this purge, editing e.g. handlers/objects.py
    and re-enabling the addon returns the pre-edit bytecode from sys.modules,
    a trap for anyone iterating on handler code. Purging submodules forces a
    fresh import on the next `from . import ...` inside register().

    Important subtlety: clearing sys.modules alone is NOT sufficient. After a
    package is imported, its submodules are also set as attributes on the
    parent package object (e.g. `blenderwright.handlers` as an attribute of the
    `blenderwright` module). The `from . import handlers` statement prefers the
    parent's attribute over a fresh import when both exist, so we must also
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
        # submodule is a direct child (e.g. "blenderwright.handlers" but not
        # "blenderwright.handlers.objects", deeper children hang off intermediate
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

    ui_panel.register()
    handlers.register()

    # Track render state so the server can return "busy" during renders.
    # Persistent, or Blender drops them on the first file load.
    @persistent
    def _render_started(scene, *_):
        render_guard.on_render_pre(scene)

    @persistent
    def _render_ended(scene, *_):
        render_guard.on_render_complete(scene)

    _app_handlers[:] = [
        ("render_pre", _render_started),
        ("render_complete", _render_ended),
        ("render_cancel", _render_ended),
        # A file load also clears it: recovers from crashed renders
        ("load_post", _render_ended),
    ]
    for list_name, callback in _app_handlers:
        getattr(bpy.app.handlers, list_name).append(callback)


def unregister():
    import bpy
    from . import ui_panel
    from . import server as addon_server
    from . import handlers

    for list_name, callback in _app_handlers:
        handler_list = getattr(bpy.app.handlers, list_name)
        if callback in handler_list:
            handler_list.remove(callback)
    _app_handlers.clear()

    addon_server.stop_server()
    handlers.unregister()
    ui_panel.unregister()

    # Purge cached submodules so disable → edit → enable picks up edited code.
    _purge_submodules_from_cache(__name__)


if __name__ == "__main__":
    register()
