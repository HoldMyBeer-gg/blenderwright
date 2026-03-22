"""Unit tests for Bool Tool operations."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.booltool import (
    booltool_auto_union,
    booltool_auto_difference,
    booltool_auto_intersect,
    booltool_auto_slice,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.booltool.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# booltool_auto_union
# ---------------------------------------------------------------------------


class TestBooltoolAutoUnion:
    def test_valid(self, mock_conn):
        booltool_auto_union("Cube", "Sphere")
        mock_conn.send_command.assert_called_once_with(
            "booltool_auto_union",
            {"object_name": "Cube", "target_name": "Sphere"},
        )

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            booltool_auto_union("", "Sphere")

    def test_empty_target_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            booltool_auto_union("Cube", "")

    def test_invalid_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            booltool_auto_union("bad;name", "Sphere")

    def test_invalid_target_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            booltool_auto_union("Cube", "bad;name")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            booltool_auto_union("Cube", "Sphere")


# ---------------------------------------------------------------------------
# booltool_auto_difference
# ---------------------------------------------------------------------------


class TestBooltoolAutoDifference:
    def test_valid(self, mock_conn):
        booltool_auto_difference("Cube", "Sphere")
        mock_conn.send_command.assert_called_once_with(
            "booltool_auto_difference",
            {"object_name": "Cube", "target_name": "Sphere"},
        )

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            booltool_auto_difference("", "Sphere")

    def test_empty_target_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            booltool_auto_difference("Cube", "")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            booltool_auto_difference("Cube", "Sphere")


# ---------------------------------------------------------------------------
# booltool_auto_intersect
# ---------------------------------------------------------------------------


class TestBooltoolAutoIntersect:
    def test_valid(self, mock_conn):
        booltool_auto_intersect("Cube", "Sphere")
        mock_conn.send_command.assert_called_once_with(
            "booltool_auto_intersect",
            {"object_name": "Cube", "target_name": "Sphere"},
        )

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            booltool_auto_intersect("", "Sphere")

    def test_empty_target_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            booltool_auto_intersect("Cube", "")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            booltool_auto_intersect("Cube", "Sphere")


# ---------------------------------------------------------------------------
# booltool_auto_slice
# ---------------------------------------------------------------------------


class TestBooltoolAutoSlice:
    def test_valid(self, mock_conn):
        booltool_auto_slice("Cube", "Sphere")
        mock_conn.send_command.assert_called_once_with(
            "booltool_auto_slice",
            {"object_name": "Cube", "target_name": "Sphere"},
        )

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            booltool_auto_slice("", "Sphere")

    def test_empty_target_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            booltool_auto_slice("Cube", "")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            booltool_auto_slice("Cube", "Sphere")
