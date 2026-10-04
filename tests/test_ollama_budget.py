"""The chat loop is bounded by the context window, not by a call counter.

A shuttle is more than 25 tool calls for any model. The old cap stopped a
local model mid-fuselage with 47k tokens of window unused, and reported it
as the model's fault. Ollama returns prompt_eval_count and eval_count on
every response, so the loop can run until the window is nearly full and say
so when it stops.

Separately, the same session spent five of its rounds calling list_objects
with nothing changed in between. A repeated read-only call is answered from
the previous result without a round trip, with a note to move on.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from blenderwright.ollama_chat import (
    BlenderChatSession,
    CONTEXT_RESERVE,
    MAX_TOOL_ROUNDS,
    READ_ONLY_TOOLS,
    context_exhausted,
)


def _response(content="", tool_calls=None, prompt_eval=None, eval_count=None):
    r = MagicMock()
    r.message.content = content
    r.message.tool_calls = tool_calls
    r.prompt_eval_count = prompt_eval
    r.eval_count = eval_count
    return r


def _call(name, **args):
    c = MagicMock()
    c.function.name = name
    c.function.arguments = args
    return c


@pytest.fixture
def session():
    with patch("blenderwright.ollama_chat.OllamaClient", MagicMock()):
        s = BlenderChatSession(num_ctx=20_000)
    s.tools = []
    s._tool_names = {"list_objects", "create_object", "get_scene_info", "get_object_info"}
    s.messages = [{"role": "system", "content": "sys"}]
    return s


class TestBudget:
    def test_hard_cap_is_a_backstop_not_a_budget(self):
        assert MAX_TOOL_ROUNDS >= 100

    def test_reserve_leaves_room_for_a_reply(self):
        assert 1024 <= CONTEXT_RESERVE <= 8192

    def test_not_exhausted_with_room(self):
        assert not context_exhausted(_response(prompt_eval=5_000, eval_count=200), num_ctx=20_000)

    def test_exhausted_when_inside_the_reserve(self):
        used = 20_000 - CONTEXT_RESERVE + 1
        assert context_exhausted(_response(prompt_eval=used, eval_count=0), num_ctx=20_000)

    def test_missing_counts_do_not_stop_the_loop(self):
        # Some Ollama builds omit the counts; a MagicMock would be truthy.
        assert not context_exhausted(_response(), num_ctx=20_000)
        assert not context_exhausted(_response(prompt_eval=MagicMock()), num_ctx=20_000)

    def test_loop_stops_when_the_window_fills(self, session):
        full = 20_000 - CONTEXT_RESERVE + 10
        session.ollama_client.chat.side_effect = [
            _response(tool_calls=[_call("create_object", type="CUBE")], prompt_eval=1_000, eval_count=50),
            _response(tool_calls=[_call("create_object", type="CUBE")], prompt_eval=full, eval_count=50),
            _response(content="should not be reached"),
        ]
        with patch.object(session, "execute_tool", return_value='{"name": "Cube"}') as ex:
            reply = session.chat("build")
        assert ex.call_count == 2
        assert "context" in reply.lower()
        assert "maximum tool-calling rounds" not in reply
        assert session.ollama_client.chat.call_count == 2

    def test_stop_message_says_how_much_was_used(self, session):
        full = 20_000 - CONTEXT_RESERVE + 10
        session.ollama_client.chat.side_effect = [
            _response(tool_calls=[_call("create_object", type="CUBE")], prompt_eval=full, eval_count=0),
        ]
        with patch.object(session, "execute_tool", return_value='{"name": "Cube"}'):
            reply = session.chat("build")
        assert "20,000" in reply

    def test_a_text_reply_near_the_limit_is_still_returned(self, session):
        # Exhaustion only cuts off further tool rounds; a finished answer
        # is a finished answer.
        full = 20_000 - CONTEXT_RESERVE + 10
        session.ollama_client.chat.side_effect = [
            _response(content="Done.", prompt_eval=full, eval_count=5),
        ]
        assert session.chat("build") == "Done."


class TestRepeatedReadOnlyCalls:
    def test_read_only_set_covers_the_pollers(self):
        for name in ("list_objects", "get_scene_info", "get_object_info", "get_selection"):
            assert name in READ_ONLY_TOOLS
        assert "create_object" not in READ_ONLY_TOOLS

    def test_identical_read_only_call_is_answered_from_cache(self, session):
        session.ollama_client.chat.side_effect = [
            _response(tool_calls=[_call("list_objects")]),
            _response(tool_calls=[_call("list_objects")]),
            _response(tool_calls=[_call("list_objects")]),
            _response(content="ok"),
        ]
        with patch.object(session, "execute_tool", return_value='{"objects": ["Cube"]}') as ex:
            session.chat("look")
        assert ex.call_count == 1
        tool_msgs = [m for m in session.messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 3
        second = json.loads(tool_msgs[1]["content"])
        assert second["status"] == "unchanged"
        assert "objects" in second["result"]
        assert "continue" in second["note"].lower()

    def test_a_change_in_between_resets_the_cache(self, session):
        session.ollama_client.chat.side_effect = [
            _response(tool_calls=[_call("list_objects")]),
            _response(tool_calls=[_call("create_object", type="CUBE")]),
            _response(tool_calls=[_call("list_objects")]),
            _response(content="ok"),
        ]
        with patch.object(session, "execute_tool", return_value='{"r": 1}') as ex:
            session.chat("look")
        assert ex.call_count == 3

    def test_different_arguments_are_not_a_repeat(self, session):
        session.ollama_client.chat.side_effect = [
            _response(tool_calls=[_call("get_object_info", object_name="A")]),
            _response(tool_calls=[_call("get_object_info", object_name="B")]),
            _response(content="ok"),
        ]
        with patch.object(session, "execute_tool", return_value='{"r": 1}') as ex:
            session.chat("look")
        assert ex.call_count == 2

    def test_repeated_mutating_call_still_runs(self, session):
        # Two identical create_object calls may be two parts. Not ours to block.
        session.ollama_client.chat.side_effect = [
            _response(tool_calls=[_call("create_object", type="CUBE")]),
            _response(tool_calls=[_call("create_object", type="CUBE")]),
            _response(content="ok"),
        ]
        with patch.object(session, "execute_tool", return_value='{"r": 1}') as ex:
            session.chat("build")
        assert ex.call_count == 2

    def test_cache_does_not_leak_across_user_messages(self, session):
        session.ollama_client.chat.side_effect = [
            _response(tool_calls=[_call("list_objects")]),
            _response(content="ok"),
            _response(tool_calls=[_call("list_objects")]),
            _response(content="ok"),
        ]
        with patch.object(session, "execute_tool", return_value='{"r": 1}') as ex:
            session.chat("look")
            session.chat("look again")
        assert ex.call_count == 2


class TestScreenshotNeverReachesTheChatModel:
    """The handlers return the PNG under "base64". The client looked for "image".

    So the vision step never ran, and the whole encoded PNG went into the
    conversation as a tool message: tens of thousands of tokens of
    base64 that the chat model cannot read. The next reply came back empty.
    The image goes to the vision model; the chat model gets the words.
    """

    @pytest.mark.parametrize("tool", ["get_viewport_screenshot", "capture_viewport"])
    def test_base64_key_triggers_vision_and_is_stripped(self, session, tool):
        session._tool_names |= {tool}
        png = "iVBORw0KGgo" * 2000
        shot = json.dumps({"base64": png, "width": 1000, "height": 562, "format": "PNG"})
        session.ollama_client.chat.side_effect = [
            _response(tool_calls=[_call(tool)]),
            _response(content="Looks right."),
        ]
        with patch.object(session, "execute_tool", return_value=shot), \
             patch.object(session, "analyze_screenshot", return_value="A grey cone.") as vision:
            session.chat("check")
        vision.assert_called_once()
        assert vision.call_args.args[0] == png
        tool_msg = [m for m in session.messages if m.get("role") == "tool"][-1]
        assert png[:40] not in tool_msg["content"]
        parsed = json.loads(tool_msg["content"])
        assert parsed["vision_analysis"] == "A grey cone."
        assert parsed["width"] == 1000
        assert "base64" not in parsed

    def test_legacy_image_key_still_works(self, session):
        session._tool_names |= {"get_viewport_screenshot"}
        shot = json.dumps({"image": "abc", "width": 10, "height": 10})
        session.ollama_client.chat.side_effect = [
            _response(tool_calls=[_call("get_viewport_screenshot")]),
            _response(content="ok"),
        ]
        with patch.object(session, "execute_tool", return_value=shot), \
             patch.object(session, "analyze_screenshot", return_value="x") as vision:
            session.chat("check")
        vision.assert_called_once_with("abc")
        tool_msg = [m for m in session.messages if m.get("role") == "tool"][-1]
        assert "image" not in json.loads(tool_msg["content"])

    def test_vision_failure_still_strips_the_image(self, session):
        session._tool_names |= {"get_viewport_screenshot"}
        png = "iVBORw0KGgo" * 2000
        shot = json.dumps({"base64": png, "width": 10, "height": 10})
        session.ollama_client.chat.side_effect = [
            _response(tool_calls=[_call("get_viewport_screenshot")]),
            _response(content="ok"),
        ]
        with patch.object(session, "execute_tool", return_value=shot), \
             patch.object(session, "analyze_screenshot", side_effect=RuntimeError("no vision model")):
            session.chat("check")
        tool_msg = [m for m in session.messages if m.get("role") == "tool"][-1]
        assert png[:40] not in tool_msg["content"]
        assert "no vision model" in tool_msg["content"]
