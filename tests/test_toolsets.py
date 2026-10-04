"""Toolsets: load a subset of the tools, or let the model load them on demand.

All 191 tool schemas cost about 48k tokens on every request. Claude-class
clients absorb that; a 32k local model has nothing left for the conversation
and starts dropping messages. The default stays the full set, because that is
what the featured output was made with. Opting down is explicit, except in the
bundled Ollama client, where the window size is known and the maths decides.

Every toolset is one tool module, so the grouping cannot drift from the code.
"""

import asyncio

import pytest

from blenderwright.server import mcp
from blenderwright import toolsets
from blenderwright.toolsets import (
    CORE,
    META_TOOLS,
    TOOLSETS,
    ToolsetError,
    apply_toolsets,
    enable_toolset,
    parse_spec,
    restore_all,
    tools_by_toolset,
)

ALL_TOOL_NAMES = {t.name for t in asyncio.run(mcp.list_tools())}


@pytest.fixture(autouse=True)
def _restore():
    """Every test starts and ends with the full registry."""
    restore_all(mcp)
    yield
    restore_all(mcp)


def _names():
    return {t.name for t in asyncio.run(mcp.list_tools())}


class TestCatalogue:
    def test_every_toolset_is_a_real_module(self):
        grouped = tools_by_toolset(mcp)
        missing = set(TOOLSETS) - set(grouped)
        assert not missing, f"toolsets with no module behind them: {sorted(missing)}"

    def test_every_module_has_a_summary(self):
        grouped = tools_by_toolset(mcp)
        unsummarised = set(grouped) - set(TOOLSETS)
        assert not unsummarised, f"modules missing from TOOLSETS: {sorted(unsummarised)}"

    def test_every_tool_belongs_to_exactly_one_toolset(self):
        grouped = tools_by_toolset(mcp)
        seen = [name for names in grouped.values() for name in names]
        assert len(seen) == len(set(seen))
        assert set(seen) == ALL_TOOL_NAMES

    def test_core_is_a_subset_of_the_catalogue(self):
        assert CORE <= set(TOOLSETS)

    def test_core_keeps_the_quality_loop_in_sight(self):
        # A model only reaches for what it can see. These are the tools that
        # turn a pile of primitives into something worth featuring.
        for toolset in ("screenshot", "mesh_quality", "lighting", "camera", "rendering"):
            assert toolset in CORE

    def test_core_is_well_under_half_the_schema(self):
        grouped = tools_by_toolset(mcp)
        core_count = sum(len(grouped[t]) for t in CORE)
        assert core_count < len(ALL_TOOL_NAMES) // 2


class TestParseSpec:
    @pytest.mark.parametrize("value", [None, "", "  ", "all", "ALL"])
    def test_unset_or_all_means_everything(self, value):
        assert parse_spec(value) == ("all", frozenset())

    @pytest.mark.parametrize("value", ["auto", "Auto", " auto "])
    def test_auto(self, value):
        assert parse_spec(value) == ("auto", frozenset())

    def test_core_keyword_expands(self):
        mode, chosen = parse_spec("core")
        assert mode == "static"
        assert chosen == CORE

    def test_core_plus_extras(self):
        mode, chosen = parse_spec("core, physics ,animation")
        assert mode == "static"
        assert chosen == CORE | {"physics", "animation"}

    def test_explicit_list(self):
        mode, chosen = parse_spec("modeling,materials")
        assert mode == "static"
        assert chosen == {"modeling", "materials"}

    def test_unknown_name_is_an_error_that_lists_the_valid_ones(self):
        with pytest.raises(ToolsetError) as exc:
            parse_spec("modeling,sculpt")
        assert "sculpt" in str(exc.value)
        assert "sculpting" in str(exc.value)

    def test_auto_cannot_be_combined(self):
        with pytest.raises(ToolsetError):
            parse_spec("auto,physics")


class TestApply:
    def test_default_exposes_every_tool(self):
        # The guard that matters: unset means today's behaviour, exactly.
        applied = apply_toolsets(mcp, None)
        assert applied.mode == "all"
        assert _names() == ALL_TOOL_NAMES

    def test_static_list_leaves_only_those_modules(self):
        grouped = tools_by_toolset(mcp)
        applied = apply_toolsets(mcp, "modeling,materials")
        assert applied.mode == "static"
        assert applied.enabled == {"modeling", "materials"}
        assert _names() == set(grouped["modeling"]) | set(grouped["materials"])

    def test_static_list_has_no_meta_tools(self):
        apply_toolsets(mcp, "modeling")
        assert not (set(META_TOOLS) & _names())

    def test_auto_exposes_core_plus_meta_tools(self):
        grouped = tools_by_toolset(mcp)
        applied = apply_toolsets(mcp, "auto")
        assert applied.mode == "auto"
        assert applied.enabled == CORE
        expected = {n for t in CORE for n in grouped[t]} | set(META_TOOLS)
        assert _names() == expected

    def test_apply_twice_is_not_cumulative(self):
        apply_toolsets(mcp, "modeling")
        apply_toolsets(mcp, "materials")
        grouped = tools_by_toolset(mcp)
        assert _names() == set(grouped["materials"])

    def test_restore_brings_everything_back(self):
        apply_toolsets(mcp, "auto")
        restore_all(mcp)
        assert _names() == ALL_TOOL_NAMES

    def test_parked_tools_keep_their_hardened_schema(self):
        # strict.py made every argument model reject unknown fields. Parking
        # and restoring a tool must hand back the same object, not a rebuild.
        before = mcp._tool_manager._tools["bevel_edges"]
        apply_toolsets(mcp, "materials")
        restore_all(mcp)
        assert mcp._tool_manager._tools["bevel_edges"] is before


