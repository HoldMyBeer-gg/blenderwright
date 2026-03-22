"""Unit tests for mesh editing tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.mesh_editing import (
    inset_faces,
    fill_faces,
    grid_fill,
    mark_seam,
    mark_sharp,
    recalculate_normals,
    flip_normals,
    quads_to_tris,
    tris_to_quads,
    dissolve_faces,
    dissolve_edges,
    dissolve_verts,
    knife_project,
    spin_mesh,
    set_edge_crease,
    select_linked,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.mesh_editing.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# inset_faces
# ---------------------------------------------------------------------------


class TestInsetFaces:
    def test_valid_defaults(self, mock_conn):
        inset_faces("Cube")
        mock_conn.send_command.assert_called_once_with(
            "inset_faces",
            {"object_name": "Cube", "thickness": 0.1, "depth": 0.0},
        )

    def test_custom_params(self, mock_conn):
        inset_faces("Cube", thickness=0.5, depth=0.2)
        args = mock_conn.send_command.call_args[0][1]
        assert args["thickness"] == 0.5
        assert args["depth"] == 0.2

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            inset_faces("")

    def test_thickness_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            inset_faces("Cube", thickness=11.0)

    def test_thickness_negative_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            inset_faces("Cube", thickness=-0.1)

    def test_depth_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            inset_faces("Cube", depth=11.0)

    def test_depth_too_low_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            inset_faces("Cube", depth=-11.0)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            inset_faces("Cube")


# ---------------------------------------------------------------------------
# fill_faces
# ---------------------------------------------------------------------------


class TestFillFaces:
    def test_valid(self, mock_conn):
        fill_faces("Cube")
        mock_conn.send_command.assert_called_once_with(
            "fill_faces", {"object_name": "Cube"},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            fill_faces("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            fill_faces("Cube")


# ---------------------------------------------------------------------------
# grid_fill
# ---------------------------------------------------------------------------


class TestGridFill:
    def test_valid_defaults(self, mock_conn):
        grid_fill("Cube")
        mock_conn.send_command.assert_called_once_with(
            "grid_fill", {"object_name": "Cube", "span": 1, "offset": 0},
        )

    def test_custom_params(self, mock_conn):
        grid_fill("Cube", span=4, offset=2)
        args = mock_conn.send_command.call_args[0][1]
        assert args["span"] == 4
        assert args["offset"] == 2

    def test_span_too_low_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            grid_fill("Cube", span=0)

    def test_span_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            grid_fill("Cube", span=1001)

    def test_offset_negative_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            grid_fill("Cube", offset=-1)

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            grid_fill("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            grid_fill("Cube")


# ---------------------------------------------------------------------------
# mark_seam
# ---------------------------------------------------------------------------


class TestMarkSeam:
    def test_valid_mark(self, mock_conn):
        mark_seam("Cube")
        mock_conn.send_command.assert_called_once_with(
            "mark_seam", {"object_name": "Cube", "clear": False},
        )

    def test_valid_clear(self, mock_conn):
        mark_seam("Cube", clear=True)
        args = mock_conn.send_command.call_args[0][1]
        assert args["clear"] is True

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            mark_seam("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            mark_seam("Cube")


# ---------------------------------------------------------------------------
# mark_sharp
# ---------------------------------------------------------------------------


class TestMarkSharp:
    def test_valid_mark(self, mock_conn):
        mark_sharp("Cube")
        mock_conn.send_command.assert_called_once_with(
            "mark_sharp", {"object_name": "Cube", "clear": False},
        )

    def test_valid_clear(self, mock_conn):
        mark_sharp("Cube", clear=True)
        args = mock_conn.send_command.call_args[0][1]
        assert args["clear"] is True

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            mark_sharp("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            mark_sharp("Cube")


# ---------------------------------------------------------------------------
# recalculate_normals
# ---------------------------------------------------------------------------


class TestRecalculateNormals:
    def test_valid_default(self, mock_conn):
        recalculate_normals("Cube")
        mock_conn.send_command.assert_called_once_with(
            "recalculate_normals", {"object_name": "Cube", "inside": False},
        )

    def test_inside(self, mock_conn):
        recalculate_normals("Cube", inside=True)
        args = mock_conn.send_command.call_args[0][1]
        assert args["inside"] is True

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            recalculate_normals("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            recalculate_normals("Cube")


# ---------------------------------------------------------------------------
# flip_normals
# ---------------------------------------------------------------------------


class TestFlipNormals:
    def test_valid(self, mock_conn):
        flip_normals("Cube")
        mock_conn.send_command.assert_called_once_with(
            "flip_normals", {"object_name": "Cube"},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            flip_normals("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            flip_normals("Cube")


# ---------------------------------------------------------------------------
# quads_to_tris
# ---------------------------------------------------------------------------


class TestQuadsToTris:
    def test_valid(self, mock_conn):
        quads_to_tris("Cube")
        mock_conn.send_command.assert_called_once_with(
            "quads_to_tris", {"object_name": "Cube"},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            quads_to_tris("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            quads_to_tris("Cube")


# ---------------------------------------------------------------------------
# tris_to_quads
# ---------------------------------------------------------------------------


class TestTrisToQuads:
    def test_valid(self, mock_conn):
        tris_to_quads("Cube")
        mock_conn.send_command.assert_called_once_with(
            "tris_to_quads", {"object_name": "Cube"},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            tris_to_quads("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            tris_to_quads("Cube")


# ---------------------------------------------------------------------------
# dissolve_faces
# ---------------------------------------------------------------------------


class TestDissolveFaces:
    def test_valid(self, mock_conn):
        dissolve_faces("Cube")
        mock_conn.send_command.assert_called_once_with(
            "dissolve_faces", {"object_name": "Cube"},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            dissolve_faces("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            dissolve_faces("Cube")


# ---------------------------------------------------------------------------
# dissolve_edges
# ---------------------------------------------------------------------------


class TestDissolveEdges:
    def test_valid(self, mock_conn):
        dissolve_edges("Cube")
        mock_conn.send_command.assert_called_once_with(
            "dissolve_edges", {"object_name": "Cube"},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            dissolve_edges("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            dissolve_edges("Cube")


# ---------------------------------------------------------------------------
# dissolve_verts
# ---------------------------------------------------------------------------


class TestDissolveVerts:
    def test_valid(self, mock_conn):
        dissolve_verts("Cube")
        mock_conn.send_command.assert_called_once_with(
            "dissolve_verts", {"object_name": "Cube"},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            dissolve_verts("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            dissolve_verts("Cube")


# ---------------------------------------------------------------------------
# knife_project
# ---------------------------------------------------------------------------


class TestKnifeProject:
    def test_valid(self, mock_conn):
        knife_project("Cube", "Circle")
        mock_conn.send_command.assert_called_once_with(
            "knife_project",
            {"object_name": "Cube", "cutter_name": "Circle"},
        )

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            knife_project("", "Circle")

    def test_empty_cutter_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            knife_project("Cube", "")

    def test_invalid_cutter_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            knife_project("Cube", "bad;name")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            knife_project("Cube", "Circle")


# ---------------------------------------------------------------------------
# spin_mesh
# ---------------------------------------------------------------------------


class TestSpinMesh:
    def test_valid_defaults(self, mock_conn):
        spin_mesh("Cube")
        args = mock_conn.send_command.call_args[0][1]
        assert args["object_name"] == "Cube"
        assert args["steps"] == 12

    def test_custom_params(self, mock_conn):
        spin_mesh("Cube", angle=3.14, steps=6, axis=(1, 0, 0), center=(1, 2, 3))
        args = mock_conn.send_command.call_args[0][1]
        assert args["angle"] == 3.14
        assert args["steps"] == 6
        assert args["axis"] == (1, 0, 0)
        assert args["center"] == (1, 2, 3)

    def test_steps_too_low_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            spin_mesh("Cube", steps=0)

    def test_steps_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            spin_mesh("Cube", steps=1001)

    def test_invalid_axis_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            spin_mesh("Cube", axis=(1, 2))

    def test_invalid_center_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            spin_mesh("Cube", center=(1,))

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            spin_mesh("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            spin_mesh("Cube")


# ---------------------------------------------------------------------------
# set_edge_crease
# ---------------------------------------------------------------------------


class TestSetEdgeCrease:
    def test_valid_default(self, mock_conn):
        set_edge_crease("Cube")
        mock_conn.send_command.assert_called_once_with(
            "set_edge_crease", {"object_name": "Cube", "value": 1.0},
        )

    def test_custom_value(self, mock_conn):
        set_edge_crease("Cube", value=0.5)
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == 0.5

    def test_value_too_low_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_edge_crease("Cube", value=-1.1)

    def test_value_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_edge_crease("Cube", value=1.1)

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_edge_crease("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_edge_crease("Cube")


# ---------------------------------------------------------------------------
# select_linked
# ---------------------------------------------------------------------------


class TestSelectLinked:
    def test_valid(self, mock_conn):
        select_linked("Cube")
        mock_conn.send_command.assert_called_once_with(
            "select_linked", {"object_name": "Cube"},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            select_linked("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            select_linked("Cube")
