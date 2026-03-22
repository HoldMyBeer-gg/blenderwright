"""Unit tests for Grease Pencil tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.gpencil import (
    create_gpencil_object,
    add_gpencil_layer,
    remove_gpencil_layer,
    add_gpencil_stroke,
    set_gpencil_stroke_property,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.gpencil.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# create_gpencil_object
# ---------------------------------------------------------------------------


class TestCreateGpencilObject:
    def test_valid_defaults(self, mock_conn):
        create_gpencil_object()
        mock_conn.send_command.assert_called_once_with(
            "create_gpencil_object",
            {"name": "", "location": [0, 0, 0]},
        )

    def test_with_name_and_location(self, mock_conn):
        create_gpencil_object(name="MyGP", location=(1, 2, 3))
        args = mock_conn.send_command.call_args[0][1]
        assert args["name"] == "MyGP"
        assert args["location"] == [1, 2, 3]

    def test_invalid_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_gpencil_object(name="bad;name")

    def test_invalid_location_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_gpencil_object(location=(1, 2))

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            create_gpencil_object()


# ---------------------------------------------------------------------------
# add_gpencil_layer
# ---------------------------------------------------------------------------


class TestAddGpencilLayer:
    def test_valid(self, mock_conn):
        add_gpencil_layer("GPObject", "Lines")
        mock_conn.send_command.assert_called_once_with(
            "add_gpencil_layer",
            {"object_name": "GPObject", "layer_name": "Lines"},
        )

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_gpencil_layer("", "Lines")

    def test_empty_layer_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_gpencil_layer("GPObject", "")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            add_gpencil_layer("GPObject", "Lines")


# ---------------------------------------------------------------------------
# remove_gpencil_layer
# ---------------------------------------------------------------------------


class TestRemoveGpencilLayer:
    def test_valid(self, mock_conn):
        remove_gpencil_layer("GPObject", "Lines")
        mock_conn.send_command.assert_called_once_with(
            "remove_gpencil_layer",
            {"object_name": "GPObject", "layer_name": "Lines"},
        )

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            remove_gpencil_layer("", "Lines")

    def test_empty_layer_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            remove_gpencil_layer("GPObject", "")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            remove_gpencil_layer("GPObject", "Lines")


# ---------------------------------------------------------------------------
# add_gpencil_stroke
# ---------------------------------------------------------------------------


class TestAddGpencilStroke:
    def test_valid(self, mock_conn):
        points = [[0, 0, 0], [1, 1, 0], [2, 0, 0]]
        add_gpencil_stroke("GPObject", "Lines", points)
        args = mock_conn.send_command.call_args[0][1]
        assert args["object_name"] == "GPObject"
        assert args["layer_name"] == "Lines"
        assert len(args["points"]) == 3
        assert args["pressure"] == 1.0
        assert args["strength"] == 1.0

    def test_custom_pressure_strength(self, mock_conn):
        points = [[0, 0, 0], [1, 0, 0]]
        add_gpencil_stroke("GPObject", "Lines", points, pressure=0.5, strength=0.8)
        args = mock_conn.send_command.call_args[0][1]
        assert args["pressure"] == 0.5
        assert args["strength"] == 0.8

    def test_empty_points_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_gpencil_stroke("GPObject", "Lines", [])

    def test_too_many_points_raises(self, mock_conn):
        points = [[0, 0, 0]] * 10001
        with pytest.raises(ValidationError):
            add_gpencil_stroke("GPObject", "Lines", points)

    def test_invalid_point_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_gpencil_stroke("GPObject", "Lines", [[0, 0]])

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_gpencil_stroke("", "Lines", [[0, 0, 0]])

    def test_empty_layer_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_gpencil_stroke("GPObject", "", [[0, 0, 0]])

    def test_pressure_out_of_range_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_gpencil_stroke("GPObject", "Lines", [[0, 0, 0]], pressure=-0.1)

    def test_strength_out_of_range_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_gpencil_stroke("GPObject", "Lines", [[0, 0, 0]], strength=1.1)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            add_gpencil_stroke("GPObject", "Lines", [[0, 0, 0]])


# ---------------------------------------------------------------------------
# set_gpencil_stroke_property
# ---------------------------------------------------------------------------


ALLOWED_GP_STROKE_PROPERTIES = {"line_width", "material_index", "display_mode"}


class TestSetGpencilStrokeProperty:
    def test_valid(self, mock_conn):
        set_gpencil_stroke_property("GPObject", "Lines", 0, "line_width", 5)
        mock_conn.send_command.assert_called_once_with(
            "set_gpencil_stroke_property",
            {
                "object_name": "GPObject",
                "layer_name": "Lines",
                "stroke_index": 0,
                "property": "line_width",
                "value": 5,
            },
        )

    def test_invalid_property_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_gpencil_stroke_property("GPObject", "Lines", 0, "bad_prop", 5)

    def test_negative_stroke_index_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_gpencil_stroke_property("GPObject", "Lines", -1, "line_width", 5)

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_gpencil_stroke_property("", "Lines", 0, "line_width", 5)

    def test_empty_layer_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_gpencil_stroke_property("GPObject", "", 0, "line_width", 5)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_gpencil_stroke_property("GPObject", "Lines", 0, "line_width", 5)
