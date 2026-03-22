"""Unit tests for object tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.objects import (
    create_object,
    delete_object,
    duplicate_object,
    rename_object,
    select_objects,
    get_object_info,
    list_objects,
    set_object_visibility,
    parent_objects,
    join_objects,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.objects.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# create_object
# ---------------------------------------------------------------------------


class TestCreateObject:
    def test_valid_cube(self, mock_conn):
        create_object("CUBE", name="MyCube")
        mock_conn.send_command.assert_called_once_with(
            "create_object",
            {
                "type": "CUBE",
                "name": "MyCube",
                "location": [0, 0, 0],
                "rotation": [0, 0, 0],
                "scale": [1, 1, 1],
            },
        )

    def test_valid_with_location(self, mock_conn):
        create_object("SPHERE", location=[1.0, 2.0, 3.0])
        call_args = mock_conn.send_command.call_args
        assert call_args[0][1]["location"] == [1.0, 2.0, 3.0]
        assert call_args[0][1]["type"] == "SPHERE"

    def test_valid_all_params(self, mock_conn):
        create_object(
            "CYLINDER",
            name="Cyl",
            location=[1, 0, 0],
            rotation=[0, 1.57, 0],
            scale=[2, 2, 2],
        )
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "CYLINDER"
        assert args["name"] == "Cyl"
        assert args["rotation"] == [0, 1.57, 0]
        assert args["scale"] == [2, 2, 2]

    def test_no_name_sends_empty(self, mock_conn):
        create_object("PLANE")
        args = mock_conn.send_command.call_args[0][1]
        assert args["name"] == ""

    def test_invalid_type_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_object("INVALID_TYPE")

    def test_invalid_name_chars_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_object("CUBE", name="bad;name")

    def test_invalid_location_wrong_size_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_object("CUBE", location=[1, 2])

    def test_invalid_location_non_numeric_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_object("CUBE", location=["a", "b", "c"])

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            create_object("CUBE")


# ---------------------------------------------------------------------------
# delete_object
# ---------------------------------------------------------------------------


class TestDeleteObject:
    def test_valid(self, mock_conn):
        delete_object("Cube")
        mock_conn.send_command.assert_called_once_with(
            "delete_object", {"name": "Cube"}
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            delete_object("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "not found"}
        with pytest.raises(RuntimeError):
            delete_object("Cube")


# ---------------------------------------------------------------------------
# duplicate_object
# ---------------------------------------------------------------------------


class TestDuplicateObject:
    def test_valid(self, mock_conn):
        duplicate_object("Cube")
        mock_conn.send_command.assert_called_once_with(
            "duplicate_object", {"name": "Cube", "linked": False}
        )

    def test_linked(self, mock_conn):
        duplicate_object("Cube", linked=True)
        mock_conn.send_command.assert_called_once_with(
            "duplicate_object", {"name": "Cube", "linked": True}
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            duplicate_object("")


# ---------------------------------------------------------------------------
# rename_object
# ---------------------------------------------------------------------------


class TestRenameObject:
    def test_valid(self, mock_conn):
        rename_object("OldName", "NewName")
        mock_conn.send_command.assert_called_once_with(
            "rename_object", {"old_name": "OldName", "new_name": "NewName"}
        )

    def test_empty_old_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            rename_object("", "NewName")

    def test_empty_new_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            rename_object("OldName", "")

    def test_invalid_new_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            rename_object("OldName", "bad<>name")


# ---------------------------------------------------------------------------
# select_objects
# ---------------------------------------------------------------------------


class TestSelectObjects:
    def test_valid(self, mock_conn):
        select_objects(["Cube", "Sphere"])
        mock_conn.send_command.assert_called_once_with(
            "select_objects", {"names": ["Cube", "Sphere"], "deselect_others": True}
        )

    def test_deselect_false(self, mock_conn):
        select_objects(["Cube"], deselect_others=False)
        args = mock_conn.send_command.call_args[0][1]
        assert args["deselect_others"] is False

    def test_invalid_name_in_list_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            select_objects(["Cube", "bad;name"])


# ---------------------------------------------------------------------------
# get_object_info
# ---------------------------------------------------------------------------


class TestGetObjectInfo:
    def test_valid(self, mock_conn):
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": {"name": "Cube", "type": "MESH"},
        }
        result = get_object_info("Cube")
        mock_conn.send_command.assert_called_once_with(
            "get_object_info", {"name": "Cube"}
        )
        assert result["type"] == "MESH"

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            get_object_info("")


# ---------------------------------------------------------------------------
# list_objects
# ---------------------------------------------------------------------------


class TestListObjects:
    def test_no_filter(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "ok", "result": []}
        list_objects()
        mock_conn.send_command.assert_called_once_with(
            "list_objects", {"type_filter": ""}
        )

    def test_with_filter(self, mock_conn):
        list_objects(type_filter="MESH")
        mock_conn.send_command.assert_called_once_with(
            "list_objects", {"type_filter": "MESH"}
        )

    def test_invalid_filter_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            list_objects(type_filter="INVALID")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "err"}
        with pytest.raises(RuntimeError):
            list_objects()


# ---------------------------------------------------------------------------
# set_object_visibility
# ---------------------------------------------------------------------------


class TestSetObjectVisibility:
    def test_valid(self, mock_conn):
        set_object_visibility("Cube", visible=False)
        mock_conn.send_command.assert_called_once_with(
            "set_object_visibility",
            {"name": "Cube", "visible": False, "viewport": True, "render": True},
        )

    def test_viewport_only(self, mock_conn):
        set_object_visibility("Cube", visible=True, viewport=True, render=False)
        args = mock_conn.send_command.call_args[0][1]
        assert args["viewport"] is True
        assert args["render"] is False

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_object_visibility("", visible=True)


# ---------------------------------------------------------------------------
# parent_objects
# ---------------------------------------------------------------------------


class TestParentObjects:
    def test_valid(self, mock_conn):
        parent_objects("Child", "Parent")
        mock_conn.send_command.assert_called_once_with(
            "parent_objects", {"child": "Child", "parent": "Parent"}
        )

    def test_empty_child_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            parent_objects("", "Parent")

    def test_empty_parent_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            parent_objects("Child", "")


# ---------------------------------------------------------------------------
# join_objects
# ---------------------------------------------------------------------------


class TestJoinObjects:
    def test_valid(self, mock_conn):
        join_objects(["Cube", "Sphere"])
        mock_conn.send_command.assert_called_once_with(
            "join_objects", {"names": ["Cube", "Sphere"]}
        )

    def test_too_few_objects_raises(self, mock_conn):
        with pytest.raises(ValidationError, match="At least 2"):
            join_objects(["Cube"])

    def test_empty_list_raises(self, mock_conn):
        with pytest.raises(ValidationError, match="At least 2"):
            join_objects([])

    def test_invalid_name_in_list_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            join_objects(["Cube", "bad;name"])

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            join_objects(["Cube", "Sphere"])
