"""Unit tests for curve tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"name": "BezierCurve"}}
    with patch("blend_ai.tools.curves.get_connection", return_value=mock):
        yield mock


class TestCreateCurve:
    def test_create_bezier_default(self, mock_conn):
        from blend_ai.tools.curves import create_curve

        result = create_curve()
        mock_conn.send_command.assert_called_once_with("create_curve", {
            "type": "BEZIER",
            "name": "",
            "location": [0, 0, 0],
        })
        assert result == {"name": "BezierCurve"}

    def test_create_nurbs(self, mock_conn):
        from blend_ai.tools.curves import create_curve

        create_curve(type="NURBS", name="MyCurve", location=(1, 2, 3))
        mock_conn.send_command.assert_called_once_with("create_curve", {
            "type": "NURBS",
            "name": "MyCurve",
            "location": [1, 2, 3],
        })

    def test_create_path(self, mock_conn):
        from blend_ai.tools.curves import create_curve

        create_curve(type="PATH")
        mock_conn.send_command.assert_called_once()

    def test_invalid_type(self, mock_conn):
        from blend_ai.tools.curves import create_curve

        with pytest.raises(ValidationError):
            create_curve(type="POLY")

    def test_invalid_location(self, mock_conn):
        from blend_ai.tools.curves import create_curve

        with pytest.raises(ValidationError):
            create_curve(location=(1, 2))


class TestAddCurvePoint:
    def test_add_point(self, mock_conn):
        from blend_ai.tools.curves import add_curve_point

        add_curve_point("BezierCurve", location=(1, 0, 0), handle_type="AUTO")
        mock_conn.send_command.assert_called_once_with("add_curve_point", {
            "curve_name": "BezierCurve",
            "location": [1, 0, 0],
            "handle_type": "AUTO",
        })

    def test_handle_types(self, mock_conn):
        from blend_ai.tools.curves import add_curve_point

        for ht in ("AUTO", "VECTOR", "ALIGNED", "FREE"):
            mock_conn.send_command.reset_mock()
            add_curve_point("BezierCurve", handle_type=ht)
            mock_conn.send_command.assert_called_once()

    def test_invalid_handle_type(self, mock_conn):
        from blend_ai.tools.curves import add_curve_point

        with pytest.raises(ValidationError):
            add_curve_point("BezierCurve", handle_type="SMOOTH")

    def test_invalid_curve_name(self, mock_conn):
        from blend_ai.tools.curves import add_curve_point

        with pytest.raises(ValidationError):
            add_curve_point("", location=(0, 0, 0))


class TestSetCurveProperty:
    def test_set_resolution_u(self, mock_conn):
        from blend_ai.tools.curves import set_curve_property

        set_curve_property("BezierCurve", "resolution_u", 12)
        mock_conn.send_command.assert_called_once_with("set_curve_property", {
            "curve_name": "BezierCurve",
            "property": "resolution_u",
            "value": 12,
        })

    def test_set_fill_mode(self, mock_conn):
        from blend_ai.tools.curves import set_curve_property

        set_curve_property("BezierCurve", "fill_mode", "FULL")
        mock_conn.send_command.assert_called_once()

    def test_invalid_fill_mode(self, mock_conn):
        from blend_ai.tools.curves import set_curve_property

        with pytest.raises(ValidationError):
            set_curve_property("BezierCurve", "fill_mode", "PARTIAL")

    def test_invalid_property_name(self, mock_conn):
        from blend_ai.tools.curves import set_curve_property

        with pytest.raises(ValidationError):
            set_curve_property("BezierCurve", "color", "red")

    def test_resolution_u_out_of_range(self, mock_conn):
        from blend_ai.tools.curves import set_curve_property

        with pytest.raises(ValidationError):
            set_curve_property("BezierCurve", "resolution_u", 0)
        with pytest.raises(ValidationError):
            set_curve_property("BezierCurve", "resolution_u", 1025)

    def test_use_fill_caps_not_bool(self, mock_conn):
        from blend_ai.tools.curves import set_curve_property

        with pytest.raises(ValidationError, match="use_fill_caps must be a boolean"):
            set_curve_property("BezierCurve", "use_fill_caps", 1)

    def test_set_twist_mode_valid(self, mock_conn):
        from blend_ai.tools.curves import set_curve_property

        set_curve_property("BezierCurve", "twist_mode", "MINIMUM")
        mock_conn.send_command.assert_called_once()

    def test_set_twist_mode_invalid(self, mock_conn):
        from blend_ai.tools.curves import set_curve_property

        with pytest.raises(ValidationError):
            set_curve_property("BezierCurve", "twist_mode", "CUSTOM")

    def test_bevel_depth_negative(self, mock_conn):
        from blend_ai.tools.curves import set_curve_property

        with pytest.raises(ValidationError):
            set_curve_property("BezierCurve", "bevel_depth", -0.1)


class TestConvertCurveToMesh:
    def test_convert(self, mock_conn):
        from blend_ai.tools.curves import convert_curve_to_mesh

        convert_curve_to_mesh("BezierCurve")
        mock_conn.send_command.assert_called_once_with("convert_curve_to_mesh", {
            "curve_name": "BezierCurve",
        })

    def test_convert_invalid_name(self, mock_conn):
        from blend_ai.tools.curves import convert_curve_to_mesh

        with pytest.raises(ValidationError):
            convert_curve_to_mesh("")


class TestCreateText:
    def test_create_text_basic(self, mock_conn):
        from blend_ai.tools.curves import create_text

        create_text("Hello World")
        mock_conn.send_command.assert_called_once_with("create_text", {
            "text": "Hello World",
            "name": "",
            "location": [0, 0, 0],
            "size": 1.0,
            "font": "",
        })

    def test_create_text_custom(self, mock_conn):
        from blend_ai.tools.curves import create_text

        create_text("Test", name="MyText", location=(1, 2, 3), size=2.5)
        mock_conn.send_command.assert_called_once_with("create_text", {
            "text": "Test",
            "name": "MyText",
            "location": [1, 2, 3],
            "size": 2.5,
            "font": "",
        })

    def test_create_text_empty_string(self, mock_conn):
        from blend_ai.tools.curves import create_text

        with pytest.raises(ValidationError, match="text must be a non-empty string"):
            create_text("")

    def test_create_text_too_long(self, mock_conn):
        from blend_ai.tools.curves import create_text

        with pytest.raises(ValidationError, match="10000 characters"):
            create_text("x" * 10001)

    def test_create_text_size_out_of_range(self, mock_conn):
        from blend_ai.tools.curves import create_text

        with pytest.raises(ValidationError):
            create_text("Hello", size=0.0)
        with pytest.raises(ValidationError):
            create_text("Hello", size=1001.0)


class TestSwitchCurveDirection:
    def test_valid(self, mock_conn):
        from blend_ai.tools.curves import switch_curve_direction

        result = switch_curve_direction("BezierCurve")
        mock_conn.send_command.assert_called_once_with("switch_curve_direction", {
            "curve_name": "BezierCurve",
        })
        assert result == {"name": "BezierCurve"}

    def test_empty_name_raises(self, mock_conn):
        from blend_ai.tools.curves import switch_curve_direction

        with pytest.raises(ValidationError):
            switch_curve_direction("")

    def test_error_response_raises(self, mock_conn):
        from blend_ai.tools.curves import switch_curve_direction

        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError, match="Blender error"):
            switch_curve_direction("BezierCurve")


class TestSetHandleType:
    def test_valid(self, mock_conn):
        from blend_ai.tools.curves import set_handle_type

        result = set_handle_type("BezierCurve", handle_type="VECTOR")
        mock_conn.send_command.assert_called_once_with("set_handle_type", {
            "curve_name": "BezierCurve",
            "handle_type": "VECTOR",
        })
        assert result == {"name": "BezierCurve"}

    def test_default_handle_type(self, mock_conn):
        from blend_ai.tools.curves import set_handle_type

        set_handle_type("BezierCurve")
        mock_conn.send_command.assert_called_once_with("set_handle_type", {
            "curve_name": "BezierCurve",
            "handle_type": "AUTO",
        })

    def test_empty_name_raises(self, mock_conn):
        from blend_ai.tools.curves import set_handle_type

        with pytest.raises(ValidationError):
            set_handle_type("")

    def test_invalid_handle_type_raises(self, mock_conn):
        from blend_ai.tools.curves import set_handle_type

        with pytest.raises(ValidationError):
            set_handle_type("BezierCurve", handle_type="SMOOTH")

    def test_all_valid_handle_types(self, mock_conn):
        from blend_ai.tools.curves import set_handle_type

        for ht in ("AUTO", "VECTOR", "ALIGNED", "FREE_ALIGN"):
            mock_conn.send_command.reset_mock()
            set_handle_type("BezierCurve", handle_type=ht)
            mock_conn.send_command.assert_called_once()

    def test_error_response_raises(self, mock_conn):
        from blend_ai.tools.curves import set_handle_type

        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError, match="Blender error"):
            set_handle_type("BezierCurve")


class TestToggleCyclic:
    def test_valid(self, mock_conn):
        from blend_ai.tools.curves import toggle_cyclic

        result = toggle_cyclic("BezierCurve")
        mock_conn.send_command.assert_called_once_with("toggle_cyclic", {
            "curve_name": "BezierCurve",
        })
        assert result == {"name": "BezierCurve"}

    def test_empty_name_raises(self, mock_conn):
        from blend_ai.tools.curves import toggle_cyclic

        with pytest.raises(ValidationError):
            toggle_cyclic("")

    def test_error_response_raises(self, mock_conn):
        from blend_ai.tools.curves import toggle_cyclic

        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError, match="Blender error"):
            toggle_cyclic("BezierCurve")


class TestSubdivideCurve:
    def test_valid(self, mock_conn):
        from blend_ai.tools.curves import subdivide_curve

        result = subdivide_curve("BezierCurve", number_cuts=3)
        mock_conn.send_command.assert_called_once_with("subdivide_curve", {
            "curve_name": "BezierCurve",
            "number_cuts": 3,
        })
        assert result == {"name": "BezierCurve"}

    def test_default_number_cuts(self, mock_conn):
        from blend_ai.tools.curves import subdivide_curve

        subdivide_curve("BezierCurve")
        mock_conn.send_command.assert_called_once_with("subdivide_curve", {
            "curve_name": "BezierCurve",
            "number_cuts": 1,
        })

    def test_empty_name_raises(self, mock_conn):
        from blend_ai.tools.curves import subdivide_curve

        with pytest.raises(ValidationError):
            subdivide_curve("")

    def test_number_cuts_too_low(self, mock_conn):
        from blend_ai.tools.curves import subdivide_curve

        with pytest.raises(ValidationError):
            subdivide_curve("BezierCurve", number_cuts=0)

    def test_number_cuts_too_high(self, mock_conn):
        from blend_ai.tools.curves import subdivide_curve

        with pytest.raises(ValidationError):
            subdivide_curve("BezierCurve", number_cuts=101)

    def test_error_response_raises(self, mock_conn):
        from blend_ai.tools.curves import subdivide_curve

        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError, match="Blender error"):
            subdivide_curve("BezierCurve")


class TestSmoothCurve:
    def test_valid(self, mock_conn):
        from blend_ai.tools.curves import smooth_curve

        result = smooth_curve("BezierCurve")
        mock_conn.send_command.assert_called_once_with("smooth_curve", {
            "curve_name": "BezierCurve",
        })
        assert result == {"name": "BezierCurve"}

    def test_empty_name_raises(self, mock_conn):
        from blend_ai.tools.curves import smooth_curve

        with pytest.raises(ValidationError):
            smooth_curve("")

    def test_error_response_raises(self, mock_conn):
        from blend_ai.tools.curves import smooth_curve

        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError, match="Blender error"):
            smooth_curve("BezierCurve")


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.curves import create_curve

        mock_conn.send_command.return_value = {"status": "error", "result": "Curve error"}
        with pytest.raises(RuntimeError, match="Blender error"):
            create_curve()
