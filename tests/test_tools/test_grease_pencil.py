"""Tests for Grease Pencil v3 drawing and Line Art."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.gpencil import (
    add_gp_stroke,
    add_lineart,
    create_gp_material,
    create_grease_pencil,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.gpencil.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_create(mock_conn):
    create_grease_pencil("Sketch", location=[0, 0, 1], layer_name="Ink")
    assert _sent(mock_conn) == ("create_grease_pencil", {
        "name": "Sketch", "location": [0.0, 0.0, 1.0], "layer_name": "Ink"})


def test_material(mock_conn):
    create_gp_material("Red", color=[1, 0, 0])
    assert _sent(mock_conn)[1] == {"name": "Red", "color": [1.0, 0.0, 0.0, 1.0]}


def test_material_offers_no_fill():
    """Script-built strokes do not render fills in Blender 5.2 (verified live)."""
    import inspect
    assert "fill_color" not in inspect.signature(create_gp_material).parameters


class TestStroke:
    def test_square(self, mock_conn):
        add_gp_stroke("Sketch", [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], cyclic=True,
                      radius=0.03, material="Red")
        assert _sent(mock_conn) == ("add_gp_stroke", {
            "object_name": "Sketch", "points": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0],
                                                [1.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
            "layer": "", "frame": 1, "radius": [0.03] * 4, "cyclic": True,
            "material": "Red"})

    def test_per_point_radius(self, mock_conn):
        add_gp_stroke("Sketch", [[0, 0, 0], [1, 0, 0], [2, 0, 0]], radius=[0.01, 0.05, 0.01])
        assert _sent(mock_conn)[1]["radius"] == [0.01, 0.05, 0.01]

    @pytest.mark.parametrize("kwargs", [
        {"points": [[0, 0, 0]]}, {"points": [[0, 0]] * 3}, {"points": "0,0,0"},
        {"points": [[0, 0, float("nan")], [1, 0, 0]]},
        {"points": [[0, 0, 0]] * 10001},
        {"points": [[0, 0, 0], [1, 0, 0]], "radius": [0.1]},
        {"points": [[0, 0, 0], [1, 0, 0]], "radius": -1},
        {"points": [[0, 0, 0], [1, 0, 0]], "material": "a\nb"},
    ])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            add_gp_stroke("Sketch", **kwargs)
        mock_conn.send_command.assert_not_called()


class TestLineart:
    def test_scene(self, mock_conn):
        add_lineart()
        assert _sent(mock_conn) == ("add_lineart", {
            "source": "SCENE", "source_name": "", "name": "LineArt", "thickness": 0.01,
            "color": [0.0, 0.0, 0.0, 1.0], "crease_angle": 2.443, "use_intersection": True})

    def test_object(self, mock_conn):
        add_lineart(source="OBJECT", source_name="Suzanne", thickness=0.02)
        assert _sent(mock_conn)[1]["source_name"] == "Suzanne"

    @pytest.mark.parametrize("kwargs", [{"source": "WORLD"}, {"source": "OBJECT"},
                                        {"thickness": 0}, {"crease_angle": 4},
                                        {"color": [2, 0, 0, 1]}])
    def test_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            add_lineart(**kwargs)