class TestEnable:
    def test_enable_adds_the_module(self):
        grouped = tools_by_toolset(mcp)
        apply_toolsets(mcp, "auto")
        added = enable_toolset(mcp, "physics")
        assert set(added) == set(grouped["physics"])
        assert set(grouped["physics"]) <= _names()

    def test_enable_is_idempotent(self):
        apply_toolsets(mcp, "auto")
        enable_toolset(mcp, "physics")
        assert enable_toolset(mcp, "physics") == []

    def test_enable_unknown_is_an_error(self):
        apply_toolsets(mcp, "auto")
        with pytest.raises(ToolsetError):
            enable_toolset(mcp, "sculpt")

    def test_enable_outside_auto_mode_still_works(self):
        apply_toolsets(mcp, "modeling")
        enable_toolset(mcp, "materials")
        assert "create_material" in _names()


def _text(result):
    """FastMCP returns (content, structured) for dict results; take the text."""
    content = result[0] if isinstance(result, tuple) else result
    return content[0].text


class TestMetaToolsOverMcp:
    def test_list_toolsets_reports_state(self):
        apply_toolsets(mcp, "auto")
        payload = _text(asyncio.run(mcp.call_tool("list_toolsets", {})))
        assert "physics" in payload
        assert "enabled" in payload

    def test_enable_toolset_tool_works_without_a_session(self):
        # The Ollama client calls tools through mcp.call_tool with no MCP
        # session, so the list_changed notification has nobody to go to.
        # That must be a quiet skip, not an error.
        apply_toolsets(mcp, "auto")
        payload = _text(asyncio.run(mcp.call_tool("enable_toolset", {"name": "sculpting"})))
        assert "enter_sculpt_mode" in payload
        assert "enter_sculpt_mode" in _names()

    def test_enable_toolset_tool_rejects_unknown(self):
        apply_toolsets(mcp, "auto")
        with pytest.raises(Exception) as exc:
            asyncio.run(mcp.call_tool("enable_toolset", {"name": "nope"}))
        assert "nope" in str(exc.value)


class TestServerEntryPoint:
    def test_env_var_is_read_by_main(self, monkeypatch):
        monkeypatch.setenv("BLENDERWRIGHT_TOOLSETS", "modeling")
        monkeypatch.setattr("sys.argv", ["blenderwright"])
        ran = {}
        monkeypatch.setattr(mcp, "run", lambda **kw: ran.update(kw))
        from blenderwright.server import main
        main()
        assert ran == {"transport": "stdio"}
        assert _names() == set(tools_by_toolset(mcp)["modeling"])

    def test_flag_beats_env_var(self, monkeypatch):
        monkeypatch.setenv("BLENDERWRIGHT_TOOLSETS", "modeling")
        monkeypatch.setattr("sys.argv", ["blenderwright", "--toolsets", "materials"])
        monkeypatch.setattr(mcp, "run", lambda **kw: None)
        from blenderwright.server import main
        main()
        assert _names() == set(tools_by_toolset(mcp)["materials"])

    def test_bad_spec_exits_with_the_valid_names(self, monkeypatch, capsys):
        monkeypatch.setenv("BLENDERWRIGHT_TOOLSETS", "sculpt")
        monkeypatch.setattr("sys.argv", ["blenderwright"])
        from blenderwright.server import main
        with pytest.raises(SystemExit):
            main()
        assert "sculpting" in capsys.readouterr().err


class TestModuleSurface:
    def test_meta_tool_names_are_stable(self):
        assert META_TOOLS == ("list_toolsets", "enable_toolset")

    def test_summaries_are_one_line(self):
        for name, summary in TOOLSETS.items():
            assert "\n" not in summary, name
            assert summary.strip() == summary, name

    def test_module_exports(self):
        for attr in ("CORE", "TOOLSETS", "apply_toolsets", "enable_toolset",
                     "restore_all", "parse_spec", "tools_by_toolset"):
            assert hasattr(toolsets, attr)
