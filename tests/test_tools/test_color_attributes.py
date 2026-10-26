"""Tests for paint_color_attribute and remove_color_attribute."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.deform import paint_color_attribute, remove_color_attribute
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.deform.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestPaintColorAttribute:
    def test_defaults(self, mock_conn):
        paint_color_attribute("Cube", [1, 0, 0])
        assert _sent(mock_conn) == ("paint_color_attribute", {
            "object_name": "Cube", "color": [1, 0, 0, 1.0], "attribute_name": "Color",
            "domain": "CORNER", "data_type": "BYTE_COLOR", "selection": "ALL",
        })

    def test_vertices_and_float_point(self, mock_conn):
        paint_color_attribute("Cube", [0, 0, 1, 0.5], attribute_name="Mask",
                              domain="POINT", data_type="FLOAT_COLOR", vertex_indices=[3, 1, 3])
        _, params = _sent(mock_conn)
        assert params["vertex_indices"] == [3, 1]
        assert params["color"] == [0, 0, 1, 0.5]
        assert (params["domain"], params["data_type"]) == ("POINT", "FLOAT_COLOR")

    @pytest.mark.parametrize("kwargs", [
        {"color": [1, 0]},
        {"color": [2, 0, 0]},
        {"color": "red"},
        {"domain": "FACE"},
        {"data_type": "FLOAT"},
        {"selection": "SOME"},
        {"vertex_indices": [-1]},
        {"vertex_indices": []},
        {"attribute_name": "x\x00"},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        args = {"object_name": "Cube", "color": [1, 1, 1]} | kwargs
        with pytest.raises(ValidationError):
            paint_color_attribute(**args)
        mock_conn.send_command.assert_not_called()

    def test_blender_error_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "nope"}
        with pytest.raises(RuntimeError, match="nope"):
            paint_color_attribute("Cube", [1, 1, 1])


class TestRemoveColorAttribute:
    def test_sends(self, mock_conn):
        remove_color_attribute("Cube", "Mask")
        assert _sent(mock_conn) == ("remove_color_attribute",
                                    {"object_name": "Cube", "attribute_name": "Mask"})

    def test_bad_name(self, mock_conn):
        with pytest.raises(ValidationError):
            remove_color_attribute("Cube", "")
