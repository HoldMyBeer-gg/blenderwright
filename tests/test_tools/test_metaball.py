"""Tool-side tests for create_metaball. Behaviour: tests_live/test_metaball.py."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.objects import MAX_METABALL_ELEMENTS, create_metaball
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.objects.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_defaults_to_one_ball(mock_conn):
    create_metaball()
    assert _sent(mock_conn) == ("create_metaball", {
        "name": "Metaball", "location": [0, 0, 0], "resolution": 0.2, "threshold": 0.6,
        "elements": [{"type": "BALL", "location": [0, 0, 0], "radius": 1.0,
                      "stiffness": 2.0, "negative": False}]})


def test_elements(mock_conn):
    create_metaball("Blob", elements=[
        {"type": "BALL", "location": [0, 0, 0], "radius": 1},
        {"type": "ELLIPSOID", "location": [1, 0, 0], "size": [1, 0.5, 0.5], "negative": True},
    ])
    elements = _sent(mock_conn)[1]["elements"]
    assert elements[1] == {"type": "ELLIPSOID", "location": [1, 0, 0], "radius": 1.0,
                           "stiffness": 2.0, "negative": True, "size": [1, 0.5, 0.5]}


@pytest.mark.parametrize("kwargs", [
    {"name": "x\x00"},
    {"resolution": 0},
    {"resolution": 5},
    {"threshold": 0},
    {"elements": []},
    {"elements": "ball"},
    {"elements": [{"type": "TORUS"}]},
    {"elements": [{"type": "BALL", "radius": 0}]},
    {"elements": [{"type": "BALL", "stiffness": 11}]},
    {"elements": [{"type": "BALL", "location": [0, 0]}]},
    {"elements": [{"type": "BALL", "size": [1, 1, 1]}]},
    {"elements": [{"type": "CUBE", "size": [0, 1, 1]}]},
    {"elements": [{"type": "BALL", "negative": "yes"}]},
    {"elements": [{"type": "BALL", "colour": 1}]},
    {"elements": [{"type": "BALL"}] * (MAX_METABALL_ELEMENTS + 1)},
])
def test_bad_input(mock_conn, kwargs):
    with pytest.raises(ValidationError):
        create_metaball(**kwargs)
    mock_conn.send_command.assert_not_called()
