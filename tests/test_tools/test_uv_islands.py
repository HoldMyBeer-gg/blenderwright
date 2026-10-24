"""Tests for UV island operations and texel density."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.uv import (
    ALLOWED_UV_ISLAND_OPERATIONS,
    get_texel_density,
    set_texel_density,
    uv_island_operation,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.uv.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_operations():
    assert ALLOWED_UV_ISLAND_OPERATIONS == {
        "AVERAGE_SCALE", "MINIMIZE_STRETCH", "ALIGN_ROTATION", "RANDOMIZE",
        "SEAMS_FROM_ISLANDS", "ARRANGE", "WELD"}


class TestIslandOperation:
    def test_defaults_to_whole_mesh(self, mock_conn):
        uv_island_operation("Crate", "AVERAGE_SCALE")
        assert _sent(mock_conn) == ("uv_island_operation", {
            "object_name": "Crate", "operation": "AVERAGE_SCALE", "selection": "ALL"})

    def test_operations_send_only_their_options(self, mock_conn):
        uv_island_operation("Crate", "MINIMIZE_STRETCH", iterations=50, margin=0.2)
        assert _sent(mock_conn)[1] == {"object_name": "Crate", "operation": "MINIMIZE_STRETCH",
                                       "selection": "ALL", "iterations": 50}
        uv_island_operation("Crate", "RANDOMIZE", rotation=0.5, scale_variation=0.1, seed=3)
        assert _sent(mock_conn)[1] == {"object_name": "Crate", "operation": "RANDOMIZE",
                                       "selection": "ALL", "rotation": 0.5,
                                       "scale_variation": 0.1, "offset": 0.0, "seed": 3}
        uv_island_operation("Crate", "ARRANGE", margin=0.02)
        assert _sent(mock_conn)[1]["margin"] == 0.02
        uv_island_operation("Crate", "WELD", threshold=0.001)
        assert _sent(mock_conn)[1]["threshold"] == 0.001

    @pytest.mark.parametrize("kwargs", [
        {"operation": "SHRINK"}, {"operation": "MINIMIZE_STRETCH", "iterations": 0},
        {"operation": "RANDOMIZE", "rotation": 7}, {"operation": "ARRANGE", "margin": 2},
        {"operation": "WELD", "threshold": -1}, {"operation": "AVERAGE_SCALE",
                                                 "selection": "SOME"},
    ])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            uv_island_operation("Crate", **kwargs)


class TestTexelDensity:
    def test_get(self, mock_conn):
        get_texel_density("Crate", texture_size=2048)
        assert _sent(mock_conn) == ("get_texel_density",
                                    {"object_name": "Crate", "texture_size": 2048})

    def test_set(self, mock_conn):
        set_texel_density("Crate", 512, texture_size=1024)
        assert _sent(mock_conn) == ("set_texel_density", {
            "object_name": "Crate", "density": 512.0, "texture_size": 1024})

    @pytest.mark.parametrize("args", [("Crate", 0), ("Crate", -5), ("Crate", 1e7)])
    def test_set_rejects_bad_density(self, mock_conn, args):
        with pytest.raises(ValidationError):
            set_texel_density(*args)

    def test_bad_texture_size(self, mock_conn):
        with pytest.raises(ValidationError):
            get_texel_density("Crate", texture_size=3)
