"""Tests for rendering handler — validates 5.1 API compliance."""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_rendering_handler():
    """Load addon.handlers.rendering directly without triggering addon/handlers/__init__.py."""
    mock_dispatcher = MagicMock()
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "rendering.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.rendering", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.rendering"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def rendering_handler():
    """Provide loaded rendering handler module."""
    return _load_rendering_handler()


def _stub_engine_enum(*names):
    """_resolve_engine reads the live enum; give the bpy mock a real list."""
    bpy = sys.modules["bpy"]
    prop = MagicMock()
    prop.enum_items.keys.return_value = list(names)
    bpy.types.RenderSettings.bl_rna.properties = {"engine": prop}


class TestHandleSetRenderEngine:
    def test_handle_set_render_engine_eevee(self, rendering_handler):
        _stub_engine_enum("BLENDER_EEVEE", "CYCLES", "BLENDER_WORKBENCH")
        """Setting engine to BLENDER_EEVEE assigns the correct 5.1 identifier."""
        import bpy

        result = rendering_handler.handle_set_render_engine({"engine": "BLENDER_EEVEE"})

        assert bpy.context.scene.render.engine == "BLENDER_EEVEE"
        assert "engine" in result

    def test_handle_set_render_engine_cycles(self, rendering_handler):
        _stub_engine_enum("BLENDER_EEVEE", "CYCLES", "BLENDER_WORKBENCH")
        """Setting engine to CYCLES assigns CYCLES."""
        import bpy

        result = rendering_handler.handle_set_render_engine({"engine": "CYCLES"})

        assert bpy.context.scene.render.engine == "CYCLES"
        assert "engine" in result

    def test_handle_set_render_engine_returns_engine(self, rendering_handler):
        _stub_engine_enum("BLENDER_EEVEE", "CYCLES", "BLENDER_WORKBENCH")
        """Return dict contains the 'engine' key."""
        result = rendering_handler.handle_set_render_engine({"engine": "BLENDER_EEVEE"})

        assert "engine" in result


class TestHandleSetRenderResolution:
    def test_handle_set_render_resolution(self, rendering_handler):
        """Setting resolution assigns resolution_x, resolution_y, and percentage."""
        import bpy

        result = rendering_handler.handle_set_render_resolution(
            {"width": 1920, "height": 1080, "percentage": 100}
        )

        assert bpy.context.scene.render.resolution_x == 1920
        assert bpy.context.scene.render.resolution_y == 1080
        assert "resolution_x" in result
        assert "resolution_y" in result


class TestHandleSetRenderSamples:
    def test_handle_set_render_samples_cycles(self, rendering_handler):
        """When engine is CYCLES, scene.cycles.samples is set."""
        import bpy

        bpy.context.scene.render.engine = "CYCLES"
        result = rendering_handler.handle_set_render_samples({"samples": 128})

        assert bpy.context.scene.cycles.samples == 128
        assert "samples" in result

    def test_handle_set_render_samples_eevee(self, rendering_handler):
        """When engine is not CYCLES, scene.eevee.taa_render_samples is set."""
        import bpy

        bpy.context.scene.render.engine = "BLENDER_EEVEE"
        result = rendering_handler.handle_set_render_samples({"samples": 64})

        assert bpy.context.scene.eevee.taa_render_samples == 64
        assert "samples" in result


class TestEngineAliasResolution:
    """Blender renamed EEVEE twice; callers should not have to track that.

    4.2-4.4 call it BLENDER_EEVEE_NEXT, 5.x calls it BLENDER_EEVEE. The
    allowlist previously held only BLENDER_EEVEE, making EEVEE unselectable on
    4.2-4.4, which the README claims to support.
    """

    def _handler(self):
        mod = _load_rendering_handler()
        return mod[0] if isinstance(mod, tuple) else mod

    def _set_available(self, *names):
        bpy = sys.modules["bpy"]
        prop = MagicMock()
        prop.enum_items.keys.return_value = list(names)
        bpy.types.RenderSettings.bl_rna.properties = {"engine": prop}

    def test_exact_name_is_used_when_available(self):
        mod = self._handler()
        self._set_available("BLENDER_EEVEE", "CYCLES")
        assert mod._resolve_engine("CYCLES") == "CYCLES"

    def test_next_maps_to_plain_eevee_on_5x(self):
        mod = self._handler()
        self._set_available("BLENDER_EEVEE", "CYCLES")
        assert mod._resolve_engine("BLENDER_EEVEE_NEXT") == "BLENDER_EEVEE"

    def test_plain_eevee_maps_to_next_on_4x(self):
        mod = self._handler()
        self._set_available("BLENDER_EEVEE_NEXT", "CYCLES")
        assert mod._resolve_engine("BLENDER_EEVEE") == "BLENDER_EEVEE_NEXT"

    def test_unknown_engine_lists_what_is_available(self):
        mod = self._handler()
        self._set_available("BLENDER_EEVEE", "CYCLES")
        with pytest.raises(ValueError) as exc:
            mod._resolve_engine("OCTANE")
        assert "CYCLES" in str(exc.value)
