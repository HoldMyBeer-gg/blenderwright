"""Tests for the render quality tools: denoising, sampling, light paths,
motion blur and render passes. Property names and ranges were read from a
live Blender 5.2.3."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.render_settings import (
    ALLOWED_RENDER_PASSES,
    set_cycles_sampling,
    set_denoising,
    set_light_paths,
    set_motion_blur,
    set_render_passes,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.render_settings.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestSetDenoising:
    def test_sends_only_what_was_given(self, mock_conn):
        set_denoising(enabled=True, quality="BALANCED")
        assert _sent(mock_conn) == ("set_denoising", {"enabled": True, "quality": "BALANCED"})

    def test_all_options(self, mock_conn):
        set_denoising(enabled=True, denoiser="OPTIX", quality="HIGH", prefilter="FAST",
                      input_passes="RGB_ALBEDO", use_gpu=True, viewport=True)
        assert _sent(mock_conn)[1] == {
            "enabled": True, "denoiser": "OPTIX", "quality": "HIGH", "prefilter": "FAST",
            "input_passes": "RGB_ALBEDO", "use_gpu": True, "viewport": True,
        }

    @pytest.mark.parametrize("kwargs", [
        {"denoiser": "NLM"}, {"quality": "ULTRA"}, {"prefilter": "SLOW"},
        {"input_passes": "NORMAL"},
    ])
    def test_rejects_unknown_values(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_denoising(**kwargs)
        mock_conn.send_command.assert_not_called()


class TestSetCyclesSampling:
    def test_sends_only_what_was_given(self, mock_conn):
        set_cycles_sampling(noise_threshold=0.02, time_limit=30)
        assert _sent(mock_conn) == ("set_cycles_sampling",
                                    {"noise_threshold": 0.02, "time_limit": 30})

    def test_all_options(self, mock_conn):
        set_cycles_sampling(adaptive=True, noise_threshold=0.01, min_samples=16,
                            time_limit=0, clamp_direct=0, clamp_indirect=10,
                            path_guiding=True, seed=7, animated_seed=True)
        assert _sent(mock_conn)[1] == {
            "adaptive": True, "noise_threshold": 0.01, "min_samples": 16, "time_limit": 0,
            "clamp_direct": 0, "clamp_indirect": 10, "path_guiding": True, "seed": 7,
            "animated_seed": True,
        }

    @pytest.mark.parametrize("kwargs", [
        {"noise_threshold": 1.5}, {"noise_threshold": -0.1}, {"min_samples": 5000},
        {"time_limit": -1}, {"time_limit": 90000}, {"clamp_indirect": -1},
        {"seed": -1}, {"min_samples": 2.5},
    ])
    def test_rejects_out_of_range(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_cycles_sampling(**kwargs)


class TestSetLightPaths:
    def test_bounces_and_caustics(self, mock_conn):
        set_light_paths(total=8, diffuse=2, glossy=3, transmission=8, volume=1,
                        transparent=16, caustics_reflective=False,
                        caustics_refractive=False, filter_glossy=0.5)
        assert _sent(mock_conn) == ("set_light_paths", {
            "total": 8, "diffuse": 2, "glossy": 3, "transmission": 8, "volume": 1,
            "transparent": 16, "caustics_reflective": False,
            "caustics_refractive": False, "filter_glossy": 0.5,
        })

    @pytest.mark.parametrize("kwargs", [
        {"total": 2000}, {"diffuse": -1}, {"filter_glossy": 11}, {"glossy": 1.5},
    ])
    def test_rejects_out_of_range(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_light_paths(**kwargs)


class TestSetMotionBlur:
    def test_all_options(self, mock_conn):
        set_motion_blur(enabled=True, shutter=0.25, position="START", eevee_steps=4)
        assert _sent(mock_conn) == ("set_motion_blur", {
            "enabled": True, "shutter": 0.25, "position": "START", "eevee_steps": 4,
        })

    @pytest.mark.parametrize("kwargs", [
        {"shutter": -0.1}, {"shutter": 3}, {"position": "MIDDLE"}, {"eevee_steps": 0},
        {"eevee_steps": 100},
    ])
    def test_rejects_bad_values(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_motion_blur(**kwargs)


class TestSetRenderPasses:
    def test_enables_listed_passes(self, mock_conn):
        set_render_passes(["mist", "normal", "cryptomatte_object"])
        assert _sent(mock_conn) == ("set_render_passes", {
            "passes": ["mist", "normal", "cryptomatte_object"], "enabled": True,
        })

    def test_disable(self, mock_conn):
        set_render_passes(["z"], enabled=False)
        assert _sent(mock_conn)[1] == {"passes": ["z"], "enabled": False}

    def test_depth_is_an_alias_for_z(self, mock_conn):
        set_render_passes(["depth"])
        assert _sent(mock_conn)[1]["passes"] == ["z"]

    def test_duplicates_are_collapsed(self, mock_conn):
        set_render_passes(["mist", "mist", "depth", "z"])
        assert _sent(mock_conn)[1]["passes"] == ["mist", "z"]

    @pytest.mark.parametrize("passes", [[], ["mist", "bloom"], "mist", [1]])
    def test_rejects_bad_lists(self, mock_conn, passes):
        with pytest.raises(ValidationError):
            set_render_passes(passes)

    def test_allowlist_covers_cryptomatte_and_cycles_extras(self):
        assert {"cryptomatte_object", "cryptomatte_material", "cryptomatte_asset",
                "shadow_catcher", "volume_direct", "transparent"} <= ALLOWED_RENDER_PASSES
