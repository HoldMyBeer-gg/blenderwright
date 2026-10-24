"""Tests for keyframe_property: keyframe any animatable property."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.animation import keyframe_property
from blenderwright.validators import ValidationError

BASE_COLOR = 'active_material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value'


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.animation.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_material_colour(mock_conn):
    keyframe_property(BASE_COLOR, frame=24, value=[1, 0, 0, 1], object_name="Cube")
    assert _sent(mock_conn) == ("keyframe_property", {
        "target": "OBJECT", "object_name": "Cube", "data_path": BASE_COLOR, "frame": 24,
        "index": -1, "value": [1.0, 0.0, 0.0, 1.0]})


def test_world_without_object(mock_conn):
    keyframe_property('node_tree.nodes["Background"].inputs["Strength"].default_value',
                      frame=1, value=0.2, target="WORLD")
    params = _sent(mock_conn)[1]
    assert params["target"] == "WORLD" and "object_name" not in params


def test_key_current_value(mock_conn):
    keyframe_property("data.energy", frame=5, object_name="Lamp")
    assert "value" not in _sent(mock_conn)[1]


@pytest.mark.parametrize("kwargs", [
    {"target": "OBJECT"},
    {"target": "CAMERA", "object_name": "Cam"},
    {"object_name": "Cube", "value": float("nan")},
    {"object_name": "Cube", "value": [1, 2, 3, 4, 5]},
    {"object_name": "Cube", "value": "red"},
    {"object_name": "Cube", "index": 4},
    {"object_name": "Cube", "data_path": "__class__"},
    {"object_name": "Cube", "frame": 2_000_000},
])
def test_rejects(mock_conn, kwargs):
    args = {"data_path": "location", "frame": 1, **kwargs}
    with pytest.raises(ValidationError):
        keyframe_property(**args)
    mock_conn.send_command.assert_not_called()
