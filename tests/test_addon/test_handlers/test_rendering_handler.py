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


class _Render52:
    """Blender 5.2: the engine enum is dynamic. RNA introspection lists only
    BLENDER_EEVEE, while assignment accepts every registered engine."""

    LIVE = ("BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES")

    def __init__(self):
        self._engine = "BLENDER_EEVEE"

    @property
    def engine(self):
        return self._engine

    @engine.setter
    def engine(self, value):
        if value not in self.LIVE:
            raise TypeError(f'bpy_struct: item.attr = val: enum "{value}" not found in {self.LIVE}')
        self._engine = value


@pytest.fixture
def render52(monkeypatch):
    import bpy

    render = _Render52()
    monkeypatch.setattr(bpy.context.scene, "render", render)
    return render


class TestHandleSetRenderEngine:
    @pytest.mark.parametrize("engine", ["CYCLES", "BLENDER_WORKBENCH", "BLENDER_EEVEE"])
    def test_every_live_engine_can_be_chosen(self, rendering_handler, render52, engine):
        result = rendering_handler.handle_set_render_engine({"engine": engine})
        assert render52.engine == engine
        assert result == {"engine": engine}

    def test_old_eevee_next_name_maps_to_eevee(self, rendering_handler, render52):
        render52.engine = "CYCLES"
        rendering_handler.handle_set_render_engine({"engine": "BLENDER_EEVEE_NEXT"})
        assert render52.engine == "BLENDER_EEVEE"

    def test_missing_engine_lists_what_blender_offers(self, rendering_handler, render52):
        with pytest.raises(ValueError, match="CYCLES"):
            rendering_handler.handle_set_render_engine({"engine": "OCTANE"})
        assert render52.engine == "BLENDER_EEVEE"


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

    def test_working_space_goes_through_the_operator(self, rendering_handler, view_settings,
                                                      monkeypatch):
        import bpy
        from types import SimpleNamespace

        colorspace = SimpleNamespace(working_space="Linear Rec.709")
        monkeypatch.setattr(bpy.data, "colorspace", colorspace, raising=False)
        calls = []

        def op(working_space, convert_colors):
            calls.append((working_space, convert_colors))
            colorspace.working_space = working_space

        monkeypatch.setattr(bpy.ops.wm, "set_working_color_space", op)
        result = rendering_handler.handle_set_color_management(
            {"working_space": "ACEScg", "convert_colors": False})
        assert calls == [("ACEScg", False)]
        assert result["working_space"] == "ACEScg"

    def test_white_balance_switches_it_on(self, rendering_handler, view_settings):
        rendering_handler.handle_set_color_management({"white_balance_temperature": 5000.0})
        assert view_settings.use_white_balance is True
        assert view_settings.white_balance_temperature == 5000.0

    def test_result_reports_full_state(self, rendering_handler, view_settings, monkeypatch):
        import bpy
        from types import SimpleNamespace

        monkeypatch.setattr(bpy.data, "colorspace",
                            SimpleNamespace(working_space="Linear Rec.709"), raising=False)
        result = rendering_handler.handle_set_color_management({"exposure": 1.0})
        assert result == {
            "view_transform": "AgX", "look": "None", "exposure": 1.0, "gamma": 1.0,
            "display_device": "sRGB", "use_white_balance": False,
            "white_balance_temperature": 6500.0, "working_space": "Linear Rec.709",
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


class TestRenderSettings2:
    def test_ray_visibility(self, rendering_handler, monkeypatch):
        import bpy
        from types import SimpleNamespace

        obj = SimpleNamespace(name="Floor", visible_camera=True, visible_diffuse=True,
                              visible_glossy=True, visible_transmission=True,
                              visible_volume_scatter=True, visible_shadow=True,
                              is_holdout=False, is_shadow_catcher=False)
        monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(get={"Floor": obj}.get))
        result = rendering_handler.handle_set_object_ray_visibility(
            {"object_name": "Floor", "glossy": False, "shadow_catcher": True})
        assert obj.visible_glossy is False and obj.is_shadow_catcher is True
        assert result["glossy"] is False and result["camera"] is True

    def test_ray_visibility_missing_object(self, rendering_handler, monkeypatch):
        import bpy
        from types import SimpleNamespace

        monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(get={}.get))
        with pytest.raises(ValueError, match="Ghost"):
            rendering_handler.handle_set_object_ray_visibility(
                {"object_name": "Ghost", "camera": False})

    def test_eevee_quality_converts_enum_sizes(self, rendering_handler, monkeypatch):
        import bpy
        from types import SimpleNamespace

        eevee = SimpleNamespace(use_raytracing=False, ray_tracing_method="PROBE",
                                use_fast_gi=True, fast_gi_method="GLOBAL_ILLUMINATION",
                                shadow_pool_size="512", shadow_ray_count=1,
                                shadow_step_count=6, volumetric_samples=64,
                                volumetric_tile_size="8", use_volumetric_shadows=False,
                                clamp_surface_direct=0.0, clamp_surface_indirect=10.0)
        monkeypatch.setattr(bpy.context.scene, "eevee", eevee)
        result = rendering_handler.handle_set_eevee_quality(
            {"raytracing": True, "shadow_pool_size": 1536, "volumetric_tile_size": 4,
             "shadow_rays": 2})
        assert (eevee.use_raytracing, eevee.shadow_pool_size, eevee.volumetric_tile_size,
                eevee.shadow_ray_count) == (True, "1536", "4", 2)
        assert result["shadow_pool_size"] == 1536

    def test_render_performance(self, rendering_handler, monkeypatch):
        import bpy
        from types import SimpleNamespace

        render = SimpleNamespace(use_simplify=False, simplify_subdivision_render=6,
                                 use_persistent_data=False, anisotropic_filter="FILTER_2")
        cycles = SimpleNamespace(texture_limit_render="OFF", texture_resolution_render=1.0,
                                 use_auto_tile=True, tile_size=2048)
        monkeypatch.setattr(bpy.context.scene, "render", render)
        monkeypatch.setattr(bpy.context.scene, "cycles", cycles)
        result = rendering_handler.handle_set_render_performance(
            {"simplify": True, "max_subdivision": 2, "texture_limit": "1024",
             "anisotropic_filter": 8})
        assert (render.use_simplify, render.simplify_subdivision_render,
                cycles.texture_limit_render, render.anisotropic_filter) == (
            True, 2, "1024", "FILTER_8")
        assert result["anisotropic_filter"] == 8


