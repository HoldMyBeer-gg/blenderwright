"""Tests for add_essentials_modifier: Blender 5.x's ready-made node modifiers."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.geometry_nodes import (
    ALLOWED_ESSENTIALS_MODIFIERS,
    add_essentials_modifier,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.geometry_nodes.get_connection", return_value=mock):
        yield mock


def test_the_eight_modifier_assets_of_blender_52():
    assert ALLOWED_ESSENTIALS_MODIFIERS == {
        "array", "scatter_on_surface", "instance_on_elements", "randomize_transforms",
        "curve_to_tube", "geometry_input", "smooth_by_angle", "capture_rest_geometry",
    }


def test_sends_modifier_and_settings(mock_conn):
    add_essentials_modifier("Ground", "scatter_on_surface",
                            {"Object": "Rock", "Amount": 50, "Density Method": "Amount"})
    assert mock_conn.send_command.call_args[0] == ("add_essentials_modifier", {
        "object_name": "Ground", "modifier": "scatter_on_surface",
        "settings": {"Object": "Rock", "Amount": 50, "Density Method": "Amount"}})


def test_no_settings(mock_conn):
    add_essentials_modifier("Pipe", "curve_to_tube")
    assert mock_conn.send_command.call_args[0][1]["settings"] == {}


@pytest.mark.parametrize("args", [
    ("Ground", "displace"), ("Gr/ound", "array"), ("Ground", "array", {"Count": float("inf")}),
    ("Ground", "array", "Count=3"),
])
def test_rejects_bad_input(mock_conn, args):
    with pytest.raises(ValidationError):
        add_essentials_modifier(*args)
    mock_conn.send_command.assert_not_called()
