"""A name over 63 characters on a create call is shortened, not refused.

Once the vision critique mentioned cockpit windows and thermal tiles, a
local model began naming parts like Nose_Tip_Conic_Fuselage_Shock_Cone_
Leading_Edge_Shape and lost seventeen rounds to "exceeds maximum length of
63", which never said what to do. Blender's limit is real; the fix is to
apply it and hand back the name that was used.
"""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.validators import (
    MAX_OBJECT_NAME_LENGTH,
    ValidationError,
    validate_new_name,
    validate_object_name,
)

LONG = "Nose_Tip_Conic_Fuselage_Shock_Cone_Leading_Edge_Shape_Pointed_Front_Section_01"


class TestNewName:
    def test_short_names_pass_through(self):
        assert validate_new_name("NoseCone01") == "NoseCone01"

    def test_long_names_are_cut_to_the_limit(self):
        out = validate_new_name(LONG)
        assert len(out) <= MAX_OBJECT_NAME_LENGTH
        assert LONG.startswith(out)

    def test_cut_does_not_end_on_a_separator(self):
        name = "A" * 62 + "_B"
        assert validate_new_name(name) == "A" * 62

    def test_still_rejects_bad_characters(self):
        with pytest.raises(ValidationError):
            validate_new_name("bad/name")

    def test_still_rejects_empty(self):
        with pytest.raises(ValidationError):
            validate_new_name("")


class TestLookupName:
    def test_long_lookup_says_no_object_can_have_that_name(self):
        with pytest.raises(ValidationError) as exc:
            validate_object_name(LONG)
        message = str(exc.value)
        assert "63" in message
        assert "returned" in message


class TestCreateToolsUseIt:
    @pytest.mark.parametrize("module,tool,kwargs", [
        ("objects", "create_object", {"type": "CONE", "name": LONG}),
        ("camera", "create_camera", {"name": LONG}),
        ("materials", "create_material", {"name": LONG}),
        ("lighting", "create_light", {"type": "POINT", "name": LONG}),
    ])
    def test_the_name_sent_fits(self, module, tool, kwargs):
        import importlib
        mod = importlib.import_module(f"blenderwright.tools.{module}")
        with patch(f"blenderwright.tools.{module}.get_connection") as conn:
            conn.return_value.send_command.return_value = {"status": "ok", "result": {"name": "x"}}
            getattr(mod, tool)(**kwargs)
            sent = conn.return_value.send_command.call_args.args[1]["name"]
        assert len(sent) <= MAX_OBJECT_NAME_LENGTH
        assert LONG.startswith(sent)

    def test_no_create_tool_still_uses_the_lookup_validator_for_name(self):
        """Every tool whose `name` is the thing being made shortens it."""
        import ast
        import pathlib
        tools_dir = pathlib.Path(__file__).parent.parent / "src" / "blenderwright" / "tools"
        offenders = []
        for path in sorted(tools_dir.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "validate_object_name"
                        and node.args and isinstance(node.args[0], ast.Name)
                        and node.args[0].id == "name"):
                    offenders.append(f"{path.name}:{node.lineno}")
        assert not offenders, f"creation names validated as lookups: {offenders}"


class TestChatThinking:
    """Measured on qwen3:30b-a3b: with think unset, thought goes to Ollama's
    separate channel and the content is the answer; with think=False the
    same model thinks inline in the content, untagged, 1,100 characters for
    a one-line question. So the default leaves it to the model."""

    def _session(self, **kw):
        from blenderwright.ollama_chat import BlenderChatSession
        with patch("blenderwright.ollama_chat.OllamaClient", MagicMock()):
            s = BlenderChatSession(**kw)
        s.tools, s._tool_names, s.messages = [], set(), [{"role": "system", "content": ""}]
        reply = MagicMock()
        reply.message.tool_calls = None
        reply.message.content = "ok"
        reply.message.thinking = "long private thought"
        s.ollama_client.chat.return_value = reply
        return s

    def test_default_leaves_think_to_the_model(self):
        s = self._session()
        s.chat("hi")
        assert "think" not in s.ollama_client.chat.call_args.kwargs

    def test_think_on_when_asked(self):
        s = self._session(think=True)
        s.chat("hi")
        assert s.ollama_client.chat.call_args.kwargs["think"] is True

    def test_think_off_when_asked(self):
        s = self._session(think=False)
        s.chat("hi")
        assert s.ollama_client.chat.call_args.kwargs["think"] is False

    def test_thinking_channel_is_not_stored(self):
        s = self._session()
        s.chat("hi")
        assert all("thinking" not in m for m in s.messages)

    def test_empty_reply_from_length_cap_prints_a_hint(self, capsys):
        s = self._session()
        s.ollama_client.chat.return_value.message.content = ""
        s.ollama_client.chat.return_value.done_reason = "length"
        assert s.chat("hi") == ""
        assert "--no-think" in capsys.readouterr().out