class _Named(list):
    """bpy collections of light groups / AOVs: add() renames duplicates."""

    def __init__(self, make):
        super().__init__()
        self._make = make

    def get(self, name):
        return next((x for x in self if x.name == name), None)

    def remove(self, item):
        super().remove(item)


@pytest.fixture
def view_layer(rendering_handler, monkeypatch):
    import bpy
    from types import SimpleNamespace

    lightgroups = _Named(None)
    lightgroups.add = lambda name: (lightgroups.append(SimpleNamespace(
        name=name.replace(".", "_"))), lightgroups[-1])[1]
    aovs = _Named(None)

    def aov_add():
        aovs.append(SimpleNamespace(name="AOV", type="COLOR"))
        return aovs[-1]

    aovs.add = aov_add
    layer = SimpleNamespace(lightgroups=lightgroups, aovs=aovs)
    sun = SimpleNamespace(name="Sun", lightgroup="")
    lamp = SimpleNamespace(name="Lamp", lightgroup="")
    world = SimpleNamespace(name="World", lightgroup="")
    monkeypatch.setattr(bpy.context, "view_layer", layer, raising=False)
    monkeypatch.setattr(bpy.context, "scene", SimpleNamespace(world=world), raising=False)
    monkeypatch.setattr(bpy.data, "objects", {"Sun": sun, "Lamp": lamp})
    return rendering_handler, layer, sun, lamp, world


def _group(handler, group, objects=(), world=False, remove=False):
    return handler.handle_set_light_group({"group": group, "objects": list(objects),
                                           "world": world, "remove": remove})


class TestSetLightGroupHandler:
    def test_creates_and_assigns(self, view_layer):
        h, layer, sun, lamp, world = view_layer
        result = _group(h, "Key", ["Sun"], world=True)
        assert sun.lightgroup == "Key" and world.lightgroup == "Key" and lamp.lightgroup == ""
        assert result["groups"] == [{"name": "Key", "objects": ["Sun"], "world": True}]

    def test_uses_the_name_blender_gave(self, view_layer):
        h, layer, sun, *_ = view_layer
        result = _group(h, "rim.1", ["Sun"])
        assert sun.lightgroup == "rim_1" and result["group"] == "rim_1"

    def test_reuses_existing_group(self, view_layer):
        h, layer, sun, lamp, _ = view_layer
        _group(h, "Key", ["Sun"])
        _group(h, "Key", ["Lamp"])
        assert len(layer.lightgroups) == 1 and lamp.lightgroup == "Key"

    def test_missing_object_assigns_nothing(self, view_layer):
        h, layer, sun, *_ = view_layer
        with pytest.raises(ValueError, match="Ghost"):
            _group(h, "Key", ["Sun", "Ghost"])
        assert sun.lightgroup == "" and len(layer.lightgroups) == 0

    def test_remove_clears_members(self, view_layer):
        h, layer, sun, lamp, world = view_layer
        _group(h, "Key", ["Sun"], world=True)
        result = _group(h, "Key", remove=True)
        assert sun.lightgroup == "" and world.lightgroup == ""
        assert result["groups"] == []

    def test_remove_missing(self, view_layer):
        h, *_ = view_layer
        with pytest.raises(ValueError, match="Key"):
            _group(h, "Key", remove=True)


class TestManageAOVHandler:
    def test_add_and_list(self, view_layer):
        h, layer, *_ = view_layer
        result = h.handle_manage_aov({"action": "ADD", "name": "mask", "type": "VALUE"})
        assert result["aovs"] == [{"name": "mask", "type": "VALUE"}]

    def test_add_existing_refused(self, view_layer):
        h, *_ = view_layer
        h.handle_manage_aov({"action": "ADD", "name": "mask", "type": "VALUE"})
        with pytest.raises(ValueError, match="already"):
            h.handle_manage_aov({"action": "ADD", "name": "mask", "type": "COLOR"})

    def test_remove(self, view_layer):
        h, layer, *_ = view_layer
        h.handle_manage_aov({"action": "ADD", "name": "mask", "type": "VALUE"})
        assert h.handle_manage_aov({"action": "REMOVE", "name": "mask"})["aovs"] == []

    def test_remove_missing(self, view_layer):
        h, *_ = view_layer
        with pytest.raises(ValueError, match="mask"):
            h.handle_manage_aov({"action": "REMOVE", "name": "mask"})
