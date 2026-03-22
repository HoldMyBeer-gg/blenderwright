"""Unit tests for transform tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.transforms import (
    set_location,
    set_rotation,
    set_scale,
    apply_transforms,
    set_origin,
    snap_to_grid,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.transforms.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# set_location
# ---------------------------------------------------------------------------


class TestSetLocation:
    def test_valid(self, mock_conn):
        set_location("Cube", [1.0, 2.0, 3.0])
        mock_conn.send_command.assert_called_once_with(
            "set_location", {"name": "Cube", "location": [1.0, 2.0, 3.0]}
        )

    def test_tuple_input(self, mock_conn):
        set_location("Cube", (0, 0, 0))
        args = mock_conn.send_command.call_args[0][1]
        assert args["location"] == [0, 0, 0]

    def test_invalid_vector_size_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_location("Cube", [1, 2])

    def test_invalid_vector_type_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_location("Cube", "not_a_vector")

    def test_non_numeric_component_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_location("Cube", [1, "two", 3])

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_location("", [0, 0, 0])

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_location("Cube", [0, 0, 0])


# ---------------------------------------------------------------------------
# set_rotation
# ---------------------------------------------------------------------------


class TestSetRotation:
    def test_euler_mode_default(self, mock_conn):
        set_rotation("Cube", [1.57, 0, 0])
        mock_conn.send_command.assert_called_once_with(
            "set_rotation",
            {"name": "Cube", "rotation": [1.57, 0, 0], "mode": "EULER"},
        )

    def test_euler_mode_explicit(self, mock_conn):
        set_rotation("Cube", [0, 0, 3.14], mode="EULER")
        args = mock_conn.send_command.call_args[0][1]
        assert args["mode"] == "EULER"
        assert args["rotation"] == [0, 0, 3.14]

    def test_quaternion_mode(self, mock_conn):
        set_rotation("Cube", [1, 0, 0, 0], mode="QUATERNION")
        mock_conn.send_command.assert_called_once_with(
            "set_rotation",
            {"name": "Cube", "rotation": [1, 0, 0, 0], "mode": "QUATERNION"},
        )

    def test_quaternion_wrong_size_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_rotation("Cube", [1, 0, 0], mode="QUATERNION")

    def test_euler_wrong_size_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_rotation("Cube", [1, 0, 0, 0], mode="EULER")

    def test_invalid_mode_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_rotation("Cube", [0, 0, 0], mode="AXIS_ANGLE")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_rotation("Cube", [0, 0, 0])


# ---------------------------------------------------------------------------
# set_scale
# ---------------------------------------------------------------------------


class TestSetScale:
    def test_valid(self, mock_conn):
        set_scale("Cube", [2, 2, 2])
        mock_conn.send_command.assert_called_once_with(
            "set_scale", {"name": "Cube", "scale": [2, 2, 2]}
        )

    def test_invalid_vector_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_scale("Cube", [1, 2])

    def test_non_numeric_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_scale("Cube", ["a", "b", "c"])

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_scale("", [1, 1, 1])


# ---------------------------------------------------------------------------
# apply_transforms
# ---------------------------------------------------------------------------


class TestApplyTransforms:
    def test_defaults(self, mock_conn):
        apply_transforms("Cube")
        mock_conn.send_command.assert_called_once_with(
            "apply_transforms",
            {"name": "Cube", "location": True, "rotation": True, "scale": True},
        )

    def test_selective(self, mock_conn):
        apply_transforms("Cube", location=False, rotation=True, scale=False)
        args = mock_conn.send_command.call_args[0][1]
        assert args["location"] is False
        assert args["rotation"] is True
        assert args["scale"] is False

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            apply_transforms("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            apply_transforms("Cube")


# ---------------------------------------------------------------------------
# set_origin
# ---------------------------------------------------------------------------


class TestSetOrigin:
    def test_default_type(self, mock_conn):
        set_origin("Cube")
        mock_conn.send_command.assert_called_once_with(
            "set_origin", {"name": "Cube", "type": "GEOMETRY"}
        )

    def test_cursor(self, mock_conn):
        set_origin("Cube", type="CURSOR")
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "CURSOR"

    def test_center_of_mass(self, mock_conn):
        set_origin("Cube", type="CENTER_OF_MASS")
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "CENTER_OF_MASS"

    def test_center_of_volume(self, mock_conn):
        set_origin("Cube", type="CENTER_OF_VOLUME")
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "CENTER_OF_VOLUME"

    def test_invalid_type_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_origin("Cube", type="INVALID")

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_origin("")


# ---------------------------------------------------------------------------
# snap_to_grid
# ---------------------------------------------------------------------------


class TestSnapToGrid:
    def test_default_grid_size(self, mock_conn):
        snap_to_grid("Cube")
        mock_conn.send_command.assert_called_once_with(
            "snap_to_grid", {"name": "Cube", "grid_size": 1.0}
        )

    def test_custom_grid_size(self, mock_conn):
        snap_to_grid("Cube", grid_size=0.5)
        args = mock_conn.send_command.call_args[0][1]
        assert args["grid_size"] == 0.5

    def test_grid_size_too_small_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            snap_to_grid("Cube", grid_size=0.0001)

    def test_grid_size_too_large_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            snap_to_grid("Cube", grid_size=5000.0)

    def test_grid_size_non_numeric_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            snap_to_grid("Cube", grid_size="big")

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            snap_to_grid("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            snap_to_grid("Cube")
