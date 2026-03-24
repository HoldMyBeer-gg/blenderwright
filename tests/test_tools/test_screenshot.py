"""Unit tests for viewport screenshot MCP tool."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.tools.screenshot import get_viewport_screenshot


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {
        "status": "ok",
        "result": {
            "base64": "dGVzdA==",
            "format": "png",
            "width": 1000,
            "height": 562,
            "mode": "fast",
        },
    }
    with patch("blend_ai.tools.screenshot.get_connection", return_value=mock):
        yield mock


class TestGetViewportScreenshot:
    def test_fast_mode_sends_fast_command(self, mock_conn):
        """mode='fast' sends fast_viewport_capture command."""
        get_viewport_screenshot(mode="fast")

        args = mock_conn.send_command.call_args
        assert args[0][0] == "fast_viewport_capture"

    def test_full_mode_sends_capture_command(self, mock_conn):
        """mode='full' sends capture_viewport command (existing behavior)."""
        get_viewport_screenshot(mode="full")

        args = mock_conn.send_command.call_args
        assert args[0][0] == "capture_viewport"

    def test_default_mode_is_fast(self, mock_conn):
        """Default mode is 'fast'."""
        get_viewport_screenshot()

        args = mock_conn.send_command.call_args
        assert args[0][0] == "fast_viewport_capture"

    def test_passes_width_height(self, mock_conn):
        """Width and height are passed based on max_size."""
        get_viewport_screenshot(max_size=500)

        args = mock_conn.send_command.call_args
        params = args[0][1]
        assert "width" in params
        assert "height" in params
        assert params["width"] == 500

    def test_error_response_raises(self, mock_conn):
        """RuntimeError raised on error response."""
        mock_conn.send_command.return_value = {
            "status": "error",
            "result": "capture failed",
        }

        with pytest.raises(RuntimeError, match="Screenshot failed"):
            get_viewport_screenshot()

    def test_returns_result(self, mock_conn):
        """Returns the result dict from Blender."""
        result = get_viewport_screenshot()

        assert "base64" in result
        assert result["format"] == "png"

    def test_max_size_validation_too_small(self):
        """max_size below 64 raises ValidationError."""
        from blend_ai.validators import ValidationError

        with pytest.raises(ValidationError):
            get_viewport_screenshot(max_size=10)

    def test_max_size_validation_too_large(self):
        """max_size above 4096 raises ValidationError."""
        from blend_ai.validators import ValidationError

        with pytest.raises(ValidationError):
            get_viewport_screenshot(max_size=10000)

    def test_invalid_mode_raises(self):
        """Invalid mode raises ValidationError."""
        from blend_ai.validators import ValidationError

        with pytest.raises(ValidationError):
            get_viewport_screenshot(mode="invalid")
