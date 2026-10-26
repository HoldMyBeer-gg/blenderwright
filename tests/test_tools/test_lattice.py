"""Tool-side tests for create_lattice and move_lattice_points.

Behaviour in Blender is covered in tests_live/test_lattice.py.
"""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.deform import create_lattice, move_lattice_points
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.deform.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestCreateLattice:
    def test_defaults(self, mock_conn):
        create_lattice("Vase")
        assert _sent(mock_conn) == ("create_lattice", {
            "object_name": "Vase", "resolution": [2, 2, 2], "interpolation": "KEY_LINEAR"})

    def test_named_and_finer(self, mock_conn):
        create_lattice("Vase", resolution=[3, 3, 5], interpolation="KEY_BSPLINE",
                       lattice_name="Cage")
        assert _sent(mock_conn)[1]["resolution"] == [3, 3, 5]
        assert _sent(mock_conn)[1]["lattice_name"] == "Cage"

    @pytest.mark.parametrize("kwargs", [
        {"resolution": [1, 2, 2]}, {"resolution": [2, 2, 65]}, {"resolution": [2, 2]},
        {"resolution": [2.5, 2, 2]}, {"interpolation": "CUBIC"}, {"lattice_name": "x\x00"},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            create_lattice("Vase", **kwargs)
        mock_conn.send_command.assert_not_called()


class TestMoveLatticePoints:
    def test_taper_the_top(self, mock_conn):
        move_lattice_points("Cage", scale=[0.2, 0.2, 1], axis="Z", sign="POS")
        assert _sent(mock_conn) == ("move_lattice_points", {
            "lattice_name": "Cage", "scale": [0.2, 0.2, 1], "axis": "Z", "sign": "POS"})

    def test_offset_by_index(self, mock_conn):
        move_lattice_points("Cage", offset=[0, 0, 0.5], point_indices=[4, 4, 1])
        assert _sent(mock_conn)[1] == {"lattice_name": "Cage", "offset": [0, 0, 0.5],
                                       "point_indices": [4, 1]}

    def test_reset(self, mock_conn):
        move_lattice_points("Cage", reset=True)
        assert _sent(mock_conn)[1] == {"lattice_name": "Cage", "reset": True}

    @pytest.mark.parametrize("kwargs", [
        {},
        {"offset": [0, 0]},
        {"scale": [0, 1, 1]},
        {"scale": [101, 1, 1]},
        {"offset": [0, 0, 1e9]},
        {"offset": [0, 0, 1], "axis": "W"},
        {"offset": [0, 0, 1], "sign": "UP", "axis": "Z"},
        {"offset": [0, 0, 1], "axis": "Z", "point_indices": [0]},
        {"offset": [0, 0, 1], "point_indices": [-1]},
        {"reset": True, "offset": [0, 0, 1]},
        {"reset": "yes"},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            move_lattice_points("Cage", **kwargs)
        mock_conn.send_command.assert_not_called()
