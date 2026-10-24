"""Tests for rendering handler: validates 5.1 API compliance."""

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


class TestImageOutputAfterVideo:
    """Since 5.0 an image file_format is refused while media_type is VIDEO."""

    def test_set_output_format_switches_to_image_media(self, rendering_handler, video_output_scene):
        result = rendering_handler.handle_set_output_format({"format": "PNG"})

        assert video_output_scene.media_type == "IMAGE"
        assert video_output_scene.file_format == "PNG"
        assert result["format"] == "PNG"

    def test_render_animation_restores_video_output(self, rendering_handler, video_output_scene):
        rendering_handler.handle_render_animation({"filepath": "/tmp/frames/", "format": "PNG"})

        assert video_output_scene.media_type == "VIDEO"
        assert video_output_scene.file_format == "FFMPEG"


class _ViewSettings:
    """Blender 5.2 view settings: looks depend on the view transform."""

    LOOKS = {
        "AgX": {"None", "AgX - Punchy", "AgX - High Contrast"},
        "Standard": {"None", "High Contrast", "Low Contrast"},
        "ACES 2.0": {"None", "ACES 2.0 - Reference Gamut Compression"},
    }

    def __init__(self):
        self._view_transform = "AgX"
        self._look = "None"
        self.exposure = 0.0
        self.gamma = 1.0
        self.use_white_balance = False
        self.white_balance_temperature = 6500.0

    @property
    def view_transform(self):
        return self._view_transform

    @view_transform.setter
    def view_transform(self, value):
        if value not in self.LOOKS:
            raise TypeError(f"enum \"{value}\" not found")
        self._view_transform = value
        self._look = "None"  # Blender resets the look when the transform changes

    @property
    def look(self):
        return self._look

    @look.setter
    def look(self, value):
        if value not in self.LOOKS[self._view_transform]:
            raise TypeError(f"enum \"{value}\" not found in {sorted(self.LOOKS[self._view_transform])}")
        self._look = value


@pytest.fixture
def view_settings():
    import bpy

    vs = _ViewSettings()
    bpy.context.scene.view_settings = vs
    bpy.context.scene.display_settings.display_device = "sRGB"
    return vs


class TestHandleSetColorManagement:
    def test_short_look_is_prefixed_for_agx(self, rendering_handler, view_settings):
        result = rendering_handler.handle_set_color_management(
            {"view_transform": "AgX", "look": "Punchy"})
        assert view_settings.look == "AgX - Punchy"
        assert result["look"] == "AgX - Punchy"

    def test_short_look_is_used_as_is_for_standard(self, rendering_handler, view_settings):
        rendering_handler.handle_set_color_management(
            {"view_transform": "Standard", "look": "High Contrast"})
        assert view_settings.look == "High Contrast"

    def test_look_applies_to_the_current_transform(self, rendering_handler, view_settings):
        rendering_handler.handle_set_color_management({"look": "High Contrast"})
        assert view_settings.look == "AgX - High Contrast"

    def test_look_none_clears_the_look(self, rendering_handler, view_settings):
        view_settings.look = "AgX - Punchy"
        rendering_handler.handle_set_color_management({"look": "None"})
        assert view_settings.look == "None"

    def test_look_wrong_for_transform_names_the_valid_ones(self, rendering_handler,
                                                           view_settings):
        with pytest.raises(ValueError, match="Punchy"):
            rendering_handler.handle_set_color_management(
                {"view_transform": "Standard", "look": "Punchy"})

    def test_white_balance_switches_it_on(self, rendering_handler, view_settings):
        rendering_handler.handle_set_color_management({"white_balance_temperature": 5000.0})
        assert view_settings.use_white_balance is True
        assert view_settings.white_balance_temperature == 5000.0

    def test_result_reports_full_state(self, rendering_handler, view_settings):
        result = rendering_handler.handle_set_color_management({"exposure": 1.0})
        assert result == {
            "view_transform": "AgX", "look": "None", "exposure": 1.0, "gamma": 1.0,
            "display_device": "sRGB", "use_white_balance": False,
            "white_balance_temperature": 6500.0,
        }


class TestHandleSetFilm:
    def test_sets_render_and_cycles_film(self, rendering_handler):
        import bpy

        scene = bpy.context.scene
        scene.render.film_transparent = False
        result = rendering_handler.handle_set_film(
            {"transparent": True, "transparent_glass": True, "filter_width": 1.5})

        assert scene.render.film_transparent is True
        assert scene.cycles.film_transparent_glass is True
        assert scene.cycles.filter_width == 1.5
        assert result["transparent"] is True


