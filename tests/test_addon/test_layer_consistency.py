"""Guard against the MCP tool layer and the addon handlers drifting apart.

Several constants are deliberately duplicated across the two layers. The
node-property allowlist is duplicated for security: the addon socket is
reachable by any local process, so the handler cannot trust the tool
layer's validation. The size caps are duplicated for the same reason.

Duplicated for a good reason is not the same as free to diverge. If the
tool layer accepts a value the handler rejects, the user gets a confusing
RuntimeError from deep inside Blender instead of a clean validation error.
If the handler allows something the tool layer never sends, the extra
surface is unreviewed. These tests pin the two together.
"""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_handler(name):
    """Load an addon handler module without triggering addon/__init__.py."""
    mock_dispatcher = MagicMock()
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher

    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "addon", "handlers", f"{name}.py"
    )
    spec = importlib.util.spec_from_file_location(f"addon.handlers.{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"addon.handlers.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tools():
    from blend_ai.tools import materials

    return materials


@pytest.fixture(scope="module")
def procedural():
    return _load_handler("procedural")


@pytest.fixture(scope="module")
def raster():
    return _load_handler("raster")


@pytest.fixture(scope="module")
def materials_handler():
    return _load_handler("materials")


# ---------------------------------------------------------------------------
# Pattern tables
# ---------------------------------------------------------------------------


class TestPatternTables:
    def test_procedural_patterns_match(self, tools, procedural):
        """Every advertised pattern must have a builder, and vice versa."""
        assert set(procedural.PATTERN_BUILDERS) == tools.PROCEDURAL_PATTERNS

    def test_every_pattern_has_a_palette(self, procedural):
        assert set(procedural.DEFAULT_PALETTES) == set(procedural.PATTERN_BUILDERS)

    def test_every_pattern_has_a_description(self, tools):
        assert set(tools.PROCEDURAL_PATTERN_DESCRIPTIONS) == tools.PROCEDURAL_PATTERNS

    def test_raster_patterns_match(self, tools, raster):
        assert set(raster.RASTER_PATTERNS) == tools.RASTER_PATTERNS

    def test_raster_and_procedural_patterns_are_disjoint(self, tools):
        """Anything a shader node can do belongs in the procedural path.

        Overlap would mean two ways to make the same thing, one of which
        needlessly bakes to pixels and loses resolution independence.
        """
        assert not (tools.RASTER_PATTERNS & tools.PROCEDURAL_PATTERNS)

    def test_param_usage_tables_reference_real_patterns(self, procedural):
        known = set(procedural.PATTERN_BUILDERS)
        assert procedural.PATTERNS_USING_DETAIL <= known
        assert procedural.PATTERNS_USING_DISTORTION <= known
        assert procedural.SCALE_INDEPENDENT_PATTERNS <= known


# ---------------------------------------------------------------------------
# Caps
# ---------------------------------------------------------------------------


class TestCaps:
    def test_raster_size_cap_matches(self, tools, raster):
        assert tools.MAX_RASTER_SIZE == raster.MAX_RASTER_SIZE

    def test_raster_count_cap_matches(self, tools, raster):
        assert tools.MAX_RASTER_COUNT == raster.MAX_RASTER_COUNT

    def test_raster_color_components_is_rgba(self, raster):
        """The canvas allocation scales with this, so it must stay 4."""
        assert raster.RASTER_COLOR_COMPONENTS == 4


# ---------------------------------------------------------------------------
# Allowlists
# ---------------------------------------------------------------------------


class TestAllowlists:
    def test_handler_allows_everything_the_tool_layer_sends(
        self, tools, materials_handler
    ):
        """A property the tool accepts but the handler rejects is a dead tool.

        The handler may allow more (it is the real boundary and may be
        stricter elsewhere), but it must never allow less, or the tool
        advertises a capability that always fails.
        """
        missing = tools.ALLOWED_SHADER_NODE_PROPERTIES - (
            materials_handler.ALLOWED_NODE_PROPERTIES
        )
        assert not missing, (
            f"Tool layer accepts properties the handler rejects: {sorted(missing)}"
        )

    def test_handler_does_not_allow_unreviewed_extras(
        self, tools, materials_handler
    ):
        """Surface the handler allows but no tool can reach is unreviewed."""
        extra = materials_handler.ALLOWED_NODE_PROPERTIES - (
            tools.ALLOWED_SHADER_NODE_PROPERTIES
        )
        assert not extra, (
            f"Handler allows properties no tool sends: {sorted(extra)}"
        )

    def test_ramp_interpolations_match(self, tools, materials_handler):
        assert (
            tools.ALLOWED_COLOR_RAMP_INTERPOLATIONS
            == materials_handler.ALLOWED_RAMP_INTERPOLATIONS
        )

    def test_ramp_color_modes_match(self, tools, materials_handler):
        assert (
            tools.ALLOWED_COLOR_RAMP_COLOR_MODES
            == materials_handler.ALLOWED_RAMP_COLOR_MODES
        )

    def test_no_dunder_properties_in_allowlist(self, materials_handler):
        """A dunder in the allowlist would be an arbitrary attribute write."""
        for prop in materials_handler.ALLOWED_NODE_PROPERTIES:
            assert not prop.startswith("__"), prop
            assert not prop.startswith("bl_"), prop
