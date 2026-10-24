"""Tests for force fields, collision and soft body."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.physics import (
    ALLOWED_FIELD_TYPES,
    add_collision,
    add_force_field,
    add_soft_body,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.physics.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_field_types():
    assert ALLOWED_FIELD_TYPES == {"FORCE", "WIND", "VORTEX", "MAGNET", "HARMONIC", "CHARGE",
                                   "LENNARDJ", "TURBULENCE", "DRAG"}


class TestForceField:
    def test_defaults(self, mock_conn):
        add_force_field("WIND")
        assert _sent(mock_conn) == ("add_force_field", {
            "type": "WIND", "name": "", "location": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0], "strength": 1.0, "flow": 0.0, "noise": 0.0,
            "seed": 1, "falloff_type": "SPHERE", "falloff_power": 0.0, "max_distance": 0.0})

    def test_turbulence(self, mock_conn):
        add_force_field("TURBULENCE", name="Gust", strength=5, noise=2.5, max_distance=4)
        params = _sent(mock_conn)[1]
        assert (params["name"], params["strength"], params["noise"],
                params["max_distance"]) == ("Gust", 5.0, 2.5, 4.0)

    @pytest.mark.parametrize("kwargs", [
        {"type": "BOID"}, {"type": "WIND", "strength": 1e9}, {"type": "WIND", "noise": -1},
        {"type": "WIND", "falloff_type": "CONE"}, {"type": "WIND", "max_distance": -1},
        {"type": "WIND", "name": "a/b"}, {"type": "WIND", "location": [0, 0]},
    ])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            add_force_field(**kwargs)


class TestCollision:
    def test_defaults(self, mock_conn):
        add_collision("Floor")
        assert _sent(mock_conn) == ("add_collision", {
            "object_name": "Floor", "thickness": 0.02, "damping": 0.1, "friction": 5.0,
            "stickiness": 0.0, "permeability": 0.0})

    @pytest.mark.parametrize("kwargs", [{"thickness": -0.1}, {"thickness": 2},
                                        {"damping": 1.5}, {"friction": 100},
                                        {"permeability": 2}])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            add_collision("Floor", **kwargs)


class TestSoftBody:
    def test_jelly(self, mock_conn):
        add_soft_body("Jelly", goal=False, mass=2.0, pull=0.9, push=0.9, bend=0.5)
        params = _sent(mock_conn)[1]
        assert params["goal"] is False and params["mass"] == 2.0 and params["bend"] == 0.5

    @pytest.mark.parametrize("kwargs", [{"mass": 0}, {"goal_strength": 1.5},
                                        {"pull": 1.5}, {"bend": 11}, {"damping": -1}])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            add_soft_body("Jelly", **kwargs)
