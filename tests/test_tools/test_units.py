"""Tests for set_units.

Unit names were read from a live Blender 5.2.3. The unit enums are dynamic
there (their RNA lists only DEFAULT), and which names are valid depends on
the unit system.
"""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.scene import UNITS_BY_SYSTEM, set_units
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"system": "METRIC"}}
    with patch("blenderwright.tools.scene.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0][1]


class TestUnitNamesMatchBlender52:
    def test_metric_lengths(self):
        assert UNITS_BY_SYSTEM["METRIC"]["length_unit"] == {
            "ADAPTIVE", "KILOMETERS", "METERS", "CENTIMETERS", "MILLIMETERS", "MICROMETERS",
        }

    def test_imperial_lengths(self):
        assert UNITS_BY_SYSTEM["IMPERIAL"]["length_unit"] == {
            "ADAPTIVE", "MILES", "FEET", "INCHES", "THOU",
        }

    def test_temperatures_follow_system(self):
        assert "CELSIUS" in UNITS_BY_SYSTEM["METRIC"]["temperature_unit"]
        assert "FAHRENHEIT" in UNITS_BY_SYSTEM["IMPERIAL"]["temperature_unit"]


class TestSetUnits:
    def test_sends_only_given_settings(self, mock_conn):
        set_units(system="METRIC", length_unit="CENTIMETERS")
        mock_conn.send_command.assert_called_once_with(
            "set_units", {"system": "METRIC", "length_unit": "CENTIMETERS"}
        )

    def test_scale_and_rotation(self, mock_conn):
        set_units(scale_length=0.01, rotation="RADIANS", use_separate=True)
        assert _sent(mock_conn) == {
            "scale_length": 0.01, "system_rotation": "RADIANS", "use_separate": True,
        }

    def test_nothing_to_set_is_refused(self, mock_conn):
        with pytest.raises(ValidationError, match="at least one"):
            set_units()

    def test_unknown_system(self, mock_conn):
        with pytest.raises(ValidationError):
            set_units(system="NAUTICAL")

    def test_unit_outside_every_system(self, mock_conn):
        with pytest.raises(ValidationError):
            set_units(length_unit="FURLONGS")

    def test_unit_from_the_other_system_is_refused(self, mock_conn):
        with pytest.raises(ValidationError, match="IMPERIAL"):
            set_units(system="METRIC", length_unit="INCHES")

    def test_units_without_system_left_to_blender(self, mock_conn):
        set_units(length_unit="INCHES")
        assert _sent(mock_conn) == {"length_unit": "INCHES"}

    def test_none_system_takes_no_units(self, mock_conn):
        with pytest.raises(ValidationError, match="NONE"):
            set_units(system="NONE", length_unit="METERS")

    @pytest.mark.parametrize("scale", [0, -1, 1e10, float("nan"), "big"])
    def test_bad_scale(self, mock_conn, scale):
        with pytest.raises(ValidationError):
            set_units(scale_length=scale)

    def test_use_separate_must_be_bool(self, mock_conn):
        with pytest.raises(ValidationError):
            set_units(use_separate="yes")

    def test_blender_error_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "nope"}
        with pytest.raises(RuntimeError, match="nope"):
            set_units(system="METRIC")
