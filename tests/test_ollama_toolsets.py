"""The Ollama client is the one place the window size is known, so it decides.

Over MCP the server never learns which model is on the other end. The bundled
Ollama client passes num_ctx itself and already estimates what the schemas
cost, so when the full set would leave less than half the window for the
conversation it starts in auto mode and says so. An explicit --toolsets or
BLENDERWRIGHT_TOOLSETS always wins over the estimate.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from blenderwright.server import mcp
from blenderwright.toolsets import CORE, META_TOOLS, restore_all, tools_by_toolset
from blenderwright.ollama_chat import BlenderChatSession, choose_toolsets

GROUPED = tools_by_toolset(mcp)
ALL_COUNT = sum(len(v) for v in GROUPED.values())
CORE_COUNT = sum(len(GROUPED[t]) for t in CORE)


@pytest.fixture(autouse=True)
def _restore():
    restore_all(mcp)
    yield
    restore_all(mcp)


@pytest.fixture
def session_factory(monkeypatch):
    """Build a session against the real registry with Ollama and Blender mocked."""
    monkeypatch.delenv("BLENDERWRIGHT_TOOLSETS", raising=False)
    conn = MagicMock()
    with patch("blenderwright.ollama_chat.OllamaClient", MagicMock()), \
         patch("blenderwright.connection.BlenderConnection", return_value=conn):
        def make(**kwargs):
            s = BlenderChatSession(**kwargs)
            s.initialize()
            return s
        yield make


class TestDecision:
    def test_full_set_fits_in_a_big_window(self):
        assert choose_toolsets(prompt_tokens=50_000, num_ctx=131_072) == "all"

    def test_full_set_crowds_a_small_window(self):
        assert choose_toolsets(prompt_tokens=50_000, num_ctx=65_536) == "auto"

    def test_boundary_is_half_the_window(self):
        assert choose_toolsets(prompt_tokens=32_768, num_ctx=65_536) == "all"
        assert choose_toolsets(prompt_tokens=32_769, num_ctx=65_536) == "auto"


class TestInitialize:
    def test_small_window_starts_in_auto(self, session_factory, capsys):
        s = session_factory(num_ctx=32_768)
        assert s.toolset_mode == "auto"
        assert len(s.tools) == CORE_COUNT + len(META_TOOLS)
        assert "enable_toolset" in s._tool_names
        out = capsys.readouterr().out
        assert "auto" in out
        assert "--toolsets all" in out

    def test_big_window_keeps_everything(self, session_factory):
        s = session_factory(num_ctx=262_144)
        assert s.toolset_mode == "all"
        assert len(s.tools) == ALL_COUNT
        assert "enable_toolset" not in s._tool_names

    def test_explicit_all_beats_the_estimate(self, session_factory):
        s = session_factory(num_ctx=32_768, toolsets="all")
        assert s.toolset_mode == "all"
        assert len(s.tools) == ALL_COUNT

    def test_explicit_static_list(self, session_factory):
        s = session_factory(num_ctx=262_144, toolsets="modeling")
        assert s.toolset_mode == "static"
        assert s._tool_names == set(GROUPED["modeling"])

    def test_env_var_is_honoured(self, session_factory, monkeypatch):
        monkeypatch.setenv("BLENDERWRIGHT_TOOLSETS", "materials")
        s = session_factory(num_ctx=262_144)
        assert s._tool_names == set(GROUPED["materials"])

    def test_auto_prompt_lists_the_menu(self, session_factory):
        s = session_factory(num_ctx=32_768)
        prompt = s.messages[0]["content"]
        assert "enable_toolset" in prompt
        for name in ("physics", "sculpting", "materials"):
            assert name in prompt

    def test_full_prompt_has_no_menu(self, session_factory):
        s = session_factory(num_ctx=262_144)
        assert "enable_toolset" not in s.messages[0]["content"]


class TestResultUnwrapping:
    """FastMCP returns (content, structured) for a dict-returning tool.

    The client used to take element zero of that tuple, find it was a list
    with no .text, and json.dumps the whole tuple with default=str. The
    model then saw a repr of a TextContent object instead of the result.
    """

    def test_dict_result_reaches_the_model_as_json(self, session_factory):
        import blenderwright.server as srv

        s = session_factory(num_ctx=262_144)
        srv._connection.send_command.return_value = {
            "status": "ok", "result": {"name": "Cube", "location": [0, 0, 0]},
        }
        text = s.execute_tool("get_object_info", {"object_name": "Cube"})
        parsed = json.loads(text)
        assert parsed == {"name": "Cube", "location": [0, 0, 0]}
        assert "TextContent" not in text and "type='text'" not in text


class TestEnableDuringChat:
    def test_enabling_refreshes_tools_and_prompt(self, session_factory):
        s = session_factory(num_ctx=32_768)
        assert "add_rigid_body" not in s._tool_names

        enable_call = MagicMock()
        enable_call.function.name = "enable_toolset"
        enable_call.function.arguments = {"name": "physics"}
        first = MagicMock()
        first.message.tool_calls = [enable_call]
        first.message.content = ""
        done = MagicMock()
        done.message.tool_calls = None
        done.message.content = "Physics is on."
        s.ollama_client.chat.side_effect = [first, done]

        reply = s.chat("make it fall")

        assert reply == "Physics is on."
        assert "add_rigid_body" in s._tool_names
        assert any(t["function"]["name"] == "add_rigid_body" for t in s.tools)
        assert "add_rigid_body" in s.messages[0]["content"]
        # The second request carried the enlarged tool list.
        second_kwargs = s.ollama_client.chat.call_args_list[1].kwargs
        names = {t["function"]["name"] for t in second_kwargs["tools"]}
        assert "add_rigid_body" in names

    def test_enable_result_names_the_new_tools(self, session_factory):
        s = session_factory(num_ctx=32_768)
        result = json.loads(s.execute_tool("enable_toolset", {"name": "animation"}))
        assert result["enabled"] == "animation"
        assert "insert_keyframe" in result["tools"]
