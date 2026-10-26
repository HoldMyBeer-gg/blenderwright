"""Tests for ray visibility, light linking, EEVEE quality and render performance."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.lighting import set_light_linking
from blenderwright.tools.render_settings import (
    set_eevee_quality,
    set_object_ray_visibility,
    set_render_performance,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.render_settings.get_connection", return_value=mock), \
            patch("blenderwright.tools.lighting.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestRayVisibility:
    def test_sends_only_given(self, mock_conn):
        set_object_ray_visibility("Glass", camera=False, shadow=False)
        assert _sent(mock_conn) == ("set_object_ray_visibility", {
            "object_name": "Glass", "camera": False, "shadow": False})

    def test_catcher_and_holdout(self, mock_conn):
        set_object_ray_visibility("Floor", shadow_catcher=True, holdout=False)
        assert _sent(mock_conn)[1] == {"object_name": "Floor", "shadow_catcher": True,
                                       "holdout": False}

    def test_nothing_given(self, mock_conn):
        with pytest.raises(ValidationError):
            set_object_ray_visibility("Floor")


class TestLightLinking:
    def test_receivers(self, mock_conn):
        set_light_linking("Key", ["Hero", "Hero", "Prop"])
        assert _sent(mock_conn) == ("set_light_linking", {
            "light_name": "Key", "objects": ["Hero", "Prop"], "role": "RECEIVERS",
            "mode": "INCLUDE"})

    def test_blockers_exclude(self, mock_conn):
        set_light_linking("Key", ["Wall"], role="BLOCKERS", mode="EXCLUDE")
        assert _sent(mock_conn)[1]["role"] == "BLOCKERS"
        assert _sent(mock_conn)[1]["mode"] == "EXCLUDE"

    def test_empty_list_clears(self, mock_conn):
        set_light_linking("Key", [])
        assert _sent(mock_conn)[1]["objects"] == []

    @pytest.mark.parametrize("kwargs", [{"role": "EMITTERS"}, {"mode": "ONLY"},
                                        {"objects": "Hero"}, {"objects": ["a\nb"]}])
    def test_rejects(self, mock_conn, kwargs):
        args = {"light_name": "Key", "objects": ["Hero"], **kwargs}
        with pytest.raises(ValidationError):
            set_light_linking(**args)


class TestEeveeQuality:
    def test_sends_only_given(self, mock_conn):
        set_eevee_quality(raytracing=True, ray_tracing_method="SCREEN",
                          shadow_pool_size=1536, fast_gi=True)
        assert _sent(mock_conn) == ("set_eevee_quality", {
            "raytracing": True, "ray_tracing_method": "SCREEN", "shadow_pool_size": 1536,
            "fast_gi": True})

    @pytest.mark.parametrize("kwargs", [
        {"ray_tracing_method": "PATH"}, {"shadow_pool_size": 100},
        {"fast_gi_method": "SSAO"}, {"shadow_rays": 5}, {"shadow_steps": 0},
        {"volumetric_samples": 300}, {"volumetric_tile_size": 3}, {"clamp_direct": -1},
    ])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_eevee_quality(**kwargs)

    def test_nothing_given(self, mock_conn):
        with pytest.raises(ValidationError):
            set_eevee_quality()


class TestRenderPerformance:
    def test_sends_only_given(self, mock_conn):
        set_render_performance(simplify=True, max_subdivision=2, texture_limit="1024",
                               persistent_data=True)
        assert _sent(mock_conn) == ("set_render_performance", {
            "simplify": True, "max_subdivision": 2, "texture_limit": "1024",
            "persistent_data": True})

    @pytest.mark.parametrize("kwargs", [
        {"max_subdivision": 7}, {"texture_limit": "1000"}, {"texture_resolution": 1.5},
        {"tile_size": 4}, {"anisotropic_filter": 3},
    ])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_render_performance(**kwargs)
