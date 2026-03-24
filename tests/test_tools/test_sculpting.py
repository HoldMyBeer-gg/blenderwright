"""Unit tests for sculpting tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"success": True}}
    with patch("blend_ai.tools.sculpting.get_connection", return_value=mock):
        yield mock


class TestEnterSculptMode:
    def test_enter_sculpt_mode(self, mock_conn):
        from blend_ai.tools.sculpting import enter_sculpt_mode

        enter_sculpt_mode("Cube")
        mock_conn.send_command.assert_called_once_with("enter_sculpt_mode", {"object_name": "Cube"})

    def test_enter_sculpt_mode_invalid_name(self, mock_conn):
        from blend_ai.tools.sculpting import enter_sculpt_mode

        with pytest.raises(ValidationError):
            enter_sculpt_mode("")


class TestExitSculptMode:
    def test_exit_sculpt_mode(self, mock_conn):
        from blend_ai.tools.sculpting import exit_sculpt_mode

        exit_sculpt_mode()
        mock_conn.send_command.assert_called_once_with("exit_sculpt_mode")


class TestSetSculptBrush:
    def test_set_brush_draw(self, mock_conn):
        from blend_ai.tools.sculpting import set_sculpt_brush

        set_sculpt_brush("DRAW")
        mock_conn.send_command.assert_called_once_with("set_sculpt_brush", {"brush_type": "DRAW"})

    def test_set_brush_all_valid_types(self, mock_conn):
        from blend_ai.tools.sculpting import set_sculpt_brush, ALLOWED_BRUSH_TYPES

        for bt in ALLOWED_BRUSH_TYPES:
            mock_conn.send_command.reset_mock()
            set_sculpt_brush(bt)
            mock_conn.send_command.assert_called_once()

    def test_set_brush_invalid_type(self, mock_conn):
        from blend_ai.tools.sculpting import set_sculpt_brush

        with pytest.raises(ValidationError):
            set_sculpt_brush("ERASER")

    def test_set_brush_case_sensitive(self, mock_conn):
        from blend_ai.tools.sculpting import set_sculpt_brush

        with pytest.raises(ValidationError):
            set_sculpt_brush("draw")


class TestSetBrushProperty:
    def test_set_size(self, mock_conn):
        from blend_ai.tools.sculpting import set_brush_property

        set_brush_property("size", 100)
        mock_conn.send_command.assert_called_once_with("set_brush_property", {
            "property": "size",
            "value": 100,
        })

    def test_set_strength(self, mock_conn):
        from blend_ai.tools.sculpting import set_brush_property

        set_brush_property("strength", 0.5)
        mock_conn.send_command.assert_called_once()

    def test_set_size_out_of_range(self, mock_conn):
        from blend_ai.tools.sculpting import set_brush_property

        with pytest.raises(ValidationError):
            set_brush_property("size", 0)
        with pytest.raises(ValidationError):
            set_brush_property("size", 501)

    def test_set_strength_out_of_range(self, mock_conn):
        from blend_ai.tools.sculpting import set_brush_property

        with pytest.raises(ValidationError):
            set_brush_property("strength", -0.1)
        with pytest.raises(ValidationError):
            set_brush_property("strength", 1.1)

    def test_set_use_frontface_not_bool(self, mock_conn):
        from blend_ai.tools.sculpting import set_brush_property

        with pytest.raises(ValidationError, match="use_frontface must be a boolean"):
            set_brush_property("use_frontface", 1)

    def test_set_use_frontface_bool(self, mock_conn):
        from blend_ai.tools.sculpting import set_brush_property

        set_brush_property("use_frontface", True)
        mock_conn.send_command.assert_called_once()

    def test_invalid_property(self, mock_conn):
        from blend_ai.tools.sculpting import set_brush_property

        with pytest.raises(ValidationError):
            set_brush_property("color", 0.5)

    def test_auto_smooth_factor_range(self, mock_conn):
        from blend_ai.tools.sculpting import set_brush_property

        set_brush_property("auto_smooth_factor", 0.0)
        mock_conn.send_command.assert_called_once()
        mock_conn.send_command.reset_mock()
        set_brush_property("auto_smooth_factor", 1.0)
        mock_conn.send_command.assert_called_once()
        with pytest.raises(ValidationError):
            set_brush_property("auto_smooth_factor", 1.1)

    def test_set_brush_property_stroke_method(self, mock_conn):
        from blend_ai.tools.sculpting import set_brush_property

        set_brush_property("stroke_method", "DOTS")
        mock_conn.send_command.assert_called_once_with(
            "set_brush_property", {"property": "stroke_method", "value": "DOTS"}
        )


class TestRemesh:
    def test_remesh_default(self, mock_conn):
        from blend_ai.tools.sculpting import remesh

        remesh("Cube")
        mock_conn.send_command.assert_called_once_with("remesh", {
            "object_name": "Cube",
            "voxel_size": 0.1,
            "mode": "VOXEL",
        })

    def test_remesh_custom(self, mock_conn):
        from blend_ai.tools.sculpting import remesh

        remesh("Cube", voxel_size=0.05, mode="SHARP")
        mock_conn.send_command.assert_called_once_with("remesh", {
            "object_name": "Cube",
            "voxel_size": 0.05,
            "mode": "SHARP",
        })

    def test_remesh_invalid_mode(self, mock_conn):
        from blend_ai.tools.sculpting import remesh

        with pytest.raises(ValidationError):
            remesh("Cube", mode="ADAPTIVE")

    def test_remesh_all_valid_modes(self, mock_conn):
        from blend_ai.tools.sculpting import remesh, ALLOWED_REMESH_MODES

        for mode in ALLOWED_REMESH_MODES:
            mock_conn.send_command.reset_mock()
            remesh("Cube", mode=mode)
            mock_conn.send_command.assert_called_once()

    def test_remesh_voxel_size_out_of_range(self, mock_conn):
        from blend_ai.tools.sculpting import remesh

        with pytest.raises(ValidationError):
            remesh("Cube", voxel_size=0.0)
        with pytest.raises(ValidationError):
            remesh("Cube", voxel_size=11.0)


class TestAddMultiresModifier:
    def test_add_multires_default(self, mock_conn):
        from blend_ai.tools.sculpting import add_multires_modifier

        add_multires_modifier("Cube")
        mock_conn.send_command.assert_called_once_with("add_multires_modifier", {
            "object_name": "Cube",
            "levels": 2,
        })

    def test_add_multires_max_level(self, mock_conn):
        from blend_ai.tools.sculpting import add_multires_modifier

        add_multires_modifier("Cube", levels=6)
        mock_conn.send_command.assert_called_once()

    def test_add_multires_level_capped(self, mock_conn):
        from blend_ai.tools.sculpting import add_multires_modifier

        with pytest.raises(ValidationError):
            add_multires_modifier("Cube", levels=7)

    def test_add_multires_level_min(self, mock_conn):
        from blend_ai.tools.sculpting import add_multires_modifier

        with pytest.raises(ValidationError):
            add_multires_modifier("Cube", levels=0)

    def test_add_multires_invalid_name(self, mock_conn):
        from blend_ai.tools.sculpting import add_multires_modifier

        with pytest.raises(ValidationError):
            add_multires_modifier("")


class TestSetSculptSymmetry:
    def test_valid_defaults(self, mock_conn):
        from blend_ai.tools.sculpting import set_sculpt_symmetry

        set_sculpt_symmetry()
        mock_conn.send_command.assert_called_once_with("set_sculpt_symmetry", {
            "use_x": True,
            "use_y": False,
            "use_z": False,
        })

    def test_custom_axes(self, mock_conn):
        from blend_ai.tools.sculpting import set_sculpt_symmetry

        set_sculpt_symmetry(use_x=False, use_y=True, use_z=True)
        args = mock_conn.send_command.call_args[0][1]
        assert args["use_x"] is False
        assert args["use_y"] is True
        assert args["use_z"] is True

    def test_error_response_raises(self, mock_conn):
        from blend_ai.tools.sculpting import set_sculpt_symmetry

        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_sculpt_symmetry()


class TestEnableDyntopo:
    def test_valid_defaults(self, mock_conn):
        from blend_ai.tools.sculpting import enable_dyntopo

        enable_dyntopo("Cube")
        mock_conn.send_command.assert_called_once_with("enable_dyntopo", {
            "object_name": "Cube",
            "detail_size": 12.0,
            "detail_mode": "RELATIVE",
        })

    def test_custom_params(self, mock_conn):
        from blend_ai.tools.sculpting import enable_dyntopo

        enable_dyntopo("Cube", detail_size=5.0, detail_mode="CONSTANT")
        args = mock_conn.send_command.call_args[0][1]
        assert args["detail_size"] == 5.0
        assert args["detail_mode"] == "CONSTANT"

    def test_invalid_detail_mode_raises(self, mock_conn):
        from blend_ai.tools.sculpting import enable_dyntopo

        with pytest.raises(ValidationError):
            enable_dyntopo("Cube", detail_mode="ADAPTIVE")

    def test_detail_size_too_low_raises(self, mock_conn):
        from blend_ai.tools.sculpting import enable_dyntopo

        with pytest.raises(ValidationError):
            enable_dyntopo("Cube", detail_size=0.0)

    def test_detail_size_too_high_raises(self, mock_conn):
        from blend_ai.tools.sculpting import enable_dyntopo

        with pytest.raises(ValidationError):
            enable_dyntopo("Cube", detail_size=501.0)

    def test_empty_name_raises(self, mock_conn):
        from blend_ai.tools.sculpting import enable_dyntopo

        with pytest.raises(ValidationError):
            enable_dyntopo("")

    def test_error_response_raises(self, mock_conn):
        from blend_ai.tools.sculpting import enable_dyntopo

        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            enable_dyntopo("Cube")


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.sculpting import enter_sculpt_mode

        mock_conn.send_command.return_value = {"status": "error", "result": "Not a mesh"}
        with pytest.raises(RuntimeError, match="Blender error"):
            enter_sculpt_mode("Cube")
