"""Unit tests for shader node value-control tools.

Covers the tools that set values *inside* shader nodes: socket defaults,
node-level properties, and ColorRamp stop editing. The pre-existing tools
only build the graph topology; these drive what the nodes actually do.
"""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.materials import (
    set_shader_node_input,
    set_shader_node_property,
    add_color_ramp_element,
    remove_color_ramp_element,
    set_color_ramp_element,
    set_color_ramp_interpolation,
    get_color_ramp,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.materials.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# set_shader_node_input
# ---------------------------------------------------------------------------


class TestSetShaderNodeInput:
    def test_float_value(self, mock_conn):
        set_shader_node_input("Mat", "Noise Texture", "Scale", 5.0)
        mock_conn.send_command.assert_called_once_with(
            "set_shader_node_input",
            {
                "material_name": "Mat",
                "node_name": "Noise Texture",
                "socket": "Scale",
                "value": 5.0,
            },
        )

    def test_socket_by_index(self, mock_conn):
        """Math nodes have two sockets both named 'Value' — index disambiguates."""
        set_shader_node_input("Mat", "Math", 1, 0.5)
        args = mock_conn.send_command.call_args[0][1]
        assert args["socket"] == 1

    def test_socket_index_zero_is_valid(self, mock_conn):
        set_shader_node_input("Mat", "Math", 0, 0.5)
        args = mock_conn.send_command.call_args[0][1]
        assert args["socket"] == 0

    def test_color_value(self, mock_conn):
        set_shader_node_input("Mat", "BSDF", "Base Color", [1.0, 0.2, 0.0, 1.0])
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == [1.0, 0.2, 0.0, 1.0]

    def test_vector_value(self, mock_conn):
        set_shader_node_input("Mat", "Mapping", "Scale", [2.0, 2.0, 1.0])
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == [2.0, 2.0, 1.0]

    def test_bool_value(self, mock_conn):
        set_shader_node_input("Mat", "Node", "Switch", True)
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] is True

    def test_string_value_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_input("Mat", "Node", "Scale", "big")

    def test_dict_value_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_input("Mat", "Node", "Scale", {"a": 1})

    def test_none_value_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_input("Mat", "Node", "Scale", None)

    def test_oversized_vector_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_input("Mat", "Node", "Scale", [1.0, 2.0, 3.0, 4.0, 5.0])

    def test_single_element_vector_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_input("Mat", "Node", "Scale", [1.0])

    def test_non_numeric_vector_component_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_input("Mat", "Node", "Scale", [1.0, "x", 3.0])

    def test_negative_socket_index_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_input("Mat", "Node", -1, 1.0)

    def test_empty_socket_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_input("Mat", "Node", "", 1.0)

    def test_empty_material_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_input("", "Node", "Scale", 1.0)

    def test_empty_node_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_input("Mat", "", "Scale", 1.0)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_shader_node_input("Mat", "Node", "Scale", 1.0)


# ---------------------------------------------------------------------------
# set_shader_node_property
# ---------------------------------------------------------------------------


class TestSetShaderNodePropertyValid:
    def test_math_operation(self, mock_conn):
        set_shader_node_property("Mat", "Math", "operation", "MULTIPLY")
        mock_conn.send_command.assert_called_once_with(
            "set_shader_node_property",
            {
                "material_name": "Mat",
                "node_name": "Math",
                "property": "operation",
                "value": "MULTIPLY",
            },
        )

    def test_mix_blend_type(self, mock_conn):
        set_shader_node_property("Mat", "Mix", "blend_type", "OVERLAY")
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == "OVERLAY"

    def test_voronoi_feature(self, mock_conn):
        set_shader_node_property("Mat", "Voronoi", "feature", "DISTANCE_TO_EDGE")
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == "DISTANCE_TO_EDGE"

    def test_bool_value(self, mock_conn):
        set_shader_node_property("Mat", "Math", "use_clamp", True)
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] is True

    def test_numeric_value(self, mock_conn):
        set_shader_node_property("Mat", "Brick", "offset", 0.5)
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == 0.5


