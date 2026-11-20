"""Plugins: tools from separately installed packages.

A package adds tools by declaring an entry point in the blenderwright.plugins
group. Loading the entry point imports its module, and the module's
@mcp.tool() decorators register the tools the same way a built-in module does.
Plugins load before the strict-parameter and enum-hint passes so their tools
get the same hardening, and a plugin can name its own toolset so auto and
core mode can still reach it.
"""

import ast
import os

import pytest

from blenderwright import plugins, toolsets
from blenderwright.toolsets import TOOLSETS, ToolsetError, parse_spec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _FakeEntryPoint:
    def __init__(self, name, load):
        self.name = name
        self._load = load

    def load(self):
        return self._load()


def _patch_entry_points(monkeypatch, eps):
    seen = {}

    def fake(*, group):
        seen["group"] = group
        return eps

    monkeypatch.setattr(plugins, "entry_points", fake)
    return seen


def test_load_plugins_imports_each_entry_point_in_the_group(monkeypatch):
    calls = []
    seen = _patch_entry_points(monkeypatch, [
        _FakeEntryPoint("one", lambda: calls.append("one")),
        _FakeEntryPoint("two", lambda: calls.append("two")),
    ])
    assert plugins.load_plugins() == ["one", "two"]
    assert calls == ["one", "two"]
    assert seen["group"] == "blenderwright.plugins"


def test_a_broken_plugin_is_reported_and_skipped(monkeypatch, capsys):
    def boom():
        raise ImportError("missing dependency")

    _patch_entry_points(monkeypatch, [
        _FakeEntryPoint("broken", boom),
        _FakeEntryPoint("fine", lambda: None),
    ])
    assert plugins.load_plugins() == ["fine"]
    err = capsys.readouterr().err
    assert "broken" in err
    assert "missing dependency" in err


def test_no_plugins_installed_loads_nothing(monkeypatch):
    _patch_entry_points(monkeypatch, [])
    assert plugins.load_plugins() == []


def test_register_toolset_makes_the_name_selectable(monkeypatch):
    monkeypatch.setattr(toolsets, "TOOLSETS", dict(TOOLSETS))
    toolsets.register_toolset("face_builder", "Build a rigged head from photos")
    assert parse_spec("face_builder") == ("static", frozenset({"face_builder"}))


def test_register_toolset_refuses_to_shadow_a_built_in(monkeypatch):
    monkeypatch.setattr(toolsets, "TOOLSETS", dict(TOOLSETS))
    with pytest.raises(ToolsetError):
        toolsets.register_toolset("materials", "not yours")


def test_server_loads_plugins_before_hardening_the_tools():
    with open(os.path.join(ROOT, "src", "blenderwright", "server.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    calls = [
        node.value.func.id
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
    ]
    assert "load_plugins" in calls
    assert calls.index("load_plugins") < calls.index("forbid_unknown_parameters")
    assert calls.index("load_plugins") < calls.index("attach_enum_hints")
