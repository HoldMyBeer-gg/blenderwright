"""Tests for blend_ai.ollama_chat."""

import json
import pytest
from unittest.mock import MagicMock, patch

from blend_ai.ollama_chat import (
    BlenderChatSession,
    _build_tool_list,
    _format_args,
    _parse_text_tool_calls,
    _strip_tool_markup,
    _find_similar_tools,
    parse_image_command,
    load_image_as_base64,
    SUPPORTED_IMAGE_FORMATS,
    SYSTEM_PROMPT_BASE,
    DEFAULT_CHAT_MODEL,
    DEFAULT_VISION_MODEL,
)


@pytest.fixture
def mock_ollama_client():
    """Mock the OllamaClient instance."""
    with patch("blend_ai.ollama_chat.OllamaClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_blender_connection():
    """Mock BlenderConnection for chat session."""
    with patch("blend_ai.connection.BlenderConnection") as mock_cls:
        mock_conn = MagicMock()
        mock_conn.send_command.return_value = {"status": "ok", "result": {"name": "Cube"}}
        mock_cls.return_value = mock_conn
        # Also patch the server module's connection
        with patch("blend_ai.server._connection", mock_conn, create=True):
            with patch("blend_ai.server.get_connection", return_value=mock_conn):
                yield mock_conn


@pytest.fixture
def mock_mcp_tools():
    """Mock the tool registry to return sample tools."""
    sample_tools = [
        {
            "type": "function",
            "function": {
                "name": "create_object",
                "description": "Create a primitive object.",
                "parameters": {
                    "type": "object",
                    "properties": {"type": {"type": "string"}},
                    "required": ["type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_viewport_screenshot",
                "description": "Capture viewport.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    ]
    with patch("blend_ai.ollama_chat.get_ollama_tools", return_value=sample_tools):
        yield sample_tools


class TestConstants:
    def test_max_tool_rounds_is_25(self):
        from blend_ai.ollama_chat import MAX_TOOL_ROUNDS
        assert MAX_TOOL_ROUNDS == 25

    def test_system_prompt_has_modeling_strategy(self):
        assert "Modeling strategy" in SYSTEM_PROMPT_BASE

    def test_system_prompt_organic_uses_sculpt(self):
        assert "sculpt" in SYSTEM_PROMPT_BASE.lower() or "Sculpt" in SYSTEM_PROMPT_BASE

    def test_system_prompt_hard_surface_box_model(self):
        assert "hard surface" in SYSTEM_PROMPT_BASE.lower() or "hard-surface" in SYSTEM_PROMPT_BASE.lower()

    def test_system_prompt_has_planning_step(self):
        assert "plan" in SYSTEM_PROMPT_BASE.lower()

    def test_system_prompt_mentions_boolean(self):
        assert "boolean" in SYSTEM_PROMPT_BASE.lower() or "Boolean" in SYSTEM_PROMPT_BASE

    def test_system_prompt_mentions_subdivision(self):
        assert "subdivision" in SYSTEM_PROMPT_BASE.lower() or "Subdivision" in SYSTEM_PROMPT_BASE


class TestContextWindow:
    """The 175 tool schemas cost ~31,000 tokens of every request.

    Measured against the live model: the prompt alone was 31,086 tokens
    against a hardcoded num_ctx of 32,768, leaving under 1,700 tokens for up
    to MAX_TOOL_ROUNDS rounds of calls and results. Work overflowed the
    window mid-task and Ollama silently dropped messages, which looked like
    the model giving up early.
    """

    def test_default_context_has_room_for_the_tool_schemas(self):
        from blend_ai.ollama_chat import DEFAULT_NUM_CTX
        assert DEFAULT_NUM_CTX >= 65536, (
            "The tool schemas alone are ~31k tokens; anything near 32k leaves "
            "no working room for tool results."
        )

    def test_num_ctx_is_configurable(self):
        from blend_ai.ollama_chat import BlenderChatSession
        session = BlenderChatSession(num_ctx=12345)
        assert session.num_ctx == 12345

    def test_session_sends_the_configured_context(self):
        from unittest.mock import MagicMock, patch
        from blend_ai.ollama_chat import BlenderChatSession

        session = BlenderChatSession(num_ctx=99999)
        session.tools = []
        session._tool_names = set()
        session.messages = []

        captured = {}

        def fake_chat(**kwargs):
            captured.update(kwargs)
            resp = MagicMock()
            resp.message.tool_calls = []
            resp.message.content = "done"
            return resp

        with patch.object(session, "ollama_client") as client:
            client.chat = fake_chat
            session.chat("hello")

        assert captured["options"]["num_ctx"] == 99999, (
            "The session must send the configured window, not a hardcoded one."
        )

    def test_context_budget_is_reported(self):
        """Silent truncation is the failure mode; make the number visible."""
        import inspect
        from blend_ai import ollama_chat
        src = inspect.getsource(ollama_chat)
        assert "prompt_tokens" in src or "context budget" in src.lower(), (
            "Startup should report how much of the window the tools consume."
        )


class TestPrimitiveGuidance:
    """A local model asked for a rocket built four cubes, 74m tall and 2m deep.

    It was obedient, not confused: the strategy section routed every
    mechanical object to CUBE, and mentioned CYLINDER only under organic
    shapes. Nothing asked for all three axes to be sized, so it modelled a
    front elevation and left Y alone.
    """

    def test_cylinder_is_offered_for_cylindrical_hard_surface(self):
        """Rockets, pipes, tanks and barrels are the obvious cylinder cases."""
        prompt = SYSTEM_PROMPT_BASE.lower()
        assert "cylinder" in prompt
        cylindrical = ("rocket", "pipe", "tank", "barrel", "bottle", "column")
        assert any(word in prompt for word in cylindrical), (
            "The strategy section names no cylindrical object, so a model "
            "reading 'hard-surface' reaches for CUBE every time."
        )

    def test_primitive_choice_is_by_shape_not_category(self):
        """'mechanical -> CUBE' is the exact rule that produced a boxy rocket."""
        prompt = SYSTEM_PROMPT_BASE.lower()
        assert "silhouette" in prompt or "match the shape" in prompt, (
            "Primitive choice should follow the object's silhouette, not a "
            "category label."
        )

    def test_all_three_axes_are_required(self):
        prompt = SYSTEM_PROMPT_BASE.lower()
        assert "all three" in prompt or "x, y and z" in prompt or "x, y, z" in prompt, (
            "Nothing tells the model to size depth as well as width and "
            "height, so it produces flat cutouts."
        )

    def test_warns_against_leaving_an_axis_at_default(self):
        prompt = SYSTEM_PROMPT_BASE.lower()
        assert "flat" in prompt or "cutout" in prompt or "cardboard" in prompt, (
            "The failure mode is worth naming so the model recognises it."
        )

    def test_parts_must_be_positioned_relative_to_each_other(self):
        """It put both stages at the same z and the engines off to one side."""
        prompt = SYSTEM_PROMPT_BASE.lower()
        assert "stack" in prompt or "overlap" in prompt or "touch" in prompt, (
            "Nothing tells the model that assembled parts must actually meet."
        )


class TestBlenderChatSession:
    def test_init_defaults(self, mock_ollama_client):
        session = BlenderChatSession()
        assert session.chat_model == DEFAULT_CHAT_MODEL
        assert session.vision_model == DEFAULT_VISION_MODEL

    def test_init_custom_params(self, mock_ollama_client):
        session = BlenderChatSession(
            chat_model="llama3",
            vision_model="llava:34b",
            host="192.168.1.1",
            port=1234,
        )
        assert session.chat_model == "llama3"
        assert session.vision_model == "llava:34b"

    def test_init_ollama_host(self):
        with patch("blend_ai.ollama_chat.OllamaClient") as mock_cls:
            BlenderChatSession(ollama_host="http://myserver:11434")
            mock_cls.assert_called_with(host="http://myserver:11434")

    def test_initialize(self, mock_ollama_client, mock_blender_connection, mock_mcp_tools):
        with patch("blend_ai.connection.BlenderConnection", return_value=mock_blender_connection):
            session = BlenderChatSession()
            session.initialize()
            mock_blender_connection.connect.assert_called_once()
            assert len(session.tools) == 2
            assert session._tool_names == {"create_object", "get_viewport_screenshot"}
            assert session.messages[0]["role"] == "system"
            assert "create_object" in session.messages[0]["content"]
            assert "get_viewport_screenshot" in session.messages[0]["content"]

    def test_execute_tool(self, mock_ollama_client, mock_blender_connection):
        """Test tool execution routes through MCP call_tool."""
        mock_text = MagicMock()
        mock_text.text = '{"name": "Cube"}'

        async def _fake_call_tool(name, args):
            return [mock_text]

        with patch("blend_ai.server.mcp") as mock_mcp:
            mock_mcp.call_tool = _fake_call_tool
            session = BlenderChatSession()
            result = session.execute_tool("create_object", {"type": "CUBE"})
            parsed = json.loads(result)
            assert parsed["name"] == "Cube"

    def test_execute_tool_error(self, mock_ollama_client, mock_blender_connection):
        """Test tool execution handles errors gracefully."""
        async def _failing_call_tool(name, args):
            raise RuntimeError("Blender error: not found")

        with patch("blend_ai.server.mcp") as mock_mcp:
            mock_mcp.call_tool = _failing_call_tool
            session = BlenderChatSession()
            result = session.execute_tool("create_object", {"type": "CUBE"})
            parsed = json.loads(result)
            assert parsed["status"] == "error"

    def test_chat_simple_response(
        self, mock_ollama_client, mock_blender_connection, mock_mcp_tools
    ):
        """Test chat with no tool calls — just a text response."""
        mock_response = MagicMock()
        mock_response.message.tool_calls = None
        mock_response.message.content = "I'll help you with Blender!"
        mock_ollama_client.chat.return_value = mock_response

        with patch("blend_ai.connection.BlenderConnection", return_value=mock_blender_connection):
            session = BlenderChatSession()
            session.initialize()
            result = session.chat("Hello")

        assert result == "I'll help you with Blender!"

    def test_chat_with_native_tool_call(
        self, mock_ollama_client, mock_blender_connection, mock_mcp_tools
    ):
        """Test chat with native Ollama tool call."""
        tool_response = MagicMock()
        tool_call = MagicMock()
        tool_call.function.name = "create_object"
        tool_call.function.arguments = {"type": "CUBE"}
        tool_response.message.tool_calls = [tool_call]
        tool_response.message.content = ""

        final_response = MagicMock()
        final_response.message.tool_calls = None
        final_response.message.content = "Created a cube!"

        mock_ollama_client.chat.side_effect = [tool_response, final_response]

        with patch("blend_ai.connection.BlenderConnection", return_value=mock_blender_connection):
            with patch.object(BlenderChatSession, "execute_tool", return_value='{"name": "Cube"}'):
                session = BlenderChatSession()
                session.initialize()
                result = session.chat("Create a cube")

        assert result == "Created a cube!"

    def test_chat_with_text_tool_call_fallback(
        self, mock_ollama_client, mock_blender_connection, mock_mcp_tools
    ):
        """Test chat when model outputs tool calls as XML text."""
        text_response = MagicMock()
        text_response.message.tool_calls = None
        text_response.message.content = (
            '<function=create_object><parameter=type>CUBE</parameter></function>\n'
            '</tool_call>'
        )

        final_response = MagicMock()
        final_response.message.tool_calls = None
        final_response.message.content = "Done! Created a cube."

        mock_ollama_client.chat.side_effect = [text_response, final_response]

        with patch("blend_ai.connection.BlenderConnection", return_value=mock_blender_connection):
            with patch.object(BlenderChatSession, "execute_tool", return_value='{"name": "Cube"}'):
                session = BlenderChatSession()
                session.initialize()
                result = session.chat("Make a cube")

        assert result == "Done! Created a cube."

    def test_chat_screenshot_triggers_vision(
        self, mock_ollama_client, mock_blender_connection, mock_mcp_tools
    ):
        """Test that screenshot tool calls auto-trigger vision analysis."""
        screenshot_result = json.dumps({"image": "base64encodeddata", "width": 1000, "height": 562})

        tool_response = MagicMock()
        tool_call = MagicMock()
        tool_call.function.name = "get_viewport_screenshot"
        tool_call.function.arguments = {}
        tool_response.message.tool_calls = [tool_call]
        tool_response.message.content = ""

        final_response = MagicMock()
        final_response.message.tool_calls = None
        final_response.message.content = "The viewport shows a default cube."

        mock_ollama_client.chat.side_effect = [tool_response, final_response]

        with patch("blend_ai.connection.BlenderConnection", return_value=mock_blender_connection):
            with patch.object(
                BlenderChatSession, "execute_tool", return_value=screenshot_result
            ):
                with patch.object(
                    BlenderChatSession, "analyze_screenshot", return_value="I see a default cube."
                ):
                    session = BlenderChatSession()
                    session.initialize()
                    result = session.chat("Take a screenshot")

        assert result == "The viewport shows a default cube."

    def test_analyze_screenshot(self, mock_ollama_client):
        """Test vision model analysis of screenshot."""
        mock_response = MagicMock()
        mock_response.message.content = "A 3D scene with a cube and a light."
        mock_ollama_client.chat.return_value = mock_response

        session = BlenderChatSession()
        result = session.analyze_screenshot("base64data", "What objects are visible?")

        mock_ollama_client.chat.assert_called_once()
        call_kwargs = mock_ollama_client.chat.call_args
        assert call_kwargs.kwargs["model"] == DEFAULT_VISION_MODEL
        msg = call_kwargs.kwargs["messages"][0]
        assert msg["role"] == "user"
        assert "base64data" in msg["images"]
        assert result == "A 3D scene with a cube and a light."

    def test_close(self, mock_ollama_client, mock_blender_connection):
        with patch("blend_ai.server._connection", mock_blender_connection):
            session = BlenderChatSession()
            session.close()
            mock_blender_connection.disconnect.assert_called_once()

    def test_execute_tool_reuses_event_loop(self, mock_ollama_client, mock_blender_connection):
        """execute_tool must reuse a cached loop, not call asyncio.run per invocation."""
        mock_text = MagicMock()
        mock_text.text = '{"status": "ok"}'

        session = BlenderChatSession()

        with patch("blend_ai.server.mcp") as mock_mcp:
            # Make call_tool return a coroutine-compatible value via run_until_complete
            async def _fake_call_tool(name, args):
                return [mock_text]

            mock_mcp.call_tool = _fake_call_tool

            with patch("asyncio.run") as mock_asyncio_run:
                session.execute_tool("create_object", {"type": "CUBE"})
                session.execute_tool("create_object", {"type": "SPHERE"})
                mock_asyncio_run.assert_not_called()

        # The session should have cached a loop
        assert session._loop is not None

    def test_vision_note_merged_into_json_result(
        self, mock_ollama_client, mock_blender_connection, mock_mcp_tools
    ):
        """Vision analysis is merged as 'vision_analysis' key when result is valid JSON."""
        screenshot_result = json.dumps({"image": "base64data", "width": 800, "height": 600})
        analysis_text = "I see a grey cube on a white background."

        tool_response = MagicMock()
        tool_call = MagicMock()
        tool_call.function.name = "get_viewport_screenshot"
        tool_call.function.arguments = {}
        tool_response.message.tool_calls = [tool_call]
        tool_response.message.content = ""

        final_response = MagicMock()
        final_response.message.tool_calls = None
        final_response.message.content = "Done."

        mock_ollama_client.chat.side_effect = [tool_response, final_response]

        with patch("blend_ai.connection.BlenderConnection", return_value=mock_blender_connection):
            with patch.object(BlenderChatSession, "execute_tool", return_value=screenshot_result):
                with patch.object(
                    BlenderChatSession, "analyze_screenshot", return_value=analysis_text
                ):
                    session = BlenderChatSession()
                    session.initialize()
                    session.chat("Take a screenshot")

        tool_msg = next(m for m in session.messages if m["role"] == "tool")
        parsed = json.loads(tool_msg["content"])
        assert "vision_analysis" in parsed
        assert parsed["vision_analysis"] == analysis_text

    def test_vision_note_concatenated_for_non_json_result(
        self, mock_ollama_client, mock_blender_connection, mock_mcp_tools
    ):
        """Vision note falls back to concatenation when result is not valid JSON."""
        analysis_text = "I see a grey cube."

        tool_response = MagicMock()
        tool_call = MagicMock()
        tool_call.function.name = "get_viewport_screenshot"
        tool_call.function.arguments = {}
        tool_response.message.tool_calls = [tool_call]
        tool_response.message.content = ""

        final_response = MagicMock()
        final_response.message.tool_calls = None
        final_response.message.content = "Done."

        mock_ollama_client.chat.side_effect = [tool_response, final_response]

        # Patch analyze_screenshot to return analysis even for non-JSON result
        # We also need parse to succeed at extracting image key — mock execute_tool
        # to return JSON with "image" so vision analysis is triggered, but then
        # pretend execute_tool returned plain text for the appended message.
        # Simplest approach: patch both execute_tool AND analyze_screenshot,
        # and configure execute_tool to return a JSON that triggers vision analysis
        # but where we intercept result processing.

        # Actually: execute_tool returns plain text, but vision analysis only triggers
        # when result JSON has "image" key. So we need execute_tool to return JSON with
        # "image" key, but also make json.dumps of result_obj fail (TypeError).
        # Easiest: return valid JSON with "image" key, mock analyze_screenshot,
        # then verify fallback path via monkeypatching json.loads on the second call.

        # Cleaner test: return a string that has "image" key detectable by json.loads
        # but then make json.dumps(result_obj) fail by patching json.loads to raise on second call.
        # Even cleaner: use a side_effect on json.loads.

        # Simplest valid approach: make execute_tool return plain text (no "image" key)
        # so vision is NOT triggered at all. Instead, test the branch directly on chat().
        # We need vision_note to be non-empty, which requires "image" key in result JSON.
        # So: return JSON with image key but arrange for result_obj update to raise TypeError.

        screenshot_json = json.dumps({"image": "data", "width": 100, "height": 100})

        with patch("blend_ai.connection.BlenderConnection", return_value=mock_blender_connection):
            with patch.object(
                BlenderChatSession, "execute_tool", return_value=screenshot_json
            ):
                with patch.object(
                    BlenderChatSession, "analyze_screenshot", return_value=analysis_text
                ):
                    # Patch json.loads inside ollama_chat to raise on the tool-content parse
                    original_loads = json.loads

                    call_count = [0]

                    def selective_loads(s, **kwargs):
                        call_count[0] += 1
                        # First call is for extracting "image" key — allow it
                        # Second call is for merging vision note — raise to test fallback
                        if call_count[0] == 2:
                            raise json.JSONDecodeError("forced", "", 0)
                        return original_loads(s, **kwargs)

                    with patch("blend_ai.ollama_chat.json.loads", side_effect=selective_loads):
                        session = BlenderChatSession()
                        session.initialize()
                        session.chat("Take a screenshot")

        tool_msg = next(m for m in session.messages if m["role"] == "tool")
        assert analysis_text in tool_msg["content"] or "[Vision Analysis]" in tool_msg["content"]


class TestParseTextToolCalls:
    def test_xml_style_no_params(self):
        text = '<function=get_scene_info></function>\n</tool_call>'
        result = _parse_text_tool_calls(text, {"get_scene_info"})
        assert len(result) == 1
        assert result[0]["name"] == "get_scene_info"
        assert result[0]["arguments"] == {}

    def test_xml_style_with_params(self):
        text = (
            '<function=create_object>'
            '<parameter=type>CUBE</parameter>'
            '<parameter=name>MyCube</parameter>'
            '</function>'
        )
        result = _parse_text_tool_calls(text, {"create_object"})
        assert len(result) == 1
        assert result[0]["name"] == "create_object"
        assert result[0]["arguments"]["type"] == "CUBE"
        assert result[0]["arguments"]["name"] == "MyCube"

    def test_xml_style_numeric_param(self):
        text = '<function=set_value><parameter=count>5</parameter></function>'
        result = _parse_text_tool_calls(text, {"set_value"})
        assert result[0]["arguments"]["count"] == 5

    def test_xml_style_list_param(self):
        text = '<function=move><parameter=location>[1, 2, 3]</parameter></function>'
        result = _parse_text_tool_calls(text, {"move"})
        assert result[0]["arguments"]["location"] == [1, 2, 3]

    def test_unknown_tool_still_parsed(self):
        """Unknown tools are parsed — validation happens in the chat loop."""
        text = '<function=unknown_tool><parameter=x>1</parameter></function>'
        result = _parse_text_tool_calls(text, {"create_object"})
        assert len(result) == 1
        assert result[0]["name"] == "unknown_tool"

    def test_json_style(self):
        text = '{"name": "create_object", "arguments": {"type": "SPHERE"}}'
        result = _parse_text_tool_calls(text, {"create_object"})
        assert len(result) == 1
        assert result[0]["name"] == "create_object"
        assert result[0]["arguments"]["type"] == "SPHERE"

    def test_no_tool_calls(self):
        text = "I'll help you create a 3D model!"
        result = _parse_text_tool_calls(text, {"create_object"})
        assert len(result) == 0

    def test_multiple_xml_calls(self):
        text = (
            '<function=create_object><parameter=type>CUBE</parameter></function>\n'
            '<function=create_object><parameter=type>SPHERE</parameter></function>'
        )
        result = _parse_text_tool_calls(text, {"create_object"})
        assert len(result) == 2

    def test_json_without_arguments_key_rejected(self):
        """JSON with only 'name' key must NOT be treated as a tool call."""
        text = '{"name": "Cube", "vertices": 8}'
        result = _parse_text_tool_calls(text, {"create_object"})
        assert result == []

    def test_json_with_name_and_arguments_accepted(self):
        """JSON with both 'name' and 'arguments' keys must be treated as a tool call."""
        text = '{"name": "create_object", "arguments": {"type": "SPHERE"}}'
        result = _parse_text_tool_calls(text, {"create_object"})
        assert len(result) == 1
        assert result[0]["name"] == "create_object"
        assert result[0]["arguments"]["type"] == "SPHERE"


class TestStripToolMarkup:
    def test_strips_xml_function(self):
        text = 'Hello <function=foo><parameter=x>1</parameter></function>\n</tool_call>'
        result = _strip_tool_markup(text)
        assert "<function" not in result
        assert "</tool_call>" not in result
        assert "Hello" in result

    def test_empty_after_strip(self):
        text = '<function=foo></function></tool_call>'
        result = _strip_tool_markup(text)
        assert result == ""

    def test_preserves_plain_text(self):
        text = "Just a normal response with no markup."
        result = _strip_tool_markup(text)
        assert result == text

    def test_strips_opening_tool_call_tag(self):
        """Both opening <tool_call> and closing </tool_call> tags must be removed."""
        text = '<tool_call>\n{"name": "foo"}\n</tool_call>'
        result = _strip_tool_markup(text)
        assert "<tool_call>" not in result
        assert "</tool_call>" not in result


class TestFindSimilarTools:
    def test_finds_similar(self):
        result = _find_similar_tools("delete_all_objects", {"delete_object", "create_object"})
        assert "delete_object" in result

    def test_no_match(self):
        result = _find_similar_tools("xyz_abc", {"create_object", "delete_object"})
        assert result == []

    def test_ranked_by_overlap(self):
        result = _find_similar_tools(
            "delete_all_objects",
            {"delete_object", "create_object", "list_objects"}
        )
        # "delete_object" shares "delete" + "object" = 2 words
        assert result[0] == "delete_object"

    def test_max_results(self):
        tools = {f"tool_{i}" for i in range(20)}
        result = _find_similar_tools("tool_5", tools, max_results=3)
        assert len(result) <= 3


class TestBuildToolList:
    def test_includes_all_tools(self):
        tools = [
            {"type": "function", "function": {"name": "create_object", "description": "Create a thing. More details."}},
            {"type": "function", "function": {"name": "delete_object", "description": "Delete a thing."}},
        ]
        result = _build_tool_list(tools)
        assert "- create_object: Create a thing" in result
        assert "- delete_object: Delete a thing" in result

    def test_sorted_alphabetically(self):
        tools = [
            {"type": "function", "function": {"name": "z_tool", "description": "Z."}},
            {"type": "function", "function": {"name": "a_tool", "description": "A."}},
        ]
        result = _build_tool_list(tools)
        assert result.index("a_tool") < result.index("z_tool")


class TestFormatArgs:
    def test_simple_args(self):
        result = _format_args({"type": "CUBE", "name": "MyCube"})
        assert "type='CUBE'" in result
        assert "name='MyCube'" in result

    def test_truncates_long_values(self):
        long_val = "a" * 100
        result = _format_args({"data": long_val})
        assert "..." in result
        assert len(result) < 100

    def test_empty_args(self):
        assert _format_args({}) == ""

    def test_numeric_args(self):
        result = _format_args({"x": 1.5, "y": 2})
        assert "x=1.5" in result
        assert "y=2" in result


class TestParseImageCommand:
    def test_path_and_message(self):
        result = parse_image_command("!image /path/to/img.png describe this")
        assert result == ("/path/to/img.png", "describe this")

    def test_path_only_no_message(self):
        result = parse_image_command("!image /path/to/img.jpg")
        assert result == ("/path/to/img.jpg", "")

    def test_no_path_returns_none(self):
        result = parse_image_command("!image")
        assert result is None

    def test_not_image_command_returns_none(self):
        result = parse_image_command("create a cube")
        assert result is None

    def test_multi_word_message(self):
        result = parse_image_command("!image /img.png make something like this in 3D")
        assert result == ("/img.png", "make something like this in 3D")

    def test_webp_extension(self):
        result = parse_image_command("!image /ref.webp")
        assert result == ("/ref.webp", "")


class TestLoadImageAsBase64:
    def test_valid_png_returns_base64(self, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        result = load_image_as_base64(str(img_file))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_valid_jpg_returns_base64(self, tmp_path):
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)
        result = load_image_as_base64(str(img_file))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_image_as_base64(str(tmp_path / "missing.png"))

    def test_unsupported_extension_raises(self, tmp_path):
        bad_file = tmp_path / "photo.bmp"
        bad_file.write_bytes(b"BM\x00")
        with pytest.raises(ValueError, match="Unsupported image format"):
            load_image_as_base64(str(bad_file))

    def test_txt_extension_raises(self, tmp_path):
        txt_file = tmp_path / "notes.txt"
        txt_file.write_bytes(b"hello")
        with pytest.raises(ValueError, match="Unsupported image format"):
            load_image_as_base64(str(txt_file))


class TestSupportedImageFormats:
    def test_contains_common_formats(self):
        assert ".png" in SUPPORTED_IMAGE_FORMATS
        assert ".jpg" in SUPPORTED_IMAGE_FORMATS
        assert ".jpeg" in SUPPORTED_IMAGE_FORMATS
        assert ".webp" in SUPPORTED_IMAGE_FORMATS
        assert ".gif" in SUPPORTED_IMAGE_FORMATS

    def test_excludes_bmp(self):
        assert ".bmp" not in SUPPORTED_IMAGE_FORMATS


class TestImageCommandRouting:
    def test_image_command_calls_analyze_screenshot_not_chat_images(
        self, mock_ollama_client, mock_blender_connection, mock_mcp_tools
    ):
        """!image should call analyze_screenshot (vision model) then chat() with text — not pass images to chat()."""
        vision_description = "A detailed humanoid figure with clear muscle definition."
        mock_response = MagicMock()
        mock_response.message.tool_calls = None
        mock_response.message.content = "I'll sculpt this!"
        mock_ollama_client.chat.return_value = mock_response

        with patch("blend_ai.connection.BlenderConnection", return_value=mock_blender_connection):
            session = BlenderChatSession()
            session.initialize()
            with patch("blend_ai.ollama_chat.load_image_as_base64", return_value="base64data"):
                with patch.object(session, "analyze_screenshot", return_value=vision_description) as mock_analyze:
                    session._handle_image_command("/ref.png", "build this")
                    mock_analyze.assert_called_once_with("base64data", context="build this")

    def test_image_command_prepends_vision_description_to_chat(
        self, mock_ollama_client, mock_blender_connection, mock_mcp_tools
    ):
        """chat() receives vision description prepended to user message, no images key."""
        vision_description = "A sphere with rough surface texture."
        mock_response = MagicMock()
        mock_response.message.tool_calls = None
        mock_response.message.content = "Got it!"
        mock_ollama_client.chat.return_value = mock_response

        with patch("blend_ai.connection.BlenderConnection", return_value=mock_blender_connection):
            session = BlenderChatSession()
            session.initialize()
            with patch("blend_ai.ollama_chat.load_image_as_base64", return_value="base64data"):
                with patch.object(session, "analyze_screenshot", return_value=vision_description):
                    session._handle_image_command("/ref.png", "make this")

        user_msg = next(m for m in session.messages if m["role"] == "user")
        assert vision_description in user_msg["content"]
        assert "make this" in user_msg["content"]
        assert "images" not in user_msg


class TestChatWithImages:
    def test_chat_includes_images_in_message(
        self, mock_ollama_client, mock_blender_connection, mock_mcp_tools
    ):
        """chat() with images adds 'images' key to user message dict."""
        mock_response = MagicMock()
        mock_response.message.tool_calls = None
        mock_response.message.content = "I see the reference image!"
        mock_ollama_client.chat.return_value = mock_response

        with patch("blend_ai.connection.BlenderConnection", return_value=mock_blender_connection):
            session = BlenderChatSession()
            session.initialize()
            session.chat("Build this", images=["base64imagedata"])

        user_msg = next(m for m in session.messages if m["role"] == "user")
        assert "images" in user_msg
        assert user_msg["images"] == ["base64imagedata"]

    def test_chat_without_images_no_images_key(
        self, mock_ollama_client, mock_blender_connection, mock_mcp_tools
    ):
        """chat() without images does not add 'images' key to user message."""
        mock_response = MagicMock()
        mock_response.message.tool_calls = None
        mock_response.message.content = "Sure!"
        mock_ollama_client.chat.return_value = mock_response

        with patch("blend_ai.connection.BlenderConnection", return_value=mock_blender_connection):
            session = BlenderChatSession()
            session.initialize()
            session.chat("Hello")

        user_msg = next(m for m in session.messages if m["role"] == "user")
        assert "images" not in user_msg


class TestToolSchemaConstraints:
    """Models trust the schema over the prose around it.

    A local model repeatedly sent scale=[0.3, 0.25] and was rejected, because
    the schema said only "array of number". The length requirement and the
    parameter descriptions both lived in the docstring, which reaches the
    model as one blob of text attached to the tool, not as structure on the
    parameter it constrains. Each rejection costs a full round trip.

    These build their own server stub rather than reading blend_ai.server.mcp,
    which other tests in this file replace with a MagicMock.
    """

    @staticmethod
    def _stub_server(tools):
        """A minimal stand-in for FastMCP.list_tools()."""
        class _Tool:
            def __init__(self, name, description, schema):
                self.name = name
                self.description = description
                self.inputSchema = schema

        class _Server:
            async def list_tools(self):
                return [_Tool(*t) for t in tools]

        return _Server()

    def _create_object_params(self):
        from blend_ai.tool_registry import get_ollama_tools
        description = (
            "Create a primitive object in the scene.\n"
            "\n"
            "Args:\n"
            "    type: Primitive type. One of: CUBE, SPHERE, UV_SPHERE, CYLINDER,\n"
            "          CONE, TORUS, PLANE, MONKEY, EMPTY.\n"
            "    name: Optional name for the object. Auto-generated if empty.\n"
            "    location: XYZ position as a 3-element list/tuple.\n"
            "    rotation: XYZ Euler rotation in radians as a 3-element list/tuple.\n"
            "    scale: XYZ scale as a 3-element list/tuple. Defaults to (1,1,1).\n"
            "\n"
            "Returns:\n"
            "    Dict with the created object's name.\n"
        )
        schema = {
            "properties": {
                "type": {"type": "string", "title": "Type"},
                "name": {"type": "string", "title": "Name", "default": ""},
                "location": {"type": "array", "title": "Location",
                             "default": [0, 0, 0], "items": {"type": "number"}},
                "rotation": {"type": "array", "title": "Rotation",
                             "default": [0, 0, 0], "items": {"type": "number"}},
                "scale": {"type": "array", "title": "Scale",
                          "default": [1, 1, 1], "items": {"type": "number"}},
            },
            "required": ["type"],
        }
        server = self._stub_server([("create_object", description, schema)])
        tools = get_ollama_tools(server)
        return tools[0]["function"]["parameters"]["properties"]

    def test_vector_parameters_declare_their_length(self):
        props = self._create_object_params()
        for axis_param in ("location", "rotation", "scale"):
            prop = props[axis_param]
            assert prop.get("minItems") == 3, f"{axis_param} does not require 3 items"
            assert prop.get("maxItems") == 3, f"{axis_param} does not cap at 3 items"

    def test_parameters_carry_their_descriptions(self):
        props = self._create_object_params()
        assert "description" in props["scale"], (
            "The docstring documents scale, but the schema does not."
        )
        assert "3" in props["scale"]["description"]

    def test_descriptions_survive_multi_line_docstring_entries(self):
        """create_object's 'type' description wraps onto a second line."""
        props = self._create_object_params()
        desc = props["type"].get("description", "")
        assert "CUBE" in desc and "CYLINDER" in desc, (
            "A wrapped Args entry lost its continuation lines."
        )

    def test_scalar_and_short_arrays_are_untouched(self):
        """Only arrays with a 3-number default describe an XYZ vector."""
        from blend_ai.tool_registry import get_ollama_tools
        description = (
            "Do a thing.\n\nArgs:\n"
            "    names: Objects to act on.\n"
            "    pair: Two numbers.\n"
            "    flags: Three booleans, not a vector.\n"
        )
        schema = {
            "properties": {
                "names": {"type": "array", "title": "Names", "default": []},
                "pair": {"type": "array", "title": "Pair", "default": [1, 2]},
                "flags": {"type": "array", "title": "Flags",
                          "default": [True, False, True]},
            },
            "required": [],
        }
        props = get_ollama_tools(
            self._stub_server([("thing", description, schema)])
        )[0]["function"]["parameters"]["properties"]
        for name in ("names", "pair", "flags"):
            assert "minItems" not in props[name], (
                f"{name} was constrained to 3 without an XYZ default"
            )

    def test_arg_parser_ignores_a_missing_args_section(self):
        from blend_ai.tool_registry import _parse_arg_docs
        assert _parse_arg_docs("Just a summary, no sections.") == {}

    def test_arg_parser_stops_at_returns(self):
        from blend_ai.tool_registry import _parse_arg_docs
        docs = _parse_arg_docs(
            "Summary.\n\nArgs:\n    a: First.\n\nReturns:\n    Something else.\n"
        )
        assert docs == {"a": "First."}
