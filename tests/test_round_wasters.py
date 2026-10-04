"""Four errors that each cost a local model a round in one shuttle session.

Every string the server sends back is the manual a small model reads. These
four answered a reasonable call with a refusal that did not say what to do
instead, or refused something that should have been accepted.
"""

import math
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from blenderwright.validators import (
    ValidationError,
    validate_numeric_range,
    validate_output_path,
)


class TestAngleCapIncludesPi:
    """shade_auto_smooth(angle=math.pi) was refused: the cap was 3.14159."""

    def test_exact_pi_is_accepted_at_a_pi_cap(self):
        assert validate_numeric_range(math.pi, max_val=math.pi, name="angle") == math.pi

    def test_a_rounded_up_pi_is_accepted(self):
        # 3.1416 is what a model that rounds sends; it means pi.
        assert validate_numeric_range(3.1416, max_val=math.pi, name="angle") == math.pi

    def test_clearly_over_is_still_refused(self):
        with pytest.raises(ValidationError):
            validate_numeric_range(4.0, max_val=math.pi, name="angle")

    def test_degrees_hint_does_not_fire_for_a_near_miss(self):
        with pytest.raises(ValidationError) as exc:
            validate_numeric_range(3.5, max_val=math.pi, name="angle")
        assert "degrees" not in str(exc.value)

    def test_degrees_hint_still_fires_for_a_degree_value(self):
        with pytest.raises(ValidationError) as exc:
            validate_numeric_range(90, max_val=math.pi, name="angle")
        assert "degrees" in str(exc.value)

    @pytest.mark.parametrize("module,symbol", [
        ("blenderwright.tools.objects", "shade_auto_smooth"),
        ("blenderwright.tools.lighting", "set_light_property"),
    ])
    def test_no_truncated_pi_left_in_tool_modules(self, module, symbol):
        import importlib
        import inspect
        src = inspect.getsource(importlib.import_module(module))
        assert "3.14159" not in src, f"{module} still caps an angle at a truncated pi"


class TestOutputPathNamesAWritableDirectory:
    """render_image('/home/user/x.png') on a Mac got Blender's raw 'cannot save'."""

    def test_missing_directory_is_refused_with_a_real_alternative(self):
        with pytest.raises(ValidationError) as exc:
            validate_output_path("/home/nobody-here/shuttle.png", allowed_extensions={".png"})
        message = str(exc.value)
        assert "nobody-here" in message
        assert "does not exist" in message
        assert tempfile.gettempdir() in message
        assert message.rstrip().endswith("shuttle.png")

    def test_existing_directory_passes(self, tmp_path):
        target = str(tmp_path / "out.png")
        assert validate_output_path(target, allowed_extensions={".png"}) == str(tmp_path / "out.png")

    def test_a_directory_as_the_file_is_refused(self, tmp_path):
        with pytest.raises(ValidationError, match="directory"):
            validate_output_path(str(tmp_path), allowed_extensions=None)

    def test_extension_check_still_applies(self, tmp_path):
        with pytest.raises(ValidationError, match="extension"):
            validate_output_path(str(tmp_path / "out.txt"), allowed_extensions={".png"})

    @pytest.mark.parametrize("tool,module,kwargs", [
        ("render_image", "blenderwright.tools.rendering", {"filepath": "/home/nobody-here/r.png"}),
        ("render_animation", "blenderwright.tools.rendering", {"filepath": "/home/nobody-here/frame_"}),
        ("capture_viewport", "blenderwright.tools.camera", {"filepath": "/home/nobody-here/v.png"}),
        ("render_video", "blenderwright.tools.sequencer", {"filepath": "/home/nobody-here/v.mp4"}),
    ])
    def test_output_tools_use_it(self, tool, module, kwargs):
        import importlib
        mod = importlib.import_module(module)
        with patch(f"{module}.get_connection") as conn:
            with pytest.raises(ValidationError, match="does not exist"):
                getattr(mod, tool)(**kwargs)
            conn.return_value.send_command.assert_not_called()


class TestUnknownParameterErrorListsTheRealOnes:
    """get_viewport_screenshot(filepath=...) twice: pydantic said 'extra inputs
    are not permitted' and a URL, and never said what the parameters were."""

    @pytest.fixture
    def session(self):
        from blenderwright.ollama_chat import BlenderChatSession
        from blenderwright.tool_registry import get_ollama_tools
        from blenderwright.server import mcp
        with patch("blenderwright.ollama_chat.OllamaClient", MagicMock()):
            s = BlenderChatSession()
        s.tools = get_ollama_tools(mcp)
        s._tool_names = {t["function"]["name"] for t in s.tools}
        return s

    def test_rewritten_error_names_the_parameters(self, session):
        import json
        out = json.loads(session.execute_tool("get_viewport_screenshot",
                                              {"filepath": "/x.png", "max_size": 800}))
        assert out["status"] == "error"
        assert "filepath" in out["result"]
        assert "max_size" in out["result"] and "mode" in out["result"]
        assert "errors.pydantic.dev" not in out["result"]

    def test_two_unknowns_are_both_named(self, session):
        import json
        with patch("blenderwright.tools.objects.get_connection"):
            out = json.loads(session.execute_tool(
                "create_object", {"type": "CYLINDER", "diameter": 9, "length": 15}))
        assert "diameter" in out["result"] and "length" in out["result"]
        assert "scale" in out["result"]


class TestVisionVerdictIsVisible:
    """Three screenshots were analysed and nobody at the terminal saw a word."""

    def test_an_excerpt_is_printed(self, capsys):
        import json
        from blenderwright.ollama_chat import BlenderChatSession
        with patch("blenderwright.ollama_chat.OllamaClient", MagicMock()):
            s = BlenderChatSession()
        shot = json.dumps({"base64": "abc", "width": 10, "height": 10})
        with patch.object(s, "analyze_screenshot", return_value="A grey cone on a sphere, no wings yet."):
            s._describe_screenshot(shot)
        out = capsys.readouterr().out
        assert "[vision]" in out
        assert "grey cone" in out


class TestFramePrefixMayBeADirectory:
    def test_render_animation_accepts_an_existing_directory(self, tmp_path):
        from blenderwright.tools import rendering
        with patch("blenderwright.tools.rendering.get_connection") as conn:
            conn.return_value.send_command.return_value = {"status": "ok", "result": {}}
            rendering.render_animation(filepath=str(tmp_path) + os.sep)
            sent = conn.return_value.send_command.call_args.args[1]
        assert sent["filepath"].startswith(str(tmp_path))
