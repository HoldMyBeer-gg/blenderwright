"""Unknown tool parameters must be rejected, not silently dropped.

A model called create_principled_material(transmission_weight='0.1'). That is
not a parameter; the real one is `transmission`. Pydantic's default for extra
fields is "ignore", so the call succeeded, reported success, and changed
nothing. The model had no way to learn it was wrong, and a human hit the same
trap earlier the same day with `base_color` instead of `color`.

Silently discarding input is the worst failure mode available: it costs no
round trip, so nothing signals the mistake at all.
"""

import pytest
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from blend_ai.strict import forbid_unknown_parameters


@pytest.fixture
def strict_server():
    """A small server of our own, immune to what other tests mutate.

    The real server's argument models are module-level singletons shared
    across the suite, so asserting against them couples this file to whatever
    else has run.
    """
    server = FastMCP("test")

    @server.tool()
    def make_thing(name: str, color: list[float] = [1.0, 0.0, 0.0, 1.0],
                   roughness: float = 0.5,
                   scale: list[float] = [1.0, 1.0, 1.0]) -> dict:
        """Make a thing.

        Args:
            name: What to call it.
            color: RGBA colour.
            roughness: Surface roughness.
            scale: XYZ scale.
        """
        return {}

    forbid_unknown_parameters(server)
    return server


def _model(server, tool_name):
    return server._tool_manager.get_tool(tool_name).fn_metadata.arg_model


class TestUnknownParametersAreRejected:
    def test_misspelled_parameter_raises(self, strict_server):
        """transmission_weight when the parameter is transmission."""
        model = _model(strict_server, "make_thing")
        with pytest.raises(ValidationError) as exc:
            model.model_validate({"name": "M", "roughness_weight": 0.1})
        assert "roughness_weight" in str(exc.value)

    def test_the_human_version_of_the_same_mistake_raises(self, strict_server):
        """base_color instead of color, which silently did nothing."""
        model = _model(strict_server, "make_thing")
        with pytest.raises(ValidationError, match="extra_forbidden"):
            model.model_validate({"name": "M", "base_color": [1, 0, 0, 1]})

    def test_valid_parameters_still_work(self, strict_server):
        model = _model(strict_server, "make_thing")
        parsed = model.model_validate({"name": "M", "color": [1, 0, 0, 1],
                                       "roughness": 0.4})
        assert parsed.roughness == 0.4

    def test_defaults_are_untouched(self, strict_server):
        model = _model(strict_server, "make_thing")
        parsed = model.model_validate({"name": "M"})
        assert list(parsed.scale) == [1.0, 1.0, 1.0]

    def test_reports_how_many_it_hardened(self, strict_server):
        """Already-strict models are not counted twice."""
        assert forbid_unknown_parameters(strict_server) == 0

    def test_every_real_tool_forbids_extras(self):
        """The property that matters in production, checked on the real server."""
        import blend_ai.server as server
        lenient = [
            name for name, tool in server.mcp._tool_manager._tools.items()
            if tool.fn_metadata.arg_model.model_config.get("extra") != "forbid"
        ]
        assert not lenient, (
            f"{len(lenient)} tool(s) still ignore unknown parameters: "
            f"{sorted(lenient)[:5]}"
        )
