"""Unit tests for generated image texture tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.materials import (
    RASTER_PATTERNS,
    MAX_RASTER_SIZE,
    create_raster_texture,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"image": "Runes"}}
    with patch("blend_ai.tools.materials.get_connection", return_value=mock):
        yield mock


class TestPatternTable:
    def test_covers_runes(self):
        assert "runes" in RASTER_PATTERNS

    def test_does_not_duplicate_shader_patterns(self):
        """Anything a shader node can do belongs in create_procedural_material."""
        from blend_ai.tools.materials import PROCEDURAL_PATTERNS

        assert not (RASTER_PATTERNS & PROCEDURAL_PATTERNS)


class TestCreateRasterTexture:
    def test_minimal_call(self, mock_conn):
        create_raster_texture("Glyphs", "runes")
        command, params = mock_conn.send_command.call_args[0]
        assert command == "create_raster_texture"
        assert params["name"] == "Glyphs"
        assert params["pattern"] == "runes"

    def test_defaults(self, mock_conn):
        create_raster_texture("G", "runes")
        params = mock_conn.send_command.call_args[0][1]
        assert params["size"] == 512
        assert params["count"] == 12
        assert params["seed"] == 0
        assert len(params["foreground"]) == 4
        assert len(params["background"]) == 4

    def test_custom_values_forwarded(self, mock_conn):
        create_raster_texture("G", "runes", size=256, count=30, seed=99)
        params = mock_conn.send_command.call_args[0][1]
        assert params["size"] == 256
        assert params["count"] == 30
        assert params["seed"] == 99

    def test_rgb_colors_padded_to_rgba(self, mock_conn):
        create_raster_texture(
            "G", "runes", foreground=[1.0, 0.0, 0.0], background=[0.0, 0.0, 0.0]
        )
        params = mock_conn.send_command.call_args[0][1]
        assert params["foreground"] == [1.0, 0.0, 0.0, 1.0]
        assert params["background"] == [0.0, 0.0, 0.0, 1.0]

    def test_unknown_pattern_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_raster_texture("G", "fire")

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_raster_texture("", "runes")

    def test_zero_size_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_raster_texture("G", "runes", size=0)

    def test_oversized_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_raster_texture("G", "runes", size=MAX_RASTER_SIZE + 1)

    def test_negative_count_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_raster_texture("G", "runes", count=-1)

    def test_negative_seed_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_raster_texture("G", "runes", seed=-1)

    def test_malformed_color_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_raster_texture("G", "runes", foreground=[1.0, 0.0])

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            create_raster_texture("G", "runes")
