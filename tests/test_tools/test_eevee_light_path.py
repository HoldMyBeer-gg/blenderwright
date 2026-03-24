"""Tests for EEVEE light path intensity controls."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.tools.rendering import set_eevee_light_path


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {
        "status": "ok",
        "result": {
            "diffuse_intensity": 1.0,
            "glossy_intensity": 0.5,
            "transmission_intensity": 0.8,
        },
    }
    with patch("blend_ai.tools.rendering.get_connection", return_value=mock):
        yield mock


class TestSetEeveeLightPath:
    def test_sends_correct_command(self, mock_conn):
        """Sends set_eevee_light_path command."""
        set_eevee_light_path(diffuse_intensity=0.8)

        args = mock_conn.send_command.call_args
        assert args[0][0] == "set_eevee_light_path"

    def test_sends_diffuse_intensity(self, mock_conn):
        """Passes diffuse_intensity parameter."""
        set_eevee_light_path(diffuse_intensity=0.5)

        params = mock_conn.send_command.call_args[0][1]
        assert params["diffuse_intensity"] == 0.5

    def test_sends_glossy_intensity(self, mock_conn):
        """Passes glossy_intensity parameter."""
        set_eevee_light_path(glossy_intensity=0.3)

        params = mock_conn.send_command.call_args[0][1]
        assert params["glossy_intensity"] == 0.3

    def test_sends_transmission_intensity(self, mock_conn):
        """Passes transmission_intensity parameter."""
        set_eevee_light_path(transmission_intensity=0.7)

        params = mock_conn.send_command.call_args[0][1]
        assert params["transmission_intensity"] == 0.7

    def test_sends_all_parameters(self, mock_conn):
        """Passes all three intensity parameters."""
        set_eevee_light_path(
            diffuse_intensity=0.5,
            glossy_intensity=0.3,
            transmission_intensity=0.7,
        )

        params = mock_conn.send_command.call_args[0][1]
        assert params["diffuse_intensity"] == 0.5
        assert params["glossy_intensity"] == 0.3
        assert params["transmission_intensity"] == 0.7

    def test_returns_result(self, mock_conn):
        """Returns result from Blender."""
        result = set_eevee_light_path(diffuse_intensity=0.8)

        assert "diffuse_intensity" in result

    def test_error_response_raises(self, mock_conn):
        """RuntimeError raised on error response."""
        mock_conn.send_command.return_value = {
            "status": "error",
            "result": "not EEVEE engine",
        }

        with pytest.raises(RuntimeError, match="Blender error"):
            set_eevee_light_path(diffuse_intensity=0.5)

    def test_validates_diffuse_range(self):
        """diffuse_intensity outside 0.0-10.0 raises ValidationError."""
        from blend_ai.validators import ValidationError

        with pytest.raises(ValidationError):
            set_eevee_light_path(diffuse_intensity=-1.0)

    def test_validates_glossy_range(self):
        """glossy_intensity outside 0.0-10.0 raises ValidationError."""
        from blend_ai.validators import ValidationError

        with pytest.raises(ValidationError):
            set_eevee_light_path(glossy_intensity=20.0)
