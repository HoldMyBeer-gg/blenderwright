"""Accepted values belong in the schema, not only in the enforcement.

27 parameters were validated against an ALLOWED_* set and documented with
nothing, or with two examples and an "e.g.". A model reading the schema had to
guess, and every wrong guess cost a round trip.

The pairing is read from the source rather than hand-written, so the constant
stays the single definition and the two cannot drift, which is exactly how the
README's tool count came to be wrong by eleven.
"""

import pytest
from mcp.server.fastmcp import FastMCP


ALLOWED_SHAPES = {"CUBE", "SPHERE", "CONE"}
ALLOWED_MODES = {"FAST", "SLOW"}


@pytest.fixture
def server():
    srv = FastMCP("test")
    return srv


def _schema(server, tool, param):
    model = server._tool_manager.get_tool(tool).fn_metadata.arg_model
    return model.model_json_schema()["properties"][param]


class TestEnumPairsReadsTheSource:
    """The pairing comes from the code, so the constant stays the one truth.

    These read a real tools module directly. Asserting against the live server
    is unreliable: tests/test_tools/conftest.py installs a fake
    blend_ai.server into sys.modules at collection and never removes it.
    """

    def test_a_validated_parameter_is_paired_with_its_constant(self):
        from blend_ai.enum_hints import _enum_pairs
        from blend_ai.tools import curves
        pairs = _enum_pairs(curves)
        assert pairs["create_curve"]["type"] == ["BEZIER", "NURBS", "PATH"]

    def test_values_are_sorted_for_a_stable_schema(self):
        from blend_ai.enum_hints import _enum_pairs
        from blend_ai.tools import physics
        for params in _enum_pairs(physics).values():
            for values in params.values():
                assert values == sorted(values)

    def test_a_parameter_checked_against_two_sets_is_skipped(self):
        """set_curve_property.value means different things per property, so a
        single enum would be a lie."""
        from blend_ai.enum_hints import _enum_pairs
        from blend_ai.tools import curves
        assert "value" not in _enum_pairs(curves).get("set_curve_property", {})

    def test_a_module_with_no_enums_yields_nothing(self):
        from blend_ai.enum_hints import _enum_pairs
        from blend_ai.tools import transforms
        pairs = _enum_pairs(transforms)
        assert isinstance(pairs, dict)

    def test_the_registry_forwards_enums_to_the_ollama_schema(self):
        from blend_ai.tool_registry import get_ollama_tools

        class _Tool:
            name = "t"
            description = "Do it.\n\nArgs:\n    mode: How.\n"
            inputSchema = {"properties": {"mode": {
                "type": "string", "enum": ["FAST", "SLOW"], "title": "Mode"}},
                "required": ["mode"]}

        class _Server:
            async def list_tools(self):
                return [_Tool()]

        prop = get_ollama_tools(_Server())[0]["function"]["parameters"]["properties"]["mode"]
        assert prop["enum"] == ["FAST", "SLOW"]
