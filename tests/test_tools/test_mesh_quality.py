"""Unit tests for mesh quality analysis tool."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.mesh_quality import analyze_mesh_quality


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {
        "status": "ok",
        "result": {
            "object": "Cube",
            "vertex_count": 8,
            "edge_count": 12,
            "face_count": 6,
            "non_manifold_edge_count": 0,
            "non_manifold_edge_indices": [],
            "wire_edge_count": 0,
            "loose_vertex_count": 0,
            "loose_vertex_indices": [],
            "zero_area_face_count": 0,
            "zero_area_face_indices": [],
            "duplicate_vertex_count": 0,
            "issues_found": False,
        },
    }
    with patch("blend_ai.tools.mesh_quality.get_connection", return_value=mock):
        yield mock


class TestAnalyzeMeshQuality:
    def test_sends_correct_command(self, mock_conn):
        """analyze_mesh_quality sends 'analyze_mesh_quality' command with object_name param."""
        analyze_mesh_quality(object_name="Cube")

        mock_conn.send_command.assert_called_once_with(
            "analyze_mesh_quality", {"object_name": "Cube"}
        )

    def test_returns_result(self, mock_conn):
        """analyze_mesh_quality returns the result dict from response."""
        result = analyze_mesh_quality(object_name="Cube")

        assert result["object"] == "Cube"
        assert result["vertex_count"] == 8
        assert result["issues_found"] is False

    def test_error_response_raises(self, mock_conn):
        """analyze_mesh_quality raises RuntimeError on error response from Blender."""
        mock_conn.send_command.return_value = {
            "status": "error",
            "result": "Object 'Missing' not found",
        }

        with pytest.raises(RuntimeError, match="Blender error: Object 'Missing' not found"):
            analyze_mesh_quality(object_name="Missing")

    def test_empty_name_raises_validation_error(self):
        """analyze_mesh_quality raises ValidationError for empty object name."""
        with pytest.raises(ValidationError):
            analyze_mesh_quality(object_name="")

    def test_invalid_chars_raises_validation_error(self):
        """analyze_mesh_quality raises ValidationError for object name with invalid chars."""
        with pytest.raises(ValidationError):
            analyze_mesh_quality(object_name="Cube;rm -rf /")
