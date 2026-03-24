"""Unit tests for auto-critique workflow prompt."""

import sys

# Ensure mcp.prompt() works as identity decorator
_server = sys.modules["blend_ai.server"]
_server.mcp.prompt.return_value = lambda fn: fn

from blend_ai.prompts.workflows import auto_critique_workflow  # noqa: E402

import pytest


class TestAutoCritiquePrompt:
    def test_returns_non_empty_string(self):
        result = auto_critique_workflow()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mentions_get_viewport_screenshot(self):
        result = auto_critique_workflow()
        assert "get_viewport_screenshot" in result

    def test_mentions_fast_mode(self):
        result = auto_critique_workflow()
        assert "fast" in result.lower()

    def test_lists_structural_operations(self):
        result = auto_critique_workflow().lower()
        assert "adding" in result or "add" in result
        assert "boolean" in result
        assert "modifier" in result
        assert "sculpt" in result

    def test_lists_excluded_operations(self):
        result = auto_critique_workflow().lower()
        assert "rename" in result or "renaming" in result
        assert "query" in result or "querying" in result or "scene info" in result

    def test_mentions_token_budget(self):
        result = auto_critique_workflow().lower()
        assert "token" in result or "budget" in result or "limit" in result

    def test_prevents_multi_capture(self):
        result = auto_critique_workflow().lower()
        assert "one screenshot" in result or "once" in result

    def test_includes_critique_checklist(self):
        result = auto_critique_workflow().lower()
        assert "proportion" in result
        assert "topology" in result
