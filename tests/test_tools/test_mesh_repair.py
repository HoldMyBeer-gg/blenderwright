"""Repairs for the defects analyze_mesh_quality already reports.

The analyser returned five defect counts and blend-ai could act on one of
them. An agent told its mesh had 412 loose vertices and 7 zero-area faces had
nothing to call. See issue #25.

    loose_vertex_count     -> repair_mesh(remove_loose=True)
    wire_edge_count        -> repair_mesh(remove_loose=True)
    zero_area_face_count   -> repair_mesh(dissolve_degenerate=True)
    non_manifold_edge_count-> repair_mesh(fill_holes=True)
    duplicate_vertex_count -> merge_vertices, which already existed
"""

import pytest
from unittest.mock import MagicMock, patch

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blend_ai.tools.mesh_quality.get_connection", return_value=mock):
        yield mock


class TestRepairMesh:
    def test_defaults_to_the_safe_repairs(self, mock_conn):
        """Removing loose geometry and dissolving degenerate faces cannot
        change a well-formed mesh, so they are on by default."""
        from blend_ai.tools.mesh_quality import repair_mesh
        repair_mesh("Cube")
        sent = mock_conn.send_command.call_args[0][1]
        assert sent["remove_loose"] is True
        assert sent["dissolve_degenerate"] is True

    def test_hole_filling_is_opt_in(self, mock_conn):
        """fill_holes invents geometry, so it should be asked for."""
        from blend_ai.tools.mesh_quality import repair_mesh
        repair_mesh("Cube")
        assert mock_conn.send_command.call_args[0][1]["fill_holes"] is False

    def test_each_repair_can_be_chosen(self, mock_conn):
        from blend_ai.tools.mesh_quality import repair_mesh
        repair_mesh("Cube", remove_loose=False, dissolve_degenerate=False,
                    fill_holes=True)
        sent = mock_conn.send_command.call_args[0][1]
        assert sent == {"object_name": "Cube", "remove_loose": False,
                        "dissolve_degenerate": False, "fill_holes": True}

    def test_doing_nothing_is_refused(self, mock_conn):
        """All three off is a no-op that would report success."""
        from blend_ai.tools.mesh_quality import repair_mesh
        with pytest.raises(ValidationError):
            repair_mesh("Cube", remove_loose=False, dissolve_degenerate=False,
                        fill_holes=False)

    def test_object_name_is_validated(self, mock_conn):
        from blend_ai.tools.mesh_quality import repair_mesh
        with pytest.raises(ValidationError):
            repair_mesh("bad<>name")

    def test_blender_errors_propagate(self, mock_conn):
        from blend_ai.tools.mesh_quality import repair_mesh
        mock_conn.send_command.return_value = {"status": "error", "result": "nope"}
        with pytest.raises(RuntimeError):
            repair_mesh("Cube")


class TestDecimateMesh:
    def test_ratio_is_sent(self, mock_conn):
        from blend_ai.tools.mesh_quality import decimate_mesh
        decimate_mesh("Cube", ratio=0.5)
        assert mock_conn.send_command.call_args[0][1]["ratio"] == 0.5

    @pytest.mark.parametrize("bad", [0, -0.1, 1.5])
    def test_ratio_must_be_a_usable_fraction(self, mock_conn, bad):
        from blend_ai.tools.mesh_quality import decimate_mesh
        with pytest.raises(ValidationError):
            decimate_mesh("Cube", ratio=bad)

    def test_ratio_of_one_is_refused_as_a_no_op(self, mock_conn):
        """Keeping 100% of the faces does nothing but report success."""
        from blend_ai.tools.mesh_quality import decimate_mesh
        with pytest.raises(ValidationError):
            decimate_mesh("Cube", ratio=1.0)

    def test_numeric_strings_are_accepted(self, mock_conn):
        from blend_ai.tools.mesh_quality import decimate_mesh
        decimate_mesh("Cube", ratio="0.25")
        assert mock_conn.send_command.call_args[0][1]["ratio"] == 0.25


class TestTheAnalyserNowHasAnAnswerForEachDefect:
    """The point of the issue: every reported defect has a repair."""

    REPAIRS = {
        "loose_vertex_count": "repair_mesh",
        "wire_edge_count": "repair_mesh",
        "zero_area_face_count": "repair_mesh",
        "non_manifold_edge_count": "repair_mesh",
        "duplicate_vertex_count": "merge_vertices",
    }

    def test_every_reported_defect_has_a_tool(self):
        from blend_ai.tools import mesh_quality, mesh_editing, modeling
        available = set(dir(mesh_quality)) | set(dir(mesh_editing)) | set(dir(modeling))
        for defect, tool in self.REPAIRS.items():
            assert tool in available, f"{defect} has no repair tool"

    def test_the_analyser_reports_exactly_the_defects_we_cover(self):
        """If the analyser learns a new defect, this fails until it has a fix."""
        import re
        from pathlib import Path
        handler = (Path(__file__).parent.parent.parent
                   / "addon" / "handlers" / "mesh_quality.py").read_text()
        reported = set(re.findall(r'"(\w+_count)"', handler))
        structural = {"vertex_count", "edge_count", "face_count"}
        assert reported - structural == set(self.REPAIRS), (
            f"defects without a listed repair: "
            f"{sorted(reported - structural - set(self.REPAIRS))}"
        )
