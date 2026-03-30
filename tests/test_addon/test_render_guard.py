"""Unit tests for render guard (render state tracking)."""

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

    def test_reset_clears_stuck_rendering(self):
        """reset() clears is_rendering when guard is stuck and returns True."""
        guard = RenderGuard()
        guard.on_render_pre(None)
        assert guard.is_rendering
        result = guard.reset()
        assert not guard.is_rendering
        assert result is True

    def test_reset_when_not_rendering_returns_false(self):
        """reset() on a fresh guard returns False and guard stays not-rendering."""
        guard = RenderGuard()
        result = guard.reset()
        assert result is False
        assert not guard.is_rendering

    def test_reset_is_idempotent(self):
        """reset() twice returns True then False."""
        guard = RenderGuard()
        guard.on_render_pre(None)
        first = guard.reset()
        second = guard.reset()
        assert first is True
        assert second is False


class TestLoadPostRecovery:
    """Tests for load_post recovery path — verifies on_render_complete clears stuck guard."""

    def test_on_render_complete_clears_stuck_guard(self):
        """Calling on_render_complete(None) directly clears a stuck render guard."""
        guard = RenderGuard()
        guard.on_render_pre(None)
        assert guard.is_rendering
        guard.on_render_complete(None)
        assert not guard.is_rendering

    def test_on_render_complete_safe_when_not_rendering(self):
        """on_render_complete(None) is safe when guard is not stuck."""
        guard = RenderGuard()
        assert not guard.is_rendering
        guard.on_render_complete(None)
        assert not guard.is_rendering
