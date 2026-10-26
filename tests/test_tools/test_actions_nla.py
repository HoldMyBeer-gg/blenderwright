"""Tests for actions, the NLA and F-curve modifiers."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.animation import (
    add_fcurve_modifier,
    add_nla_strip,
    list_nla,
    manage_action,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.animation.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestManageAction:
    def test_list(self, mock_conn):
        manage_action("Cube", "LIST")
        assert _sent(mock_conn) == ("manage_action", {"object_name": "Cube",
                                                      "operation": "LIST"})

    def test_assign_shared(self, mock_conn):
        manage_action("Cube.001", "ASSIGN", action_name="Bounce")
        assert _sent(mock_conn)[1] == {"object_name": "Cube.001", "operation": "ASSIGN",
                                       "action_name": "Bounce"}

    @pytest.mark.parametrize("args", [("Cube", "DELETE"), ("Cube", "ASSIGN"),
                                      ("Cube", "NEW"), ("Cube", "ASSIGN", "a\nb")])
    def test_rejects(self, mock_conn, args):
        with pytest.raises(ValidationError):
            manage_action(*args)


class TestNla:
    def test_strip(self, mock_conn):
        add_nla_strip("Cube", "Walk", frame_start=10, repeat=4, blend_type="ADD",
                      extrapolation="HOLD_FORWARD", influence=0.5)
        assert _sent(mock_conn) == ("add_nla_strip", {
            "object_name": "Cube", "action_name": "Walk", "frame_start": 10, "track_name": "",
            "blend_type": "ADD", "repeat": 4.0, "scale": 1.0, "extrapolation": "HOLD_FORWARD",
            "blend_in": 0.0, "blend_out": 0.0, "influence": 0.5})

    @pytest.mark.parametrize("kwargs", [{"blend_type": "SCREEN"}, {"repeat": 0},
                                        {"repeat": 2000}, {"scale": 0}, {"influence": 1.5},
                                        {"extrapolation": "LOOP"}, {"blend_in": -1},
                                        {"track_name": "a\nb"}])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            add_nla_strip("Cube", "Walk", **kwargs)

    def test_list(self, mock_conn):
        list_nla("Cube")
        assert _sent(mock_conn) == ("list_nla", {"object_name": "Cube"})


class TestFcurveModifier:
    def test_cycles(self, mock_conn):
        add_fcurve_modifier("Cube", "location", "CYCLES", index=2)
        assert _sent(mock_conn) == ("add_fcurve_modifier", {
            "object_name": "Cube", "data_path": "location", "index": 2, "modifier": "CYCLES",
            "settings": {}})

    def test_noise_settings(self, mock_conn):
        add_fcurve_modifier("Cube", "rotation_euler", "NOISE",
                            settings={"strength": 0.2, "scale": 8, "phase": 3})
        assert _sent(mock_conn)[1]["settings"] == {"strength": 0.2, "scale": 8, "phase": 3}

    @pytest.mark.parametrize("kwargs", [
        {"modifier": "ENVELOPE"},
        {"modifier": "NOISE", "settings": {"__class__": 1}},
        {"modifier": "NOISE", "settings": {"strength": float("nan")}},
        {"modifier": "CYCLES", "settings": {"mode_after": "x" * 100}},
        {"modifier": "NOISE", "data_path": "location()"},
        {"modifier": "NOISE", "index": 9},
    ])
    def test_rejects(self, mock_conn, kwargs):
        args = {"object_name": "Cube", "data_path": "location", **kwargs}
        with pytest.raises(ValidationError):
            add_fcurve_modifier(**args)
