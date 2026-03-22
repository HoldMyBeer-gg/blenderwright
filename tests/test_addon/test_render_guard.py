"""Unit tests for render guard (render state tracking)."""

import pytest
from addon.render_guard import RenderGuard


class TestRenderGuard:
    def test_not_rendering_initially(self):
        guard = RenderGuard()
        assert not guard.is_rendering

    def test_on_render_pre_sets_rendering(self):
        guard = RenderGuard()
        guard.on_render_pre(None)
        assert guard.is_rendering

    def test_on_render_complete_clears_rendering(self):
        guard = RenderGuard()
        guard.on_render_pre(None)
        assert guard.is_rendering
        guard.on_render_complete(None)
        assert not guard.is_rendering

    def test_on_render_cancel_clears_rendering(self):
        guard = RenderGuard()
        guard.on_render_pre(None)
        assert guard.is_rendering
        guard.on_render_cancel(None)
        assert not guard.is_rendering

    def test_complete_without_pre_is_safe(self):
        guard = RenderGuard()
        guard.on_render_complete(None)
        assert not guard.is_rendering

    def test_cancel_without_pre_is_safe(self):
        guard = RenderGuard()
        guard.on_render_cancel(None)
        assert not guard.is_rendering

    def test_thread_safe_access(self):
        """is_rendering can be read from any thread safely."""
        import threading

        guard = RenderGuard()
        guard.on_render_pre(None)
        results = []

        def check():
            results.append(guard.is_rendering)

        t = threading.Thread(target=check)
        t.start()
        t.join()
        assert results == [True]
