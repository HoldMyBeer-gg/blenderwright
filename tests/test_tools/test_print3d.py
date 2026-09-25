"""Tool-layer tests for the 3D Print Toolbox wrapper."""

import math
import pytest
from unittest.mock import MagicMock, patch

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blend_ai.tools.print3d.get_connection", return_value=mock):
        yield mock


class TestCheck3DPrintability:
    def test_command_name_and_object(self, mock_conn):
        from blend_ai.tools.print3d import check_3d_printability
        check_3d_printability("Roof")
        assert mock_conn.send_command.call_args[0][0] == "check_3d_printability"
        assert mock_conn.send_command.call_args[0][1]["object_name"] == "Roof"

    def test_object_name_is_validated(self, mock_conn):
        from blend_ai.tools.print3d import check_3d_printability
        with pytest.raises(ValidationError):
            check_3d_printability("../../etc/passwd")

    @pytest.mark.parametrize("check", [
        "SOLID", "INTERSECT", "DEGENERATE", "THICKNESS",
        "SHARP", "OVERHANG", "NONPLANAR",
    ])
    def test_each_check_is_accepted(self, mock_conn, check):
        from blend_ai.tools.print3d import check_3d_printability
        check_3d_printability("Roof", checks=[check])
        assert mock_conn.send_command.call_args[0][1]["checks"] == [check]

    def test_unknown_check_is_rejected(self, mock_conn):
        from blend_ai.tools.print3d import check_3d_printability
        with pytest.raises(ValidationError):
            check_3d_printability("Roof", checks=["WARP_CORE"])

    def test_checks_must_be_a_list(self, mock_conn):
        from blend_ai.tools.print3d import check_3d_printability
        with pytest.raises(ValidationError):
            check_3d_printability("Roof", checks="SOLID")

    def test_empty_checks_means_everything(self, mock_conn):
        from blend_ai.tools.print3d import check_3d_printability
        check_3d_printability("Roof", checks=[])
        assert mock_conn.send_command.call_args[0][1]["checks"] == []

    def test_duplicate_checks_are_collapsed(self, mock_conn):
        from blend_ai.tools.print3d import check_3d_printability
        check_3d_printability("Roof", checks=["SOLID", "SOLID"])
        assert mock_conn.send_command.call_args[0][1]["checks"] == ["SOLID"]

    def test_angles_are_radians_and_bounded(self, mock_conn):
        from blend_ai.tools.print3d import check_3d_printability
        check_3d_printability("Roof", overhang_angle=math.radians(50))
        sent = mock_conn.send_command.call_args[0][1]
        assert sent["overhang_angle"] == pytest.approx(math.radians(50))

    def test_degree_sized_angle_is_rejected_with_a_hint(self, mock_conn):
        """45 means 45 radians. The validator says so rather than silently capping."""
        from blend_ai.tools.print3d import check_3d_printability
        with pytest.raises(ValidationError, match="radian"):
            check_3d_printability("Roof", overhang_angle=45.0)

    def test_negative_thickness_is_rejected(self, mock_conn):
        from blend_ai.tools.print3d import check_3d_printability
        with pytest.raises(ValidationError):
            check_3d_printability("Roof", min_thickness=-1.0)

    def test_thresholds_are_omitted_when_not_given(self, mock_conn):
        """Sending a default would overwrite the user's toolbox settings."""
        from blend_ai.tools.print3d import check_3d_printability
        check_3d_printability("Roof")
        sent = mock_conn.send_command.call_args[0][1]
        for key in ("overhang_angle", "min_thickness", "sharp_angle",
                    "nonplanar_angle", "zero_threshold"):
            assert key not in sent

    def test_blender_error_is_raised(self, mock_conn):
        from blend_ai.tools.print3d import check_3d_printability
        mock_conn.send_command.return_value = {
            "status": "error",
            "result": "RuntimeError: The 3D Print Toolbox extension is not enabled",
        }
        with pytest.raises(RuntimeError, match="3D Print Toolbox"):
            check_3d_printability("Roof")

    def test_report_is_returned(self, mock_conn):
        from blend_ai.tools.print3d import check_3d_printability
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": {"object": "Roof", "bad_contiguous_edge_count": 3,
                       "issues_found": True, "print_blocking": ["3 bad contiguous edges"]},
        }
        out = check_3d_printability("Roof")
        assert out["bad_contiguous_edge_count"] == 3
        assert out["print_blocking"] == ["3 bad contiguous edges"]


class TestExtensionCatalog:
    def test_toolbox_is_suggested_for_printing_tasks(self):
        from blend_ai.tools.scene import EXTENSION_CATALOG
        assert "print3d_toolbox" in EXTENSION_CATALOG
        keywords = EXTENSION_CATALOG["print3d_toolbox"]["keywords"]
        assert any(k in keywords for k in ("3d print", "print", "printable"))
