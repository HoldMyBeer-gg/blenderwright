"""Unit tests for modeling tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.modeling import (
    add_modifier,
    remove_modifier,
    apply_modifier,
    set_modifier_property,
    boolean_operation,
    subdivide_mesh,
    extrude_faces,
    bevel_edges,
    loop_cut,
    set_smooth_shading,
    merge_vertices,
    separate_mesh,
    bridge_edge_loops,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.modeling.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# add_modifier
# ---------------------------------------------------------------------------


class TestAddModifier:
    def test_valid(self, mock_conn):
        add_modifier("Cube", "SUBSURF")
        mock_conn.send_command.assert_called_once_with(
            "add_modifier",
            {"object_name": "Cube", "modifier_type": "SUBSURF", "name": ""},
        )

    def test_with_custom_name(self, mock_conn):
        add_modifier("Cube", "MIRROR", name="MyMirror")
        args = mock_conn.send_command.call_args[0][1]
        assert args["name"] == "MyMirror"
        assert args["modifier_type"] == "MIRROR"

    def test_all_valid_types(self, mock_conn):
        valid_types = [
            "SUBSURF", "MIRROR", "ARRAY", "BEVEL", "BOOLEAN", "SOLIDIFY",
            "DECIMATE", "REMESH",
        ]
        for t in valid_types:
            mock_conn.send_command.reset_mock()
            add_modifier("Cube", t)
            assert mock_conn.send_command.called

    def test_invalid_type_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_modifier("Cube", "FAKE_MODIFIER")

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_modifier("", "SUBSURF")

    def test_invalid_custom_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            add_modifier("Cube", "SUBSURF", name="bad;name")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            add_modifier("Cube", "SUBSURF")


# ---------------------------------------------------------------------------
# remove_modifier
# ---------------------------------------------------------------------------


class TestRemoveModifier:
    def test_valid(self, mock_conn):
        remove_modifier("Cube", "Subdivision")
        mock_conn.send_command.assert_called_once_with(
            "remove_modifier",
            {"object_name": "Cube", "modifier_name": "Subdivision"},
        )

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            remove_modifier("", "Subdivision")

    def test_empty_modifier_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            remove_modifier("Cube", "")


# ---------------------------------------------------------------------------
# apply_modifier
# ---------------------------------------------------------------------------


class TestApplyModifier:
    def test_valid(self, mock_conn):
        apply_modifier("Cube", "Subdivision")
        mock_conn.send_command.assert_called_once_with(
            "apply_modifier",
            {"object_name": "Cube", "modifier_name": "Subdivision"},
        )

    def test_empty_names_raise(self, mock_conn):
        with pytest.raises(ValidationError):
            apply_modifier("", "Subdivision")
        with pytest.raises(ValidationError):
            apply_modifier("Cube", "")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            apply_modifier("Cube", "Subdivision")


# ---------------------------------------------------------------------------
# set_modifier_property
# ---------------------------------------------------------------------------


class TestSetModifierProperty:
    def test_valid(self, mock_conn):
        set_modifier_property("Cube", "Subdivision", "levels", 3)
        mock_conn.send_command.assert_called_once_with(
            "set_modifier_property",
            {
                "object_name": "Cube",
                "modifier_name": "Subdivision",
                "property": "levels",
                "value": 3,
            },
        )

    def test_empty_property_raises(self, mock_conn):
        with pytest.raises(ValidationError, match="property must be a non-empty string"):
            set_modifier_property("Cube", "Subdivision", "", 3)

    def test_non_string_property_raises(self, mock_conn):
        with pytest.raises(ValidationError, match="property must be a non-empty string"):
            set_modifier_property("Cube", "Subdivision", None, 3)

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_modifier_property("", "Subdivision", "levels", 3)


# ---------------------------------------------------------------------------
# boolean_operation
# ---------------------------------------------------------------------------


class TestBooleanOperation:
    def test_valid_difference(self, mock_conn):
        boolean_operation("Cube", "Sphere", "DIFFERENCE")
        mock_conn.send_command.assert_called_once_with(
            "boolean_operation",
            {"object_name": "Cube", "target_name": "Sphere", "operation": "DIFFERENCE"},
        )

    def test_valid_union(self, mock_conn):
        boolean_operation("Cube", "Sphere", "UNION")
        args = mock_conn.send_command.call_args[0][1]
        assert args["operation"] == "UNION"

    def test_valid_intersect(self, mock_conn):
        boolean_operation("Cube", "Sphere", "INTERSECT")
        args = mock_conn.send_command.call_args[0][1]
        assert args["operation"] == "INTERSECT"

    def test_invalid_operation_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            boolean_operation("Cube", "Sphere", "XOR")

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            boolean_operation("", "Sphere", "DIFFERENCE")

    def test_empty_target_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            boolean_operation("Cube", "", "DIFFERENCE")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            boolean_operation("Cube", "Sphere")


# ---------------------------------------------------------------------------
# subdivide_mesh
# ---------------------------------------------------------------------------


class TestSubdivideMesh:
    def test_valid_default(self, mock_conn):
        subdivide_mesh("Cube")
        mock_conn.send_command.assert_called_once_with(
            "subdivide_mesh", {"object_name": "Cube", "cuts": 1}
        )

    def test_valid_custom_cuts(self, mock_conn):
        subdivide_mesh("Cube", cuts=5)
        args = mock_conn.send_command.call_args[0][1]
        assert args["cuts"] == 5

    def test_cuts_too_low_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            subdivide_mesh("Cube", cuts=0)

    def test_cuts_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            subdivide_mesh("Cube", cuts=101)

    def test_non_numeric_cuts_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            subdivide_mesh("Cube", cuts="many")


# ---------------------------------------------------------------------------
# extrude_faces
# ---------------------------------------------------------------------------


class TestExtrudeFaces:
    def test_valid_default(self, mock_conn):
        extrude_faces("Cube")
        mock_conn.send_command.assert_called_once_with(
            "extrude_faces", {"object_name": "Cube", "offset": 1.0}
        )

    def test_custom_offset(self, mock_conn):
        extrude_faces("Cube", offset=2.5)
        args = mock_conn.send_command.call_args[0][1]
        assert args["offset"] == 2.5

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            extrude_faces("")


# ---------------------------------------------------------------------------
# bevel_edges
# ---------------------------------------------------------------------------


class TestBevelEdges:
    def test_valid_defaults(self, mock_conn):
        bevel_edges("Cube")
        mock_conn.send_command.assert_called_once_with(
            "bevel_edges", {"object_name": "Cube", "width": 0.1, "segments": 1}
        )

    def test_custom_params(self, mock_conn):
        bevel_edges("Cube", width=0.5, segments=3)
        args = mock_conn.send_command.call_args[0][1]
        assert args["width"] == 0.5
        assert args["segments"] == 3

    def test_negative_width_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            bevel_edges("Cube", width=-0.1)

    def test_segments_too_low_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            bevel_edges("Cube", segments=0)

    def test_segments_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            bevel_edges("Cube", segments=101)


# ---------------------------------------------------------------------------
# loop_cut
# ---------------------------------------------------------------------------


class TestLoopCut:
    def test_valid_default(self, mock_conn):
        loop_cut("Cube")
        mock_conn.send_command.assert_called_once_with(
            "loop_cut", {"object_name": "Cube", "cuts": 1}
        )

    def test_custom_cuts(self, mock_conn):
        loop_cut("Cube", cuts=10)
        args = mock_conn.send_command.call_args[0][1]
        assert args["cuts"] == 10

    def test_cuts_too_low_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            loop_cut("Cube", cuts=0)

    def test_cuts_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            loop_cut("Cube", cuts=101)

    def test_non_numeric_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            loop_cut("Cube", cuts="ten")


# ---------------------------------------------------------------------------
# set_smooth_shading
# ---------------------------------------------------------------------------


class TestSetSmoothShading:
    def test_smooth_true(self, mock_conn):
        set_smooth_shading("Cube", smooth=True)
        mock_conn.send_command.assert_called_once_with(
            "set_smooth_shading", {"object_name": "Cube", "smooth": True}
        )

    def test_smooth_false(self, mock_conn):
        set_smooth_shading("Cube", smooth=False)
        args = mock_conn.send_command.call_args[0][1]
        assert args["smooth"] is False

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_smooth_shading("")


# ---------------------------------------------------------------------------
# merge_vertices
# ---------------------------------------------------------------------------


class TestMergeVertices:
    def test_valid_default(self, mock_conn):
        merge_vertices("Cube")
        mock_conn.send_command.assert_called_once_with(
            "merge_vertices", {"object_name": "Cube", "threshold": 0.0001}
        )

    def test_custom_threshold(self, mock_conn):
        merge_vertices("Cube", threshold=0.01)
        args = mock_conn.send_command.call_args[0][1]
        assert args["threshold"] == 0.01

    def test_threshold_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            merge_vertices("Cube", threshold=11.0)

    def test_threshold_negative_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            merge_vertices("Cube", threshold=-0.01)

    def test_non_numeric_threshold_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            merge_vertices("Cube", threshold="small")


# ---------------------------------------------------------------------------
# separate_mesh
# ---------------------------------------------------------------------------


class TestSeparateMesh:
    def test_valid_default(self, mock_conn):
        separate_mesh("Cube")
        mock_conn.send_command.assert_called_once_with(
            "separate_mesh", {"object_name": "Cube", "type": "SELECTED"}
        )

    def test_material_type(self, mock_conn):
        separate_mesh("Cube", type="MATERIAL")
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "MATERIAL"

    def test_loose_type(self, mock_conn):
        separate_mesh("Cube", type="LOOSE")
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "LOOSE"

    def test_invalid_type_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            separate_mesh("Cube", type="VERTEX")

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            separate_mesh("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            separate_mesh("Cube")


# ---------------------------------------------------------------------------
# bridge_edge_loops
# ---------------------------------------------------------------------------


class TestBridgeEdgeLoops:
    def test_valid_defaults(self, mock_conn):
        bridge_edge_loops("Cube")
        mock_conn.send_command.assert_called_once_with(
            "bridge_edge_loops",
            {"object_name": "Cube", "segments": 1, "profile_shape_factor": 0.0},
        )

    def test_custom_segments(self, mock_conn):
        bridge_edge_loops("Cube", segments=4)
        args = mock_conn.send_command.call_args[0][1]
        assert args["segments"] == 4

    def test_custom_profile(self, mock_conn):
        bridge_edge_loops("Cube", profile_shape_factor=0.5)
        args = mock_conn.send_command.call_args[0][1]
        assert args["profile_shape_factor"] == 0.5

    def test_segments_too_low_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            bridge_edge_loops("Cube", segments=0)

    def test_segments_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            bridge_edge_loops("Cube", segments=1001)

    def test_profile_too_low_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            bridge_edge_loops("Cube", profile_shape_factor=-1.1)

    def test_profile_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            bridge_edge_loops("Cube", profile_shape_factor=1.1)

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            bridge_edge_loops("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            bridge_edge_loops("Cube")
