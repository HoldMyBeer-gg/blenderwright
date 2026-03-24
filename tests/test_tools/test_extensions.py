"""Unit tests for extension suggestion tool."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.tools.scene import suggest_extensions


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    # Default: no extensions installed
    mock.send_command.return_value = {"status": "ok", "result": {"installed": []}}
    with patch("blend_ai.tools.scene.get_connection", return_value=mock):
        yield mock


class TestSuggestExtensions:
    def test_boolean_task_suggests_bool_tool(self, mock_conn):
        """suggest_extensions with boolean task returns Bool Tool suggestion."""
        result = suggest_extensions(task_description="boolean union of two meshes")

        ext_ids = [s["extension_id"] for s in result["suggestions"]]
        assert "bool_tool" in ext_ids

    def test_loop_task_suggests_looptools(self, mock_conn):
        """suggest_extensions with loop task returns LoopTools suggestion."""
        result = suggest_extensions(task_description="editing edge loops on a mesh")

        ext_ids = [s["extension_id"] for s in result["suggestions"]]
        assert "looptools" in ext_ids

    def test_shader_task_suggests_node_wrangler(self, mock_conn):
        """suggest_extensions with shader task returns Node Wrangler suggestion."""
        result = suggest_extensions(task_description="creating shader nodes for material")

        ext_ids = [s["extension_id"] for s in result["suggestions"]]
        assert "node_wrangler" in ext_ids

    def test_unrelated_task_returns_no_suggestions(self, mock_conn):
        """suggest_extensions returns empty suggestions when task matches no keywords."""
        result = suggest_extensions(task_description="moving objects around the scene")

        assert result["suggestions"] == []

    def test_empty_task_returns_all_extensions(self, mock_conn):
        """suggest_extensions with empty task returns all non-installed extensions."""
        result = suggest_extensions(task_description="")

        ext_ids = [s["extension_id"] for s in result["suggestions"]]
        assert "bool_tool" in ext_ids
        assert "looptools" in ext_ids
        assert "node_wrangler" in ext_ids

    def test_calls_get_installed_extensions_command(self, mock_conn):
        """suggest_extensions queries Blender for installed extensions."""
        suggest_extensions(task_description="boolean union")

        mock_conn.send_command.assert_called_once_with("get_installed_extensions")

    def test_suggestion_dict_has_required_keys(self, mock_conn):
        """Each suggestion dict contains name, description, and extension_id keys."""
        result = suggest_extensions(task_description="boolean union of meshes")

        assert len(result["suggestions"]) > 0
        for suggestion in result["suggestions"]:
            assert "name" in suggestion
            assert "description" in suggestion
            assert "extension_id" in suggestion

    def test_error_response_raises_runtime_error(self, mock_conn):
        """RuntimeError is raised when get_installed_extensions returns error."""
        mock_conn.send_command.return_value = {"status": "error", "result": "no connection"}

        with pytest.raises(RuntimeError, match="Blender error: no connection"):
            suggest_extensions(task_description="boolean union")

    def test_result_contains_installed_list(self, mock_conn):
        """Result dict contains installed list from Blender response."""
        result = suggest_extensions(task_description="boolean union")

        assert "installed" in result
        assert result["installed"] == []


class TestInstalledSkipped:
    def test_bool_tool_installed_excluded_from_boolean_suggestions(self, mock_conn):
        """Bool Tool excluded from suggestions when it is already installed."""
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": {"installed": ["bool_tool"]},
        }

        result = suggest_extensions(task_description="boolean union of two meshes")

        ext_ids = [s["extension_id"] for s in result["suggestions"]]
        assert "bool_tool" not in ext_ids

    def test_all_installed_returns_empty_suggestions(self, mock_conn):
        """Empty suggestions list when all matching extensions are already installed."""
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": {"installed": ["bool_tool", "looptools", "node_wrangler"]},
        }

        result = suggest_extensions(task_description="")

        assert result["suggestions"] == []

    def test_partial_install_only_shows_non_installed(self, mock_conn):
        """Only non-installed extensions appear in suggestions."""
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": {"installed": ["looptools"]},
        }

        result = suggest_extensions(task_description="")

        ext_ids = [s["extension_id"] for s in result["suggestions"]]
        assert "looptools" not in ext_ids
        assert "bool_tool" in ext_ids
        assert "node_wrangler" in ext_ids
