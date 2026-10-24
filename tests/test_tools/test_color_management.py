"""Tests for set_color_management and set_film.

Allowed values were read from a live Blender 5.2.3: view transforms, display
devices and looks are dynamic enums there, so RNA introspection shows nothing.
"""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.rendering import (
    ALLOWED_DISPLAY_DEVICES,
    ALLOWED_LOOKS,
    ALLOWED_VIEW_TRANSFORMS,
    set_color_management,
    set_film,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"view_transform": "AgX"}}
    with patch("blenderwright.tools.rendering.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0][1]


class TestAllowlistsMatchBlender52:
    def test_view_transforms(self):
        assert ALLOWED_VIEW_TRANSFORMS == {
            "Standard", "ACES 1.3", "ACES 2.0", "Khronos PBR Neutral", "AgX",
            "Filmic", "Filmic Log", "False Color", "Raw",
        }

    def test_display_devices(self):
        assert ALLOWED_DISPLAY_DEVICES == {
            "sRGB", "Display P3", "Rec.1886", "Rec.2020", "Rec.2100-PQ", "Rec.2100-HLG",
        }

    def test_looks_are_short_names(self):
        assert "Punchy" in ALLOWED_LOOKS and "High Contrast" in ALLOWED_LOOKS
        assert "None" in ALLOWED_LOOKS
        assert not any(" - " in look for look in ALLOWED_LOOKS)


class TestSetColorManagement:
    def test_sends_only_what_was_given(self, mock_conn):
        set_color_management(view_transform="AgX", look="Punchy")
        assert _sent(mock_conn) == {"view_transform": "AgX", "look": "Punchy"}

    def test_nothing_given_sends_nothing(self, mock_conn):
        set_color_management()
        assert _sent(mock_conn) == {}

    def test_exposure_gamma_display_and_white_balance(self, mock_conn):
        set_color_management(exposure=1.5, gamma=1.2, display_device="Display P3",
                             white_balance_temperature=5000)
        assert _sent(mock_conn) == {
            "exposure": 1.5, "gamma": 1.2, "display_device": "Display P3",
            "white_balance_temperature": 5000.0,
        }

    @pytest.mark.parametrize("kwargs", [
        {"view_transform": "Filmic2"},
        {"look": "AgX - Punchy"},
        {"look": "Sepia"},
        {"display_device": "Rec.709"},
        {"exposure": 11},
        {"exposure": float("nan")},
        {"gamma": -0.1},
        {"gamma": 5.1},
        {"white_balance_temperature": 1000},
    ])
    def test_rejects_bad_values(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_color_management(**kwargs)
        mock_conn.send_command.assert_not_called()

    def test_blender_error_is_raised(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "nope"}
        with pytest.raises(RuntimeError, match="nope"):
            set_color_management(view_transform="AgX")


class TestSetFilm:
    def test_transparent_background(self, mock_conn):
        set_film(transparent=True)
        assert _sent(mock_conn) == {"transparent": True}

    def test_glass_and_filter(self, mock_conn):
        set_film(transparent=True, transparent_glass=True, filter_width=1.5)
        assert _sent(mock_conn) == {
            "transparent": True, "transparent_glass": True, "filter_width": 1.5,
        }

    def test_rejects_bad_filter_width(self, mock_conn):
        with pytest.raises(ValidationError):
            set_film(filter_width=20)
