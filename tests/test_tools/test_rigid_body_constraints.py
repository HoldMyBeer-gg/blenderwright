"""Tests for add_rigid_body_constraint and set_rigid_body_world."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.physics import (
    ALLOWED_RBC_TYPES,
    add_rigid_body_constraint,
    set_rigid_body_world,
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


def test_types_match_blender52():
    assert ALLOWED_RBC_TYPES == {"FIXED", "POINT", "HINGE", "SLIDER", "PISTON", "GENERIC",
                                 "GENERIC_SPRING", "MOTOR"}


class TestAddRigidBodyConstraint:
    def test_defaults(self, mock_conn):
        add_rigid_body_constraint("A", "B")
        assert _sent(mock_conn) == ("add_rigid_body_constraint", {
            "object1": "A", "object2": "B", "type": "FIXED", "name": "Constraint",
            "disable_collisions": True, "settings": {},
        })

    def test_hinge_with_placement_breaking_and_limits(self, mock_conn):
        add_rigid_body_constraint(
            "Door", "Frame", type="HINGE", empty_name="Hinge", location=[1, 0, 2],
            rotation=[0, 1.5708, 0], breaking_threshold=50,
            settings={"use_limit_ang_z": True, "limit_ang_z_upper": 1.57})
        _, params = _sent(mock_conn)
        assert params["location"] == [1, 0, 2] and params["rotation"] == [0, 1.5708, 0]
        assert params["breaking_threshold"] == 50
        assert params["settings"] == {"use_limit_ang_z": True, "limit_ang_z_upper": 1.57}

    @pytest.mark.parametrize("kwargs", [
        {"type": "ROPE"},
        {"object2": "A"},
        {"empty_name": "x\x00"},
        {"location": [1, 2]},
        {"rotation": "up"},
        {"breaking_threshold": -1},
        {"disable_collisions": "yes"},
        {"settings": {"__class__": 1}},
        {"settings": {"object1": ["x"]}},
        {"settings": "use_breaking"},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        args = {"object1": "A", "object2": "B"} | kwargs
        with pytest.raises(ValidationError):
            add_rigid_body_constraint(**args)
        mock_conn.send_command.assert_not_called()


class TestSetRigidBodyWorld:
    def test_only_given_settings(self, mock_conn):
        set_rigid_body_world(substeps_per_frame=20, solver_iterations=30)
        assert _sent(mock_conn) == ("set_rigid_body_world",
                                    {"substeps_per_frame": 20, "solver_iterations": 30})

    def test_all(self, mock_conn):
        set_rigid_body_world(enabled=False, time_scale=0.5, use_split_impulse=True)
        assert _sent(mock_conn)[1] == {"enabled": False, "time_scale": 0.5,
                                       "use_split_impulse": True}

    def test_nothing_refused(self, mock_conn):
        with pytest.raises(ValidationError, match="at least one"):
            set_rigid_body_world()

    @pytest.mark.parametrize("kwargs", [
        {"substeps_per_frame": 0}, {"substeps_per_frame": 5000},
        {"solver_iterations": 0}, {"time_scale": -1}, {"time_scale": 1000},
        {"enabled": 1},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_rigid_body_world(**kwargs)
