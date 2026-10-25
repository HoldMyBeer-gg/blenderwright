"""Every MCP tool, called for real against Blender 5.2 with sane arguments."""

import json
import os

import pytest

from blenderwright.server import mcp
from tests_live.cases import BASE_SETUP, CASES, NEEDS_GPU, NEEDS_VIEWPORT, SETUP

TOOLS = {tool.name: tool.fn for tool in mcp._tool_manager.list_tools()}
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
NO_GPU = bool(os.environ.get("BLENDERWRIGHT_NO_GPU"))


def _fill(value, paths):
    if isinstance(value, str):
        return value.format(**paths) if "{" in value else value
    if isinstance(value, list):
        return [_fill(v, paths) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, paths) for k, v in value.items()}
    return value


def test_every_tool_has_a_case():
    assert sorted(set(TOOLS) - set(CASES)) == [], "add a live case in tests_live/cases.py"
    assert sorted(set(CASES) - set(TOOLS)) == [], "case for a tool that no longer exists"


@pytest.mark.parametrize("name", sorted(CASES))
def test_tool_runs(scene, name):
    if name in NEEDS_VIEWPORT:
        pytest.xfail(NEEDS_VIEWPORT[name])
    if name in NEEDS_GPU and NO_GPU:
        pytest.skip(f"no GPU here: {NEEDS_GPU[name]}")
    paths = {"tmp": str(scene), "scene": str(scene / "scene.blend"), "asset": ASSETS}
    for tool, kwargs in BASE_SETUP + SETUP.get(name, []):
        TOOLS[tool](**_fill(kwargs, paths))
    result = TOOLS[name](**_fill(CASES[name], paths))
    json.dumps(result, default=str)  # the reply must serialise for the MCP client


@pytest.mark.skipif(NO_GPU, reason="no GPU here: EEVEE renders with OpenGL")
def test_eevee_render(scene):
    """The default engine renders a real image, not just a result dict."""
    from blenderwright.tools.rendering import render_image, set_render_engine, set_render_resolution

    set_render_resolution(width=32, height=32)
    set_render_engine(engine="BLENDER_EEVEE")
    out = scene / "eevee.png"
    render_image(filepath=str(out))
    assert out.exists() and out.stat().st_size > 0
