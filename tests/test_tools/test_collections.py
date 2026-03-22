"""Unit tests for collection tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"success": True}}
    with patch("blend_ai.tools.collections.get_connection", return_value=mock):
        yield mock


class TestCreateCollection:
    def test_create_collection(self, mock_conn):
        from blend_ai.tools.collections import create_collection

        create_collection("MyCollection")
        mock_conn.send_command.assert_called_once_with("create_collection", {
            "name": "MyCollection",
            "parent": "",
        })

    def test_create_collection_with_parent(self, mock_conn):
        from blend_ai.tools.collections import create_collection

        create_collection("SubCollection", parent="ParentCollection")
        mock_conn.send_command.assert_called_once_with("create_collection", {
            "name": "SubCollection",
            "parent": "ParentCollection",
        })

    def test_create_collection_empty_name(self, mock_conn):
        from blend_ai.tools.collections import create_collection

        with pytest.raises(ValidationError):
            create_collection("")

    def test_create_collection_invalid_chars_in_name(self, mock_conn):
        from blend_ai.tools.collections import create_collection

        with pytest.raises(ValidationError):
            create_collection("My/Collection")

    def test_create_collection_name_too_long(self, mock_conn):
        from blend_ai.tools.collections import create_collection

        with pytest.raises(ValidationError):
            create_collection("a" * 64)


class TestMoveToCollection:
    def test_move_single_object(self, mock_conn):
        from blend_ai.tools.collections import move_to_collection

        move_to_collection(["Cube"], "MyCollection")
        mock_conn.send_command.assert_called_once_with("move_to_collection", {
            "object_names": ["Cube"],
            "collection_name": "MyCollection",
        })

    def test_move_multiple_objects(self, mock_conn):
        from blend_ai.tools.collections import move_to_collection

        move_to_collection(["Cube", "Sphere", "Light"], "SceneObjects")
        mock_conn.send_command.assert_called_once_with("move_to_collection", {
            "object_names": ["Cube", "Sphere", "Light"],
            "collection_name": "SceneObjects",
        })

    def test_move_empty_list(self, mock_conn):
        from blend_ai.tools.collections import move_to_collection

        with pytest.raises(ValidationError, match="object_names must not be empty"):
            move_to_collection([], "MyCollection")

    def test_move_invalid_object_name(self, mock_conn):
        from blend_ai.tools.collections import move_to_collection

        with pytest.raises(ValidationError):
            move_to_collection([""], "MyCollection")

    def test_move_invalid_collection_name(self, mock_conn):
        from blend_ai.tools.collections import move_to_collection

        with pytest.raises(ValidationError):
            move_to_collection(["Cube"], "")


class TestSetCollectionVisibility:
    def test_hide_collection(self, mock_conn):
        from blend_ai.tools.collections import set_collection_visibility

        set_collection_visibility("MyCollection", visible=False)
        mock_conn.send_command.assert_called_once_with("set_collection_visibility", {
            "name": "MyCollection",
            "visible": False,
            "viewport": True,
            "render": True,
        })

    def test_show_collection_viewport_only(self, mock_conn):
        from blend_ai.tools.collections import set_collection_visibility

        set_collection_visibility("MyCollection", visible=True, viewport=True, render=False)
        mock_conn.send_command.assert_called_once_with("set_collection_visibility", {
            "name": "MyCollection",
            "visible": True,
            "viewport": True,
            "render": False,
        })

    def test_invalid_name(self, mock_conn):
        from blend_ai.tools.collections import set_collection_visibility

        with pytest.raises(ValidationError):
            set_collection_visibility("", visible=True)


class TestDeleteCollection:
    def test_delete_collection_keep_objects(self, mock_conn):
        from blend_ai.tools.collections import delete_collection

        delete_collection("MyCollection")
        mock_conn.send_command.assert_called_once_with("delete_collection", {
            "name": "MyCollection",
            "delete_objects": False,
        })

    def test_delete_collection_with_objects(self, mock_conn):
        from blend_ai.tools.collections import delete_collection

        delete_collection("MyCollection", delete_objects=True)
        mock_conn.send_command.assert_called_once_with("delete_collection", {
            "name": "MyCollection",
            "delete_objects": True,
        })

    def test_delete_invalid_name(self, mock_conn):
        from blend_ai.tools.collections import delete_collection

        with pytest.raises(ValidationError):
            delete_collection("")


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.collections import create_collection

        mock_conn.send_command.return_value = {"status": "error", "result": "Collection exists"}
        with pytest.raises(RuntimeError, match="Blender error"):
            create_collection("MyCollection")