class TestRenderQualityHandlers:
    def _cycles(self, monkeypatch):
        import bpy
        from types import SimpleNamespace

        c = SimpleNamespace(
            use_denoising=False, denoiser="OPENIMAGEDENOISE", denoising_quality="HIGH",
            denoising_prefilter="ACCURATE", denoising_input_passes="RGB_ALBEDO_NORMAL",
            denoising_use_gpu=False, use_preview_denoising=False,
            use_adaptive_sampling=True, adaptive_threshold=0.01, adaptive_min_samples=0,
            time_limit=0.0, sample_clamp_direct=0.0, sample_clamp_indirect=10.0,
            use_guiding=False, seed=0, use_animated_seed=False,
            max_bounces=12, diffuse_bounces=4, glossy_bounces=4, transmission_bounces=12,
            volume_bounces=0, transparent_max_bounces=8, caustics_reflective=True,
            caustics_refractive=True, blur_glossy=1.0,
        )
        monkeypatch.setattr(bpy.context.scene, "cycles", c)
        return c

    def test_denoising(self, rendering_handler, monkeypatch):
        c = self._cycles(monkeypatch)
        result = rendering_handler.handle_set_denoising(
            {"enabled": True, "quality": "FAST", "viewport": True})
        assert (c.use_denoising, c.denoising_quality, c.use_preview_denoising) == (
            True, "FAST", True)
        assert result["quality"] == "FAST" and result["enabled"] is True

    def test_denoiser_missing_on_this_machine_is_explained(self, rendering_handler,
                                                           monkeypatch):
        c = self._cycles(monkeypatch)

        class _Strict:
            def __setattr__(self, name, value):
                if name == "denoiser" and value == "OPTIX":
                    raise TypeError('enum "OPTIX" not found in (\'OPENIMAGEDENOISE\')')
                object.__setattr__(self, name, value)

        strict = _Strict()
        strict.__dict__.update(vars(c))
        import bpy
        monkeypatch.setattr(bpy.context.scene, "cycles", strict)
        with pytest.raises(ValueError, match="OPTIX.*not available"):
            rendering_handler.handle_set_denoising({"denoiser": "OPTIX"})

    def test_sampling(self, rendering_handler, monkeypatch):
        c = self._cycles(monkeypatch)
        result = rendering_handler.handle_set_cycles_sampling(
            {"noise_threshold": 0.05, "min_samples": 32, "path_guiding": True, "seed": 3})
        assert (c.adaptive_threshold, c.adaptive_min_samples, c.use_guiding, c.seed) == (
            0.05, 32, True, 3)
        assert result["noise_threshold"] == 0.05

    def test_light_paths(self, rendering_handler, monkeypatch):
        c = self._cycles(monkeypatch)
        result = rendering_handler.handle_set_light_paths(
            {"total": 6, "glossy": 2, "caustics_refractive": False, "filter_glossy": 0.5})
        assert (c.max_bounces, c.glossy_bounces, c.caustics_refractive, c.blur_glossy) == (
            6, 2, False, 0.5)
        assert result["total"] == 6

    def test_motion_blur(self, rendering_handler, monkeypatch):
        import bpy
        from types import SimpleNamespace

        render = SimpleNamespace(use_motion_blur=False, motion_blur_shutter=0.5,
                                 motion_blur_position="CENTER")
        eevee = SimpleNamespace(motion_blur_steps=1)
        monkeypatch.setattr(bpy.context.scene, "render", render)
        monkeypatch.setattr(bpy.context.scene, "eevee", eevee)
        result = rendering_handler.handle_set_motion_blur(
            {"enabled": True, "shutter": 0.25, "position": "END", "eevee_steps": 4})
        assert (render.use_motion_blur, render.motion_blur_shutter,
                render.motion_blur_position, eevee.motion_blur_steps) == (True, 0.25, "END", 4)
        assert result["enabled"] is True

    def test_render_passes_reach_the_right_owner(self, rendering_handler, monkeypatch):
        import bpy
        from types import SimpleNamespace

        vl = SimpleNamespace(
            name="ViewLayer", use_pass_mist=False, use_pass_z=False,
            cycles=SimpleNamespace(use_pass_shadow_catcher=False),
            eevee=SimpleNamespace(use_pass_transparent=False),
        )
        monkeypatch.setattr(bpy.context, "view_layer", vl)
        result = rendering_handler.handle_set_render_passes(
            {"passes": ["mist", "z", "shadow_catcher", "transparent"], "enabled": True})
        assert vl.use_pass_mist and vl.use_pass_z
        assert vl.cycles.use_pass_shadow_catcher and vl.eevee.use_pass_transparent
        assert result["view_layer"] == "ViewLayer"
        assert set(result["changed"]) == {"mist", "z", "shadow_catcher", "transparent"}

    def test_render_pass_outside_the_map_is_refused(self, rendering_handler):
        """The socket can be reached without the tool's allowlist."""
        with pytest.raises(ValueError, match="__class__"):
            rendering_handler.handle_set_render_passes({"passes": ["__class__"]})
