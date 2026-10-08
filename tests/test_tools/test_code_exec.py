"""Unit tests for code_exec MCP tool."""

import pytest
from unittest.mock import patch, MagicMock

from blenderwright.tools.code_exec import execute_blender_code


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {
        "status": "ok",
        "result": {"output": "hello", "success": True},
    }
    with patch("blenderwright.tools.code_exec.get_connection", return_value=mock):
        yield mock


class TestExecuteBlenderCode:
    def test_empty_code_raises(self):
        """Empty code raises ValueError."""
        with pytest.raises(ValueError):
            execute_blender_code(code="")

    def test_whitespace_only_raises(self):
        """Whitespace-only code raises ValueError."""
        with pytest.raises(ValueError):
            execute_blender_code(code="   \n  ")

    def test_sends_execute_code_command(self, mock_conn):
        """Valid code sends execute_code command."""
        execute_blender_code(code="print('hi')")

        mock_conn.send_command.assert_called_once()
        args = mock_conn.send_command.call_args
        assert args[0][0] == "execute_code"
        assert args[0][1]["code"] == "print('hi')"

    def test_returns_result(self, mock_conn):
        """Returns the result dict from Blender."""
        result = execute_blender_code(code="print('hi')")

        assert result["output"] == "hello"
        assert result["success"] is True

    def test_error_response_raises(self, mock_conn):
        """RuntimeError raised on error response."""
        mock_conn.send_command.return_value = {
            "status": "error",
            "result": "SyntaxError: invalid syntax",
        }

        with pytest.raises(RuntimeError, match="Blender error"):
            execute_blender_code(code="print(")

    def test_disabled_in_blender_raises_with_hint(self, mock_conn):
        """When the user has not enabled raw Python, the error says how to."""
        mock_conn.send_command.return_value = {
            "status": "error",
            "result": "PermissionError: execute_blender_code is disabled. "
            "Tick 'Allow raw Python' in the blenderwright panel.",
        }
        with pytest.raises(RuntimeError, match="Allow raw Python"):
            execute_blender_code(code="print('x')")

    def test_docstring_says_off_by_default(self):
        """The model must learn from the tool description that it is opt-in."""
        doc = execute_blender_code.__doc__ or ""
        assert "off by default" in doc.lower()
        assert "not a security boundary" in doc.lower()
