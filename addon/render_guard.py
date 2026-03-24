"""Render state tracking for the blend-ai addon.

Tracks whether Blender is currently rendering so that the server
can return a "busy" response instead of queueing commands that
will time out while the main thread is blocked.

The flag is set from bpy.app.handlers callbacks on the main thread
and read from the server's background thread — threading.Event
provides the necessary thread safety.
"""

import threading


class RenderGuard:
    """Thread-safe render state tracker."""

    def __init__(self):
        self._rendering = threading.Event()

    @property
    def is_rendering(self) -> bool:
        return self._rendering.is_set()

    def on_render_pre(self, scene) -> None:
        """Called by bpy.app.handlers.render_pre."""
        self._rendering.set()

    def on_render_complete(self, scene) -> None:
        """Called by bpy.app.handlers.render_complete."""
        self._rendering.clear()

    def on_render_cancel(self, scene) -> None:
        """Called by bpy.app.handlers.render_cancel."""
        self._rendering.clear()

    def reset(self) -> bool:
        """Force-clear the render guard.

        Returns:
            True if the guard was stuck (is_rendering was True), False otherwise.
        """
        was_rendering = self._rendering.is_set()
        self._rendering.clear()
        return was_rendering


# Global instance — imported by server.py and registered by __init__.py
render_guard = RenderGuard()
