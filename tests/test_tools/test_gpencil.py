"""Unit tests for Annotation tools (Blender 5.x)."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.gpencil import (
    create_annotation,
    add_annotation_layer,
    remove_annotation_layer,
    add_annotation_stroke,
    set_annotation_stroke_property,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.gpencil.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# create_annotation
# ---------------------------------------------------------------------------


class TestCreateAnnotation:
    def test_valid_defaults(self, mock_conn):
        create_annotation()
        mock_conn.send_command.assert_called_once_with(
            "create_annotation",
            {"name": ""},
        )

    def test_with_name(self, mock_conn):
        create_annotation(name="MyAnnotation")
        args = mock_conn.send_command.call_args[0][1]
        assert args["name"] == "MyAnnotation"

    def test_create_annotation_sends_correct_command(self, mock_conn):
        """Verify send_command is called with 'create_annotation' command name."""
        create_annotation(name="Test")
        call_args = mock_conn.send_command.call_args[0]
        assert call_args[0] == "create_annotation"
        assert call_args[1]["name"] == "Test"

    def test_invalid_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_annotation(name="bad;name")

    def test_no_location_parameter(self, mock_conn):
        """create_annotation must NOT have a location parameter."""
        import inspect
        from blend_ai.tools.gpencil import create_annotation as fn
        sig = inspect.signature(fn)
        assert "location" not in sig.parameters, (
            "create_annotation must not have a 'location' parameter "
            "(annotations are viewport overlays, not positioned objects)"
        )

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            create_annotation()


# ---------------------------------------------------------------------------
# add_annotation_layer
# ---------------------------------------------------------------------------


class TestAddAnnotationLayer:
    def test_valid(self, mock_conn):
        add_annotation_layer("MyAnnotation", "Lines")
        mock_conn.send_command.assert_called_once_with(
            "add_annotation_layer",
            {"annotation_name": "MyAnnotation", "layer_name": "Lines"},
        )

    def test_empty_annotation_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_annotation_layer("", "Lines")

    def test_empty_layer_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_annotation_layer("MyAnnotation", "")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            add_annotation_layer("MyAnnotation", "Lines")


# ---------------------------------------------------------------------------
# remove_annotation_layer
# ---------------------------------------------------------------------------


class TestRemoveAnnotationLayer:
    def test_valid(self, mock_conn):
        remove_annotation_layer("MyAnnotation", "Lines")
        mock_conn.send_command.assert_called_once_with(
            "remove_annotation_layer",
            {"annotation_name": "MyAnnotation", "layer_name": "Lines"},
        )

    def test_empty_annotation_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            remove_annotation_layer("", "Lines")

    def test_empty_layer_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            remove_annotation_layer("MyAnnotation", "")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            remove_annotation_layer("MyAnnotation", "Lines")


# ---------------------------------------------------------------------------
# add_annotation_stroke
# ---------------------------------------------------------------------------


class TestAddAnnotationStroke:
    def test_valid(self, mock_conn):
        points = [[0, 0, 0], [1, 1, 0], [2, 0, 0]]
        add_annotation_stroke("MyAnnotation", "Lines", points)
        args = mock_conn.send_command.call_args[0][1]
        assert args["annotation_name"] == "MyAnnotation"
        assert args["layer_name"] == "Lines"
        assert len(args["points"]) == 3
        assert args["pressure"] == 1.0

    def test_add_annotation_stroke_no_strength_param(self, mock_conn):
        """The MCP tool function signature must NOT have a 'strength' parameter."""
        import inspect
        from blend_ai.tools.gpencil import add_annotation_stroke as fn
        sig = inspect.signature(fn)
        assert "strength" not in sig.parameters, (
            "add_annotation_stroke must not have 'strength' parameter "
            "(AnnotationStroke has no .strength)"
        )

    def test_add_annotation_stroke_no_strength_in_payload(self, mock_conn):
        """The send_command payload must NOT include 'strength'."""
        points = [[0, 0, 0], [1, 0, 0]]
        add_annotation_stroke("MyAnnotation", "Lines", points)
        args = mock_conn.send_command.call_args[0][1]
        assert "strength" not in args, (
            "Stroke payload must not include 'strength' (AnnotationStroke has no .strength)"
        )

    def test_custom_pressure(self, mock_conn):
        points = [[0, 0, 0], [1, 0, 0]]
        add_annotation_stroke("MyAnnotation", "Lines", points, pressure=0.5)
        args = mock_conn.send_command.call_args[0][1]
        assert args["pressure"] == 0.5

    def test_empty_points_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_annotation_stroke("MyAnnotation", "Lines", [])

    def test_too_many_points_raises(self, mock_conn):
        points = [[0, 0, 0]] * 10001
        with pytest.raises(ValidationError):
            add_annotation_stroke("MyAnnotation", "Lines", points)

    def test_invalid_point_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_annotation_stroke("MyAnnotation", "Lines", [[0, 0]])

    def test_empty_annotation_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_annotation_stroke("", "Lines", [[0, 0, 0]])

    def test_empty_layer_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_annotation_stroke("MyAnnotation", "", [[0, 0, 0]])

    def test_pressure_out_of_range_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_annotation_stroke("MyAnnotation", "Lines", [[0, 0, 0]], pressure=-0.1)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            add_annotation_stroke("MyAnnotation", "Lines", [[0, 0, 0]])


# ---------------------------------------------------------------------------
# set_annotation_stroke_property
# ---------------------------------------------------------------------------


ALLOWED_ANNOTATION_STROKE_PROPERTIES = {"line_width", "material_index", "display_mode"}


class TestSetAnnotationStrokeProperty:
    def test_valid(self, mock_conn):
        set_annotation_stroke_property("MyAnnotation", "Lines", 0, "line_width", 5)
        mock_conn.send_command.assert_called_once_with(
            "set_annotation_stroke_property",
            {
                "annotation_name": "MyAnnotation",
                "layer_name": "Lines",
                "stroke_index": 0,
                "property": "line_width",
                "value": 5,
            },
        )

    def test_invalid_property_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_annotation_stroke_property("MyAnnotation", "Lines", 0, "bad_prop", 5)

    def test_negative_stroke_index_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_annotation_stroke_property("MyAnnotation", "Lines", -1, "line_width", 5)

    def test_empty_annotation_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_annotation_stroke_property("", "Lines", 0, "line_width", 5)

    def test_empty_layer_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_annotation_stroke_property("MyAnnotation", "", 0, "line_width", 5)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_annotation_stroke_property("MyAnnotation", "Lines", 0, "line_width", 5)