class TestSetShaderNodePropertyInvalid:
    def test_disallowed_property_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_property("Mat", "Node", "bl_idname", "X")

    def test_dunder_property_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_property("Mat", "Node", "__class__", "X")

    def test_unsafe_string_value_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_property("Mat", "Node", "operation", "A;rm -rf /")

    def test_overlong_string_value_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_property("Mat", "Node", "operation", "A" * 65)

    def test_list_value_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_property("Mat", "Node", "operation", ["A"])

    def test_none_value_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_property("Mat", "Node", "operation", None)

    def test_empty_material_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shader_node_property("", "Node", "operation", "ADD")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_shader_node_property("Mat", "Node", "operation", "ADD")


# ---------------------------------------------------------------------------
# add_color_ramp_element
# ---------------------------------------------------------------------------


class TestAddColorRampElement:
    def test_valid_rgba(self, mock_conn):
        add_color_ramp_element("Mat", "ColorRamp", 0.5, [1.0, 0.0, 0.0, 1.0])
        mock_conn.send_command.assert_called_once_with(
            "add_color_ramp_element",
            {
                "material_name": "Mat",
                "node_name": "ColorRamp",
                "position": 0.5,
                "color": [1.0, 0.0, 0.0, 1.0],
            },
        )

    def test_rgb_is_padded_to_rgba(self, mock_conn):
        """RGB input gains a fully-opaque alpha so the wire format is uniform."""
        add_color_ramp_element("Mat", "ColorRamp", 0.5, [1.0, 0.0, 0.0])
        args = mock_conn.send_command.call_args[0][1]
        assert args["color"] == [1.0, 0.0, 0.0, 1.0]

    def test_position_lower_bound(self, mock_conn):
        add_color_ramp_element("Mat", "ColorRamp", 0.0, [0.0, 0.0, 0.0, 1.0])
        args = mock_conn.send_command.call_args[0][1]
        assert args["position"] == 0.0

    def test_position_upper_bound(self, mock_conn):
        add_color_ramp_element("Mat", "ColorRamp", 1.0, [0.0, 0.0, 0.0, 1.0])
        args = mock_conn.send_command.call_args[0][1]
        assert args["position"] == 1.0

    def test_position_above_one_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_color_ramp_element("Mat", "ColorRamp", 1.5, [0.0, 0.0, 0.0, 1.0])

    def test_position_below_zero_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_color_ramp_element("Mat", "ColorRamp", -0.1, [0.0, 0.0, 0.0, 1.0])

    def test_component_above_one_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_color_ramp_element("Mat", "ColorRamp", 0.5, [1.5, 0.0, 0.0, 1.0])

    def test_two_component_color_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_color_ramp_element("Mat", "ColorRamp", 0.5, [1.0, 0.0])

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            add_color_ramp_element("Mat", "ColorRamp", 0.5, [1.0, 0.0, 0.0, 1.0])


# ---------------------------------------------------------------------------
# remove_color_ramp_element
# ---------------------------------------------------------------------------


class TestRemoveColorRampElement:
    def test_valid(self, mock_conn):
        remove_color_ramp_element("Mat", "ColorRamp", 1)
        mock_conn.send_command.assert_called_once_with(
            "remove_color_ramp_element",
            {"material_name": "Mat", "node_name": "ColorRamp", "index": 1},
        )

    def test_index_zero_is_valid(self, mock_conn):
        remove_color_ramp_element("Mat", "ColorRamp", 0)
        args = mock_conn.send_command.call_args[0][1]
        assert args["index"] == 0

    def test_negative_index_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            remove_color_ramp_element("Mat", "ColorRamp", -1)

    def test_non_integer_index_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            remove_color_ramp_element("Mat", "ColorRamp", 1.5)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            remove_color_ramp_element("Mat", "ColorRamp", 0)


# ---------------------------------------------------------------------------
# set_color_ramp_element
# ---------------------------------------------------------------------------


