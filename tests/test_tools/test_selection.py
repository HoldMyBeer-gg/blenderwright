"""Selecting part of a mesh, so the edit tools can act on part of it.

Every mesh handler called select_all(action="SELECT") first, so "bevel the top
edge" or "inset the front face" could not be expressed and sixteen tools
quietly did their job to the entire mesh. See issue #24.

Selection is not state we invent. Blender stores it on the mesh data as
vertex/edge/polygon select flags; it survives leaving edit mode, survives
deselecting the object, and is saved in the .blend. Verified against Blender
5.1. These tools set it; the edit tools will read it.
"""

import pytest
from unittest.mock import MagicMock, patch

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blend_ai.tools.selection.get_connection", return_value=mock):
        yield mock


class TestSelectAllGeometry:
    @pytest.mark.parametrize("action", ["SELECT", "DESELECT", "INVERT"])
    def test_actions_are_passed_through(self, mock_conn, action):
        from blend_ai.tools.selection import select_all_geometry
        select_all_geometry("Cube", action=action)
        assert mock_conn.send_command.call_args[0][1]["action"] == action

    def test_unknown_action_is_rejected(self, mock_conn):
        from blend_ai.tools.selection import select_all_geometry
        with pytest.raises(ValidationError):
            select_all_geometry("Cube", action="TOGGLE_MAYBE")


class TestSelectByIndex:
    """The deterministic primitive: no operator, no context, no guessing.

    analyze_mesh_quality already reports sample indices for each defect, so
    this is what lets an agent act on them.
    """

    def test_indices_and_element_are_sent(self, mock_conn):
        from blend_ai.tools.selection import select_by_index
        select_by_index("Cube", element="FACE", indices=[0, 3])
        sent = mock_conn.send_command.call_args[0][1]
        assert sent["element"] == "FACE"
        assert sent["indices"] == [0, 3]

    @pytest.mark.parametrize("element", ["VERTEX", "EDGE", "FACE"])
    def test_each_element_type_is_allowed(self, mock_conn, element):
        from blend_ai.tools.selection import select_by_index
        select_by_index("Cube", element=element, indices=[0])
        assert mock_conn.send_command.called

    def test_unknown_element_is_rejected(self, mock_conn):
        from blend_ai.tools.selection import select_by_index
        with pytest.raises(ValidationError):
            select_by_index("Cube", element="POLYGON", indices=[0])

    def test_empty_indices_is_rejected(self, mock_conn):
        """Selecting nothing would report success having done nothing."""
        from blend_ai.tools.selection import select_by_index
        with pytest.raises(ValidationError):
            select_by_index("Cube", element="FACE", indices=[])

    def test_negative_index_is_rejected(self, mock_conn):
        from blend_ai.tools.selection import select_by_index
        with pytest.raises(ValidationError):
            select_by_index("Cube", element="FACE", indices=[0, -2])

    def test_extends_by_default_is_false(self, mock_conn):
        """Replacing is the predictable default; extending is opt-in."""
        from blend_ai.tools.selection import select_by_index
        select_by_index("Cube", element="FACE", indices=[1])
        assert mock_conn.send_command.call_args[0][1]["extend"] is False


class TestSelectByAxis:
    def test_axis_and_sign_are_sent(self, mock_conn):
        from blend_ai.tools.selection import select_by_axis
        select_by_axis("Cube", axis="Z", sign="POS")
        sent = mock_conn.send_command.call_args[0][1]
        assert sent["axis"] == "Z" and sent["sign"] == "POS"

    @pytest.mark.parametrize("bad", [("W", "POS"), ("Z", "UPWARDS")])
    def test_invalid_values_are_rejected(self, mock_conn, bad):
        from blend_ai.tools.selection import select_by_axis
        with pytest.raises(ValidationError):
            select_by_axis("Cube", axis=bad[0], sign=bad[1])


class TestSelectSimilar:
    def test_type_is_sent(self, mock_conn):
        from blend_ai.tools.selection import select_similar
        select_similar("Cube", type="FACE_AREA")
        assert mock_conn.send_command.call_args[0][1]["type"] == "FACE_AREA"

    def test_the_enum_matches_blender(self, mock_conn):
        """Verified against Blender 5.1: FACE_AREA, not AREA."""
        from blend_ai.tools.selection import ALLOWED_SIMILAR_TYPES
        assert "FACE_AREA" in ALLOWED_SIMILAR_TYPES
        assert "AREA" not in ALLOWED_SIMILAR_TYPES

    def test_unknown_type_is_rejected(self, mock_conn):
        from blend_ai.tools.selection import select_similar
        with pytest.raises(ValidationError):
            select_similar("Cube", type="AREA")


class TestSelectFacesBySides:
    def test_quads(self, mock_conn):
        from blend_ai.tools.selection import select_faces_by_sides
        select_faces_by_sides("Cube", number=4, comparison="EQUAL")
        sent = mock_conn.send_command.call_args[0][1]
        assert sent["number"] == 4 and sent["comparison"] == "EQUAL"

    def test_ngons_via_greater(self, mock_conn):
        from blend_ai.tools.selection import select_faces_by_sides
        select_faces_by_sides("Cube", number=4, comparison="GREATER")
        assert mock_conn.send_command.call_args[0][1]["comparison"] == "GREATER"

    def test_a_face_needs_at_least_three_sides(self, mock_conn):
        from blend_ai.tools.selection import select_faces_by_sides
        with pytest.raises(ValidationError):
            select_faces_by_sides("Cube", number=2)


class TestGetSelection:
    """Without this an agent cannot see what it selected."""

    def test_reports_the_object(self, mock_conn):
        from blend_ai.tools.selection import get_selection
        get_selection("Cube")
        assert mock_conn.send_command.call_args[0][1] == {"object_name": "Cube"}


class TestLoopSelectIsNotOffered:
    def test_no_loop_select_tool_exists(self):
        """bpy.ops.mesh.loop_select needs a view3d region and a click.

        Verified: it raises "Operator bpy.ops.mesh.loop_select.poll() Expected
        a view3d region". Offering it would be a tool that always fails.
        """
        from blend_ai.tools import selection
        assert not any("loop" in name for name in dir(selection))
