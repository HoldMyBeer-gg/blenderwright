"""Tests for set_sculpt_mask and set_face_sets."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.sculpting import (
    ALLOWED_FACE_SET_MODES,
    set_face_sets,
    set_sculpt_mask,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.sculpting.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestSetSculptMask:
    def test_mask_everything(self, mock_conn):
        set_sculpt_mask("Head")
        assert _sent(mock_conn) == ("set_sculpt_mask", {"object_name": "Head", "value": 1.0})

    def test_vertices(self, mock_conn):
        set_sculpt_mask("Head", value=0.5, vertex_indices=[2, 0, 2])
        assert _sent(mock_conn)[1] == {"object_name": "Head", "value": 0.5,
                                       "vertex_indices": [2, 0]}

    def test_from_vertex_group(self, mock_conn):
        set_sculpt_mask("Head", vertex_group="Ears")
        assert _sent(mock_conn)[1]["vertex_group"] == "Ears"

    def test_invert_and_clear(self, mock_conn):
        set_sculpt_mask("Head", invert=True)
        assert _sent(mock_conn)[1] == {"object_name": "Head", "invert": True}
        set_sculpt_mask("Head", clear=True)
        assert _sent(mock_conn)[1] == {"object_name": "Head", "clear": True}

    @pytest.mark.parametrize("kwargs", [
        {"value": 1.5}, {"value": -0.1}, {"value": "full"},
        {"vertex_indices": [-1]}, {"vertex_group": "../x"},
        {"vertex_indices": [0], "vertex_group": "Ears"},
        {"invert": True, "clear": True}, {"invert": "yes"},
        {"clear": True, "vertex_indices": [0]},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_sculpt_mask("Head", **kwargs)
        mock_conn.send_command.assert_not_called()


class TestSetFaceSets:
    def test_modes(self):
        assert ALLOWED_FACE_SET_MODES == {"LOOSE_PARTS", "MATERIALS", "ASSIGN", "CLEAR"}

    def test_loose_parts(self, mock_conn):
        set_face_sets("Head", "LOOSE_PARTS")
        assert _sent(mock_conn) == ("set_face_sets", {"object_name": "Head",
                                                      "mode": "LOOSE_PARTS"})

    def test_assign(self, mock_conn):
        set_face_sets("Head", "ASSIGN", face_indices=[4, 5], face_set=3)
        assert _sent(mock_conn)[1] == {"object_name": "Head", "mode": "ASSIGN",
                                       "face_indices": [4, 5], "face_set": 3}

    @pytest.mark.parametrize("kwargs", [
        {"mode": "RANDOM"},
        {"mode": "ASSIGN"},
        {"mode": "ASSIGN", "face_indices": [1], "face_set": 0},
        {"mode": "ASSIGN", "face_indices": [-2], "face_set": 1},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_face_sets("Head", **kwargs)
