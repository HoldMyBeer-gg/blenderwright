"""A name over Blender's 255-byte limit on a create call is shortened, not refused.

Once the vision critique mentioned cockpit windows and thermal tiles, a
local model began naming parts like Nose_Tip_Conic_Fuselage_Shock_Cone_
Leading_Edge_Shape and lost seventeen rounds to "exceeds maximum length of
63", which never said what to do. Blender's limit (63 then, 255 bytes in
5.x) is real; the fix is to apply it and hand back the name that was used.
"""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.validators import (
    MAX_OBJECT_NAME_LENGTH,
    ValidationError,
    validate_new_name,
    validate_object_name,
)

LONG = "Nose_Tip_Conic_Fuselage_Shock_Cone_Leading_Edge_Shape_Pointed_Front_Section_01" * 4


class TestNewName:
    def test_short_names_pass_through(self):
        assert validate_new_name("NoseCone01") == "NoseCone01"

    def test_long_names_are_cut_to_the_limit(self):
        out = validate_new_name(LONG)
        assert len(out) <= MAX_OBJECT_NAME_LENGTH
        assert LONG.startswith(out)

    def test_cut_does_not_end_on_a_separator(self):
        name = "A" * 254 + "_B"
        assert validate_new_name(name) == "A" * 254

    def test_a_name_that_fits_is_kept_exactly(self):
        assert validate_new_name("Panel_") == "Panel_"

    def test_still_rejects_bad_characters(self):
        with pytest.raises(ValidationError):
            validate_new_name("bad\nname")

    def test_still_rejects_empty(self):
        with pytest.raises(ValidationError):
            validate_new_name("")


class TestLookupName:
    def test_long_lookup_says_no_object_can_have_that_name(self):
        with pytest.raises(ValidationError) as exc:
            validate_object_name(LONG)
        message = str(exc.value)
        assert "255" in message
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


class TestNamesBlenderCanHold:
    """Blender 5.2 names hold any printable text up to 255 UTF-8 bytes. Names
    are only ever sent as values, so lookups accept whatever Blender stores:
    FBX and 3ds Max files bring 'Material #25' and 'mixamorig:Hips'."""

    @pytest.mark.parametrize("name", [
        "Material #25", "Wood (Oak)", "mixamorig:Hips", "Würfel", "立方体", "a/b; c",
    ])
    def test_real_names_are_accepted(self, name):
        assert validate_object_name(name) == name
        assert validate_new_name(name) == name

    def test_up_to_255_bytes(self):
        assert validate_object_name("A" * 255) == "A" * 255
        with pytest.raises(ValidationError, match="255"):
            validate_object_name("A" * 256)

    def test_limit_is_bytes_not_characters(self):
        assert validate_object_name("é" * 127) == "é" * 127
        with pytest.raises(ValidationError, match="255"):
            validate_object_name("é" * 128)

    def test_new_name_is_cut_on_a_character_boundary(self):
        out = validate_new_name("é" * 200)
        assert out == "é" * 127

    @pytest.mark.parametrize("name", ["bad\nname", "bad\x00name", "tab\there", "bell\x07"])
    def test_control_characters_are_refused(self, name):
        with pytest.raises(ValidationError, match="control character"):
            validate_object_name(name)
