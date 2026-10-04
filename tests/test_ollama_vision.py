"""The vision model has to actually answer, and the chat model has to hear it.

qwen3.5 is a thinking model. With think unset it spent its whole output
budget thinking about the screenshot (17,000 characters), hit the length
limit, and returned empty content. Every vision verdict since the client
was written was an empty string, and the chat model read silence as
approval. Three shuttles in a row ended with "Perfect!".
"""

import json
import math
from unittest.mock import MagicMock, patch

import pytest

from blenderwright.ollama_chat import (
    BlenderChatSession,
    NO_VISION_VERDICT,
    coerce_arguments,
    parse_vector_text,
)


@pytest.fixture
def session():
    with patch("blenderwright.ollama_chat.OllamaClient", MagicMock()):
        s = BlenderChatSession()
    s.tools = []
    s._tool_names = set()
    s.messages = [{"role": "system", "content": "sys"},
                  {"role": "user", "content": "Make a realistic space shuttle"}]
    return s


def _reply(content, done_reason="stop"):
    r = MagicMock()
    r.message.content = content
    r.done_reason = done_reason
    return r


class TestVisionCall:
    def test_thinking_is_off_for_the_vision_call(self, session):
        session.ollama_client.chat.return_value = _reply("A cylinder.")
        session.analyze_screenshot("abc")
        kwargs = session.ollama_client.chat.call_args.kwargs
        assert kwargs["think"] is False

    def test_empty_verdict_becomes_a_visible_placeholder(self, session, capsys):
        session.ollama_client.chat.return_value = _reply("", done_reason="length")
        out = session.analyze_screenshot("abc")
        assert out == NO_VISION_VERDICT
        printed = capsys.readouterr().out
        assert "no description" in printed.lower()
        assert session.vision_model in printed

    def test_whitespace_counts_as_empty(self, session):
        session.ollama_client.chat.return_value = _reply("  \n ")
        assert session.analyze_screenshot("abc") == NO_VISION_VERDICT

    def test_screenshot_critique_names_the_users_request(self, session):
        session.ollama_client.chat.return_value = _reply("Two cones, no wings.")
        shot = json.dumps({"base64": "abc", "width": 10, "height": 10})
        session._describe_screenshot(shot)
        prompt = session.ollama_client.chat.call_args.kwargs["messages"][0]["content"]
        assert "space shuttle" in prompt
        assert "wrong" in prompt.lower()

    def test_critique_prompt_asks_for_problems_not_a_description(self, session):
        session.ollama_client.chat.return_value = _reply("ok")
        session.analyze_screenshot("abc", context="The user asked for: a chair.")
        prompt = session.ollama_client.chat.call_args.kwargs["messages"][0]["content"]
        for word in ("floating", "flat", "scale"):
            assert word in prompt.lower()


class TestVectorText:
    """rotation='[-3.1416/2,0,0]' was sent twice. It is a list; it just arrived
    as a string with a division in it."""

    @pytest.mark.parametrize("text, expected", [
        ("[1, 2, 3]", [1, 2, 3]),
        ("[-3.1416/2, 0, 0]", [-1.5708, 0, 0]),
        ("(0, 0, -3.14/2)", [0, 0, -1.57]),
        ("[pi/2, 0, pi]", [math.pi / 2, 0, math.pi]),
        ("[2*3, 1+1, 4-1]", [6, 2, 3]),
    ])
    def test_lists_with_arithmetic_parse(self, text, expected):
        assert parse_vector_text(text) == pytest.approx(expected)

    @pytest.mark.parametrize("text", [
        "__import__('os').system('x')",
        "[open('/etc/passwd')]",
        "[1, 2, x]",
        "[1 ** 99999999]",
        "[1, 2, 3",
        "hello",
    ])
    def test_anything_else_is_refused(self, text):
        assert parse_vector_text(text) is None

    def test_arguments_are_coerced_from_the_schema(self):
        tools = [{"type": "function", "function": {
            "name": "create_object",
            "parameters": {"type": "object", "properties": {
                "type": {"type": "string"},
                "rotation": {"type": "array"},
                "scale": {"type": "array"},
                "name": {"type": "string"},
            }}}}]
        args = {"type": "CYLINDER", "rotation": "[-3.1416/2,0,0]", "scale": [1, 1, 1],
                "name": "[not a list]"}
        out = coerce_arguments("create_object", args, tools)
        assert out["rotation"] == pytest.approx([-1.5708, 0, 0])
        assert out["scale"] == [1, 1, 1]
        assert out["name"] == "[not a list]"
        assert out["type"] == "CYLINDER"

    def test_unparseable_string_is_left_for_the_validator(self):
        tools = [{"type": "function", "function": {
            "name": "t", "parameters": {"type": "object",
                                        "properties": {"v": {"type": "array"}}}}}]
        assert coerce_arguments("t", {"v": "[1, 2, x]"}, tools) == {"v": "[1, 2, x]"}

    def test_chat_loop_coerces_before_executing(self, session):
        session.tools = [{"type": "function", "function": {
            "name": "create_object",
            "parameters": {"type": "object", "properties": {"rotation": {"type": "array"}}}}}]
        session._tool_names = {"create_object"}
        call = MagicMock()
        call.function.name = "create_object"
        call.function.arguments = {"rotation": "[0, 0, -3.14/2]"}
        first = MagicMock()
        first.message.tool_calls = [call]
        first.message.content = ""
        first.prompt_eval_count = 10
        first.eval_count = 1
        done = MagicMock()
        done.message.tool_calls = None
        done.message.content = "ok"
        done.prompt_eval_count = 10
        done.eval_count = 1
        session.ollama_client.chat.side_effect = [first, done]
        with patch.object(session, "execute_tool", return_value="{}") as ex:
            session.chat("go")
        assert ex.call_args.args[1]["rotation"] == pytest.approx([0, 0, -1.57])


class TestMissingRequiredField:
    """create_light() got 'Field required' and a URL. Name the field and the rest."""

    def test_missing_field_is_named_with_the_parameter_list(self):
        from blenderwright.tool_registry import get_ollama_tools
        from blenderwright.server import mcp
        with patch("blenderwright.ollama_chat.OllamaClient", MagicMock()):
            s = BlenderChatSession()
        s.tools = get_ollama_tools(mcp)
        with patch("blenderwright.tools.lighting.get_connection"):
            out = json.loads(s.execute_tool("create_light", {}))
        assert out["status"] == "error"
        assert "type" in out["result"]
        assert "requires" in out["result"].lower()
        assert "errors.pydantic.dev" not in out["result"]