class TestSetColorRampElement:
    def test_position_only(self, mock_conn):
        set_color_ramp_element("Mat", "ColorRamp", 0, position=0.25)
        args = mock_conn.send_command.call_args[0][1]
        assert args["position"] == 0.25
        assert "color" not in args

    def test_color_only(self, mock_conn):
        set_color_ramp_element("Mat", "ColorRamp", 0, color=[0.0, 1.0, 0.0, 1.0])
        args = mock_conn.send_command.call_args[0][1]
        assert args["color"] == [0.0, 1.0, 0.0, 1.0]
        assert "position" not in args

    def test_both(self, mock_conn):
        set_color_ramp_element("Mat", "ColorRamp", 2, position=0.75, color=[0.0, 0.0, 1.0])
        args = mock_conn.send_command.call_args[0][1]
        assert args["position"] == 0.75
        assert args["color"] == [0.0, 0.0, 1.0, 1.0]
        assert args["index"] == 2

    def test_neither_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_color_ramp_element("Mat", "ColorRamp", 0)

    def test_out_of_range_position_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_color_ramp_element("Mat", "ColorRamp", 0, position=2.0)

    def test_negative_index_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_color_ramp_element("Mat", "ColorRamp", -1, position=0.5)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_color_ramp_element("Mat", "ColorRamp", 0, position=0.5)


# ---------------------------------------------------------------------------
# set_color_ramp_interpolation
# ---------------------------------------------------------------------------


class TestSetColorRampInterpolation:
    def test_constant(self, mock_conn):
        set_color_ramp_interpolation("Mat", "ColorRamp", "CONSTANT")
        mock_conn.send_command.assert_called_once_with(
            "set_color_ramp_interpolation",
            {
                "material_name": "Mat",
                "node_name": "ColorRamp",
                "interpolation": "CONSTANT",
            },
        )

    def test_all_valid_modes(self, mock_conn):
        for mode in ("EASE", "CARDINAL", "LINEAR", "B_SPLINE", "CONSTANT"):
            mock_conn.send_command.reset_mock()
            set_color_ramp_interpolation("Mat", "ColorRamp", mode)
            args = mock_conn.send_command.call_args[0][1]
            assert args["interpolation"] == mode

    def test_color_mode_included(self, mock_conn):
        set_color_ramp_interpolation("Mat", "ColorRamp", "LINEAR", color_mode="HSV")
        args = mock_conn.send_command.call_args[0][1]
        assert args["color_mode"] == "HSV"

    def test_color_mode_omitted_when_empty(self, mock_conn):
        set_color_ramp_interpolation("Mat", "ColorRamp", "LINEAR")
        args = mock_conn.send_command.call_args[0][1]
        assert "color_mode" not in args

    def test_invalid_interpolation_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_color_ramp_interpolation("Mat", "ColorRamp", "SMOOTH")

    def test_invalid_color_mode_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_color_ramp_interpolation("Mat", "ColorRamp", "LINEAR", color_mode="CMYK")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_color_ramp_interpolation("Mat", "ColorRamp", "LINEAR")


# ---------------------------------------------------------------------------
# get_color_ramp
# ---------------------------------------------------------------------------


class TestGetColorRamp:
    def test_valid(self, mock_conn):
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": {
                "elements": [
                    {"index": 0, "position": 0.0, "color": [0.0, 0.0, 0.0, 1.0]},
                    {"index": 1, "position": 1.0, "color": [1.0, 1.0, 1.0, 1.0]},
                ],
                "interpolation": "LINEAR",
            },
        }
        result = get_color_ramp("Mat", "ColorRamp")
        mock_conn.send_command.assert_called_once_with(
            "get_color_ramp", {"material_name": "Mat", "node_name": "ColorRamp"}
        )
        assert len(result["elements"]) == 2

    def test_empty_material_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            get_color_ramp("", "ColorRamp")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            get_color_ramp("Mat", "ColorRamp")
