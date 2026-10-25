"""Tool-side tests for set_freestyle. Behaviour: tests_live/test_freestyle.py."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.render_settings import ALLOWED_FREESTYLE_EDGES, set_freestyle
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.render_settings.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_edge_types():
    assert ALLOWED_FREESTYLE_EDGES == {
        "SILHOUETTE", "BORDER", "CREASE", "CONTOUR", "EXTERNAL_CONTOUR",
        "MATERIAL_BOUNDARY", "RIDGE_VALLEY", "SUGGESTIVE_CONTOUR", "EDGE_MARK"}


def test_turn_on_with_style(mock_conn):
    set_freestyle(thickness=2.5, color=[0, 0, 0], edges=["SILHOUETTE", "CREASE"],
                  crease_angle=120)
    assert _sent(mock_conn) == ("set_freestyle", {
        "enabled": True, "thickness": 2.5, "color": [0, 0, 0],
        "edges": ["SILHOUETTE", "CREASE"], "crease_angle": 120})


def test_turn_off(mock_conn):
    set_freestyle(enabled=False)
    assert _sent(mock_conn)[1] == {"enabled": False}


@pytest.mark.parametrize("kwargs", [
    {"enabled": "yes"}, {"thickness": 0}, {"thickness": 10001}, {"color": [2, 0, 0]},
    {"edges": "SILHOUETTE"}, {"edges": ["OUTLINE"]}, {"crease_angle": 200},
    {"as_render_pass": 1},
])
def test_bad_input(mock_conn, kwargs):
    with pytest.raises(ValidationError):
        set_freestyle(**kwargs)
    mock_conn.send_command.assert_not_called()
