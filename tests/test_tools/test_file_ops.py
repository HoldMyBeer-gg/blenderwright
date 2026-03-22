"""Unit tests for file operations tools."""

import os
import tempfile

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"success": True}}
    with patch("blend_ai.tools.file_ops.get_connection", return_value=mock):
        yield mock


@pytest.fixture
def temp_blend_file():
    """Create a temporary .blend file for must_exist tests."""
    fd, path = tempfile.mkstemp(suffix=".blend")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def temp_fbx_file():
    """Create a temporary .fbx file for import tests."""
    fd, path = tempfile.mkstemp(suffix=".fbx")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestImportFile:
    def test_import_file(self, mock_conn, temp_fbx_file):
        from blend_ai.tools.file_ops import import_file

        import_file(temp_fbx_file)
        call_args = mock_conn.send_command.call_args
        assert call_args[0][0] == "import_file"
        assert call_args[0][1]["filepath"].endswith(".fbx")

    def test_import_file_with_type(self, mock_conn, temp_fbx_file):
        from blend_ai.tools.file_ops import import_file

        import_file(temp_fbx_file, type="FBX")
        call_args = mock_conn.send_command.call_args
        assert call_args[0][1]["type"] == "FBX"

    def test_import_file_must_exist(self, mock_conn):
        from blend_ai.tools.file_ops import import_file

        with pytest.raises(ValidationError, match="File does not exist"):
            import_file("/tmp/nonexistent_file_xyz123.fbx")

    def test_import_file_invalid_extension(self, mock_conn):
        from blend_ai.tools.file_ops import import_file

        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            with pytest.raises(ValidationError, match="not allowed"):
                import_file(path)
        finally:
            os.unlink(path)

    def test_import_file_invalid_type_override(self, mock_conn, temp_fbx_file):
        from blend_ai.tools.file_ops import import_file

        with pytest.raises(ValidationError):
            import_file(temp_fbx_file, type="INVALID")


class TestExportFile:
    def test_export_file(self, mock_conn):
        from blend_ai.tools.file_ops import export_file

        export_file("/tmp/export.obj")
        call_args = mock_conn.send_command.call_args
        assert call_args[0][0] == "export_file"
        assert call_args[0][1]["selected_only"] is False

    def test_export_file_selected_only(self, mock_conn):
        from blend_ai.tools.file_ops import export_file

        export_file("/tmp/export.fbx", selected_only=True)
        call_args = mock_conn.send_command.call_args
        assert call_args[0][1]["selected_only"] is True

    def test_export_file_with_type(self, mock_conn):
        from blend_ai.tools.file_ops import export_file

        export_file("/tmp/export.fbx", type="FBX")
        call_args = mock_conn.send_command.call_args
        assert call_args[0][1]["type"] == "FBX"

    def test_export_file_invalid_extension(self, mock_conn):
        from blend_ai.tools.file_ops import export_file

        with pytest.raises(ValidationError, match="not allowed"):
            export_file("/tmp/export.mp4")

    def test_export_does_not_require_exist(self, mock_conn):
        from blend_ai.tools.file_ops import export_file

        export_file("/tmp/new_export_file.stl")
        mock_conn.send_command.assert_called_once()


class TestSaveFile:
    def test_save_file_no_path(self, mock_conn):
        from blend_ai.tools.file_ops import save_file

        save_file()
        mock_conn.send_command.assert_called_once_with("save_file", {"filepath": ""})

    def test_save_file_with_path(self, mock_conn):
        from blend_ai.tools.file_ops import save_file

        save_file(filepath="/tmp/my_scene.blend")
        call_args = mock_conn.send_command.call_args
        assert call_args[0][0] == "save_file"
        assert call_args[0][1]["filepath"].endswith(".blend")

    def test_save_file_invalid_extension(self, mock_conn):
        from blend_ai.tools.file_ops import save_file

        with pytest.raises(ValidationError, match="not allowed"):
            save_file(filepath="/tmp/scene.fbx")


class TestOpenFile:
    def test_open_file(self, mock_conn, temp_blend_file):
        from blend_ai.tools.file_ops import open_file

        open_file(temp_blend_file)
        call_args = mock_conn.send_command.call_args
        assert call_args[0][0] == "open_file"
        assert call_args[0][1]["filepath"].endswith(".blend")

    def test_open_file_must_exist(self, mock_conn):
        from blend_ai.tools.file_ops import open_file

        with pytest.raises(ValidationError, match="File does not exist"):
            open_file("/tmp/nonexistent_scene_xyz123.blend")

    def test_open_file_wrong_extension(self, mock_conn):
        from blend_ai.tools.file_ops import open_file

        fd, path = tempfile.mkstemp(suffix=".fbx")
        os.close(fd)
        try:
            with pytest.raises(ValidationError, match="not allowed"):
                open_file(path)
        finally:
            os.unlink(path)


class TestListRecentFiles:
    def test_list_recent_files(self, mock_conn):
        from blend_ai.tools.file_ops import list_recent_files

        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": ["/tmp/scene1.blend", "/tmp/scene2.blend"],
        }
        result = list_recent_files()
        mock_conn.send_command.assert_called_once_with("list_recent_files")
        assert len(result) == 2

    def test_list_recent_files_empty(self, mock_conn):
        from blend_ai.tools.file_ops import list_recent_files

        mock_conn.send_command.return_value = {"status": "ok", "result": []}
        result = list_recent_files()
        assert result == []


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.file_ops import list_recent_files

        mock_conn.send_command.return_value = {"status": "error", "result": "Permission denied"}
        with pytest.raises(RuntimeError, match="Blender error"):
            list_recent_files()
