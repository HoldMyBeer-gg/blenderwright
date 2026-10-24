"""Tests for the compositor tools (Blender 5.x node-group compositor)."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.compositor import (
    ALLOWED_EFFECTS,
    add_compositor_effect,
    list_compositor,
    remove_compositor_effect,
    set_compositor_effect,
    setup_compositor,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.compositor.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_effects_cover_builtin_nodes_and_essentials_assets():
    assert {"glare", "lens_distortion", "color_balance", "denoise", "blur", "exposure",
            "brightness_contrast", "hue_saturation", "kuwahara", "pixelate", "posterize",
            "anti_aliasing"} <= ALLOWED_EFFECTS
    assert {"vignette", "film_grain", "chromatic_aberration", "sepia", "split_toning",
            "sensor_noise", "unsharp_mask", "tune_image"} <= ALLOWED_EFFECTS


class TestSetup:
    def test_setup(self, mock_conn):
        setup_compositor()
        assert _sent(mock_conn) == ("setup_compositor", {"reset": False})

    def test_reset(self, mock_conn):
        setup_compositor(reset=True)
        assert _sent(mock_conn)[1] == {"reset": True}


class TestAddEffect:
    def test_effect_with_settings(self, mock_conn):
        add_compositor_effect("glare", {"Type": "Fog Glow", "Strength": 0.6, "Clamp": True})
        assert _sent(mock_conn) == ("add_compositor_effect", {
            "effect": "glare",
            "settings": {"Type": "Fog Glow", "Strength": 0.6, "Clamp": True},
        })

    def test_vector_and_color_values(self, mock_conn):
        add_compositor_effect("vignette", {"Scale": [0.9, 0.7], "Feather": 0.5})
        assert _sent(mock_conn)[1]["settings"]["Scale"] == [0.9, 0.7]

    def test_no_settings(self, mock_conn):
        add_compositor_effect("film_grain")
        assert _sent(mock_conn)[1] == {"effect": "film_grain", "settings": {}}

    def test_unknown_effect(self, mock_conn):
        with pytest.raises(ValidationError):
            add_compositor_effect("lens_flare")
        mock_conn.send_command.assert_not_called()

    @pytest.mark.parametrize("settings", [
        "Strength=1",
        {"": 1},
        {"x" * 65: 1},
        {"Strength": float("nan")},
        {"Strength": float("inf")},
        {"Strength": None},
        {"Strength": {"nested": 1}},
        {"Scale": [1]},
        {"Scale": [1, 2, 3, 4, 5]},
        {"Scale": [1, "a"]},
        {"Type": "x" * 65},
        {"Bad\nName": 1},
    ])
    def test_rejects_bad_settings(self, mock_conn, settings):
        with pytest.raises(ValidationError):
            add_compositor_effect("glare", settings)
        mock_conn.send_command.assert_not_called()


class TestEditRemoveList:
    def test_set(self, mock_conn):
        set_compositor_effect("Glare", {"Strength": 0.3})
        assert _sent(mock_conn) == ("set_compositor_effect",
                                    {"node_name": "Glare", "settings": {"Strength": 0.3}})

    def test_set_needs_settings(self, mock_conn):
        with pytest.raises(ValidationError):
            set_compositor_effect("Glare", {})

    def test_remove(self, mock_conn):
        remove_compositor_effect("Glare.001")
        assert _sent(mock_conn) == ("remove_compositor_effect", {"node_name": "Glare.001"})

    def test_list(self, mock_conn):
        list_compositor()
        assert _sent(mock_conn) == ("list_compositor", {})

    def test_bad_node_name(self, mock_conn):
        with pytest.raises(ValidationError):
            remove_compositor_effect("../../etc")

    def test_blender_error_raised(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "boom"}
        with pytest.raises(RuntimeError, match="boom"):
            list_compositor()
