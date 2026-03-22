"""Unit tests for UV tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"success": True}}
    with patch("blend_ai.tools.uv.get_connection", return_value=mock):
        yield mock


class TestSmartUVProject:
    def test_smart_uv_defaults(self, mock_conn):
        from blend_ai.tools.uv import smart_uv_project

        smart_uv_project("Cube")
        mock_conn.send_command.assert_called_once_with("smart_uv_project", {
            "object_name": "Cube",
            "angle_limit": 66.0,
            "island_margin": 0.0,
            "area_weight": 0.0,
        })

    def test_smart_uv_custom(self, mock_conn):
        from blend_ai.tools.uv import smart_uv_project

        smart_uv_project("Cube", angle_limit=45.0, island_margin=0.02, area_weight=0.5)
        mock_conn.send_command.assert_called_once_with("smart_uv_project", {
            "object_name": "Cube",
            "angle_limit": 45.0,
            "island_margin": 0.02,
            "area_weight": 0.5,
        })

    def test_angle_limit_out_of_range(self, mock_conn):
        from blend_ai.tools.uv import smart_uv_project

        with pytest.raises(ValidationError):
            smart_uv_project("Cube", angle_limit=-1.0)
        with pytest.raises(ValidationError):
            smart_uv_project("Cube", angle_limit=90.0)

    def test_island_margin_out_of_range(self, mock_conn):
        from blend_ai.tools.uv import smart_uv_project

        with pytest.raises(ValidationError):
            smart_uv_project("Cube", island_margin=-0.1)
        with pytest.raises(ValidationError):
            smart_uv_project("Cube", island_margin=1.1)

    def test_area_weight_out_of_range(self, mock_conn):
        from blend_ai.tools.uv import smart_uv_project

        with pytest.raises(ValidationError):
            smart_uv_project("Cube", area_weight=-0.1)
        with pytest.raises(ValidationError):
            smart_uv_project("Cube", area_weight=1.1)

    def test_invalid_object_name(self, mock_conn):
        from blend_ai.tools.uv import smart_uv_project

        with pytest.raises(ValidationError):
            smart_uv_project("")


class TestUVUnwrap:
    def test_unwrap_angle_based(self, mock_conn):
        from blend_ai.tools.uv import uv_unwrap

        uv_unwrap("Cube", method="ANGLE_BASED")
        mock_conn.send_command.assert_called_once_with("uv_unwrap", {
            "object_name": "Cube",
            "method": "ANGLE_BASED",
        })

    def test_unwrap_conformal(self, mock_conn):
        from blend_ai.tools.uv import uv_unwrap

        uv_unwrap("Cube", method="CONFORMAL")
        mock_conn.send_command.assert_called_once()

    def test_unwrap_invalid_method(self, mock_conn):
        from blend_ai.tools.uv import uv_unwrap

        with pytest.raises(ValidationError):
            uv_unwrap("Cube", method="SMART")

    def test_unwrap_default_method(self, mock_conn):
        from blend_ai.tools.uv import uv_unwrap

        uv_unwrap("Cube")
        call_args = mock_conn.send_command.call_args
        assert call_args[0][1]["method"] == "ANGLE_BASED"


class TestSetUVProjection:
    def test_cube_projection(self, mock_conn):
        from blend_ai.tools.uv import set_uv_projection

        set_uv_projection("Cube", "CUBE")
        mock_conn.send_command.assert_called_once_with("set_uv_projection", {
            "object_name": "Cube",
            "projection": "CUBE",
        })

    def test_cylinder_projection(self, mock_conn):
        from blend_ai.tools.uv import set_uv_projection

        set_uv_projection("Cylinder", "CYLINDER")
        mock_conn.send_command.assert_called_once()

    def test_sphere_projection(self, mock_conn):
        from blend_ai.tools.uv import set_uv_projection

        set_uv_projection("Sphere", "SPHERE")
        mock_conn.send_command.assert_called_once()

    def test_invalid_projection(self, mock_conn):
        from blend_ai.tools.uv import set_uv_projection

        with pytest.raises(ValidationError):
            set_uv_projection("Cube", "PLANAR")

    def test_invalid_object_name(self, mock_conn):
        from blend_ai.tools.uv import set_uv_projection

        with pytest.raises(ValidationError):
            set_uv_projection("", "CUBE")


class TestPackUVIslands:
    def test_pack_default(self, mock_conn):
        from blend_ai.tools.uv import pack_uv_islands

        pack_uv_islands("Cube")
        mock_conn.send_command.assert_called_once_with("pack_uv_islands", {
            "object_name": "Cube",
            "margin": 0.001,
        })

    def test_pack_custom_margin(self, mock_conn):
        from blend_ai.tools.uv import pack_uv_islands

        pack_uv_islands("Cube", margin=0.05)
        mock_conn.send_command.assert_called_once_with("pack_uv_islands", {
            "object_name": "Cube",
            "margin": 0.05,
        })

    def test_margin_out_of_range(self, mock_conn):
        from blend_ai.tools.uv import pack_uv_islands

        with pytest.raises(ValidationError):
            pack_uv_islands("Cube", margin=-0.001)
        with pytest.raises(ValidationError):
            pack_uv_islands("Cube", margin=1.1)

    def test_margin_boundaries(self, mock_conn):
        from blend_ai.tools.uv import pack_uv_islands

        pack_uv_islands("Cube", margin=0.0)
        mock_conn.send_command.assert_called_once()
        mock_conn.send_command.reset_mock()
        pack_uv_islands("Cube", margin=1.0)
        mock_conn.send_command.assert_called_once()


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.uv import smart_uv_project

        mock_conn.send_command.return_value = {"status": "error", "result": "Not a mesh object"}
        with pytest.raises(RuntimeError, match="Blender error"):
            smart_uv_project("Cube")
