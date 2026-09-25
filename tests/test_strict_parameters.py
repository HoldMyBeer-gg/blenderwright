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


class TestRequiredVectorsDeclareTheirLength:
    """The minItems fix inferred length from a 3-number default.

    set_location, set_rotation and set_scale take their vector as a required
    parameter with no default, so the inference never fired on the three
    most-called tools in the server. A model still had nothing telling it how
    many components to send, which is the mistake that started all of this
    (scale=[0.3, 0.25]).

    These exercise the alias and the registry directly. Asserting against the
    live server is unreliable here: tests/test_tools/conftest.py installs a
    fake blend_ai.server into sys.modules at collection and never removes it,
    so what the global holds depends on import order.
    """

    def test_the_vector_alias_constrains_length(self):
        from pydantic import BaseModel, ValidationError
        from blend_ai.tools.transforms import Vector3

        class M(BaseModel):
            v: Vector3

        assert list(M(v=[1.0, 2.0, 3.0]).v) == [1.0, 2.0, 3.0]
        with pytest.raises(ValidationError):
            M(v=[0.3, 0.25])
        with pytest.raises(ValidationError):
            M(v=[1.0, 2.0, 3.0, 4.0])

    def test_the_alias_publishes_its_length_in_the_schema(self):
        from pydantic import BaseModel
        from blend_ai.tools.transforms import Vector3

        class M(BaseModel):
            v: Vector3

        prop = M.model_json_schema()["properties"]["v"]
        assert prop["minItems"] == 3 and prop["maxItems"] == 3

    def test_the_three_transform_tools_use_the_alias(self):
        """Source-level check, immune to how the server module is loaded."""
        import inspect
        from blend_ai.tools import transforms
        for name, param in (("set_location", "location"),
                            ("set_rotation", "rotation"),
                            ("set_scale", "scale")):
            annotation = inspect.signature(
                getattr(transforms, name)).parameters[param].annotation
            assert annotation is transforms.Vector3, (
                f"{name}.{param} is {annotation!r}, not the constrained alias"
            )

    def test_the_registry_passes_length_constraints_through(self):
        """Previously it only added minItems via the 3-number-default guess."""
        from blend_ai.tool_registry import get_ollama_tools

        class _Tool:
            name = "t"
            description = "Do it.\n\nArgs:\n    v: A vector.\n"
            inputSchema = {"properties": {"v": {
                "type": "array", "items": {"type": "number"},
                "minItems": 3, "maxItems": 3, "title": "V"}}, "required": ["v"]}

        class _Server:
            async def list_tools(self):
                return [_Tool()]

        prop = get_ollama_tools(_Server())[0]["function"]["parameters"]["properties"]["v"]
        assert prop["minItems"] == 3 and prop["maxItems"] == 3
