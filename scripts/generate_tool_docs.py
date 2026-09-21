#!/usr/bin/env python3
"""Generate the public tool reference from the source tree.

The tool count in the README drifted by eleven before anyone noticed,
because it was maintained by hand. A page listing every tool would rot the
same way, so this reads the tools out of the AST instead: nothing here is
written twice.

Usage:
    python scripts/generate_tool_docs.py            # write docs/index.html
    python scripts/generate_tool_docs.py --check    # exit 1 if it is stale
"""

from __future__ import annotations

import argparse
import ast
import html
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "src" / "blend_ai" / "tools"
OUT_DIR = ROOT / "docs"
SITE_URL = "https://blend-ai.holdmybeer.gg/"
REPO_URL = "https://github.com/HoldMyBeer-gg/blend-ai"

# Module file name -> the heading it appears under.
MODULE_TITLES = {
    "animation": "Animation",
    "armature": "Armature & Rigging",
    "booltool": "Bool Tool",
    "camera": "Camera",
    "code_exec": "Code Execution",
    "collections": "Collections",
    "curves": "Curves",
    "file_ops": "File I/O",
    "geometry_nodes": "Geometry Nodes",
    "gpencil": "Grease Pencil",
    "lighting": "Lighting",
    "materials": "Materials & Shaders",
    "mesh_editing": "Mesh Editing",
    "mesh_quality": "Mesh Quality",
    "modeling": "Modeling",
    "objects": "Objects",
    "physics": "Physics",
    "rendering": "Rendering",
    "scene": "Scene",
    "screenshot": "Viewport Capture",
    "sculpting": "Sculpting",
    "transforms": "Transforms",
    "uv": "UV Mapping",
    "viewport": "Viewport",
}


class Tool:
    """One @mcp.tool() function, as documented in the source."""

    def __init__(self, module: str, node: ast.FunctionDef) -> None:
        self.module = module
        self.name = node.name
        self.params = _parameters(node)
        doc = ast.get_docstring(node) or ""
        self.summary, self.args, self.returns = _split_docstring(doc)

    @property
    def signature(self) -> str:
        return f"{self.name}({', '.join(p['render'] for p in self.params)})"


def _annotation(node: ast.AST | None) -> str:
    return ast.unparse(node) if node is not None else ""


def _parameters(node: ast.FunctionDef) -> list[dict[str, str]]:
    """Positional parameters with their annotations and defaults."""
    args = node.args.args
    defaults = node.args.defaults
    pad = [None] * (len(args) - len(defaults))
    out = []
    for arg, default in zip(args, pad + list(defaults)):
        annotation = _annotation(arg.annotation)
        rendered = arg.arg
        if annotation:
            rendered += f": {annotation}"
        if default is not None:
            rendered += f" = {ast.unparse(default)}"
        out.append({"name": arg.arg, "type": annotation, "render": rendered})
    return out


def _split_docstring(doc: str) -> tuple[str, list[tuple[str, str]], str]:
    """Split a Google-style docstring into summary, args and returns."""
    if not doc:
        return "", [], ""

    parts = re.split(r"\n\s*(Args|Returns):\s*\n", doc)
    summary = parts[0].strip()
    sections: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i]] = parts[i + 1]

    args: list[tuple[str, str]] = []
    if "Args" in sections:
        current: str | None = None
        buf: list[str] = []
        for line in sections["Args"].splitlines():
            if not line.strip():
                continue
            match = re.match(r"\s{4}(\w+):\s*(.*)", line)
            if match:
                if current:
                    args.append((current, " ".join(buf).strip()))
                current, buf = match.group(1), [match.group(2)]
            elif current:
                buf.append(line.strip())
        if current:
            args.append((current, " ".join(buf).strip()))

    returns = " ".join(sections.get("Returns", "").split()).strip()
    return summary, args, returns


def collect_tools() -> list[Tool]:
    tools: list[Tool] = []
    for path in sorted(TOOLS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                func = decorator.func if isinstance(decorator, ast.Call) else decorator
                if isinstance(func, ast.Attribute) and func.attr == "tool":
                    tools.append(Tool(path.stem, node))
                    break
    return tools


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def render(tools: list[Tool]) -> str:
    by_module: dict[str, list[Tool]] = {}
    for tool in tools:
        by_module.setdefault(tool.module, []).append(tool)
    for group in by_module.values():
        group.sort(key=lambda t: t.name)

    modules = sorted(by_module, key=lambda m: MODULE_TITLES.get(m, m).lower())
    count = len(tools)

    description = (
        f"Complete reference for all {count} tools in blend-ai, the MCP server "
        f"for Blender. Modeling, mesh editing, materials, shader nodes, lighting, "
        f"camera, animation, rendering, sculpting, UV mapping, physics, geometry "
        f"nodes and rigging, driven by Claude or any MCP client."
    )

    nav = "\n".join(
        f'<a href="#{m}">{_esc(MODULE_TITLES.get(m, m))} '
        f'<span class="n">{len(by_module[m])}</span></a>'
        for m in modules
    )

    sections = []
    for module in modules:
        title = MODULE_TITLES.get(module, module)
        cards = []
        for tool in by_module[module]:
            params = ""
            if tool.args:
                rows = "\n".join(
                    f"<tr><th>{_esc(name)}</th><td>{_esc(desc)}</td></tr>"
                    for name, desc in tool.args
                )
                params = f'<table class="args"><tbody>{rows}</tbody></table>'
            returns = (
                f'<p class="ret"><span>Returns</span> {_esc(tool.returns)}</p>'
                if tool.returns
                else ""
            )
            cards.append(
                f'<article class="tool" id="{_esc(tool.name)}" '
                f'data-search="{_esc((tool.name + " " + tool.summary).lower())}">'
                f'<h3><a href="#{_esc(tool.name)}">{_esc(tool.name)}</a></h3>'
                f'<pre class="sig"><code>{_esc(tool.signature)}</code></pre>'
                f"<p>{_esc(tool.summary)}</p>{params}{returns}</article>"
            )
        sections.append(
            f'<section class="module" id="{_esc(module)}" '
            f'data-module="{_esc(title.lower())}">'
            f'<h2>{_esc(title)} <span class="n">{len(by_module[module])}</span></h2>'
            f'{"".join(cards)}</section>'
        )

    return TEMPLATE.format(
        count=count,
        modules=len(modules),
        description=_esc(description),
        site=SITE_URL,
        repo=REPO_URL,
        nav=nav,
        sections="\n".join(sections),
    )


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>blend-ai tool reference: {count} Blender MCP tools</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{site}">
<meta property="og:title" content="blend-ai tool reference">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{site}">
<meta property="og:type" content="website">
<style>
:root {{
  --bg: #fbfaf8; --panel: #fff; --text: #1a1a1a; --muted: #5c5c5c;
  --line: #e4e0da; --accent: #b4551f; --code-bg: #f4f1ec;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #14151a; --panel: #1b1d24; --text: #e8e6e3; --muted: #9a978f;
    --line: #2b2e37; --accent: #e08a52; --code-bg: #22252e;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #14151a; --panel: #1b1d24; --text: #e8e6e3; --muted: #9a978f;
  --line: #2b2e37; --accent: #e08a52; --code-bg: #22252e;
}}
* {{ box-sizing: border-box; }}
html {{ overflow-x: hidden; }}
body {{
  margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}}
code, pre, .sig {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
.wrap {{ max-width: 1180px; margin: 0 auto; padding: 0 16px; }}
header {{ border-bottom: 1px solid var(--line); padding: 44px 0 28px; }}
h1 {{ margin: 0 0 8px; font-size: clamp(1.7rem, 4vw, 2.4rem); letter-spacing: -0.02em; }}
.tag {{ color: var(--muted); margin: 0 0 20px; max-width: 62ch; }}
.stats {{ display: flex; gap: 22px; flex-wrap: wrap; color: var(--muted); font-size: .9rem; }}
.stats b {{ color: var(--accent); font-size: 1.05rem; }}
.links a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
.links a:hover {{ text-decoration: underline; }}
#q {{
  width: 100%; margin: 24px 0 0; padding: 12px 14px; font-size: 1rem;
  background: var(--panel); color: var(--text);
  border: 1px solid var(--line); border-radius: 9px;
}}
#q:focus {{ outline: 2px solid var(--accent); outline-offset: 1px; }}
.layout {{ display: grid; grid-template-columns: 210px minmax(0, 1fr);
          gap: 34px; padding: 30px 0 70px; }}
main {{ min-width: 0; }}
nav {{ position: sticky; top: 16px; align-self: start; max-height: 92vh; overflow: auto; }}
nav a {{
  display: flex; justify-content: space-between; gap: 8px;
  padding: 5px 9px; border-radius: 6px; color: var(--muted);
  text-decoration: none; font-size: .87rem;
}}
nav a:hover {{ background: var(--code-bg); color: var(--text); }}
nav .n, h2 .n {{
  color: var(--muted); background: var(--code-bg);
  border-radius: 20px; padding: 0 7px; font-size: .75rem; font-weight: 600;
}}
h2 {{
  margin: 34px 0 14px; padding-bottom: 8px; font-size: 1.28rem;
  border-bottom: 1px solid var(--line); scroll-margin-top: 14px;
  display: flex; align-items: center; gap: 10px;
}}
.module:first-child h2 {{ margin-top: 0; }}
.tool {{
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 10px; padding: 15px 17px; margin-bottom: 12px;
  scroll-margin-top: 14px;
}}
.tool h3 {{ margin: 0 0 8px; font-size: 1rem; }}
.tool h3 a {{ color: var(--accent); text-decoration: none; }}
.tool h3 a:hover {{ text-decoration: underline; }}
.tool p {{ margin: 0 0 10px; }}
.sig {{
  margin: 0 0 10px; padding: 9px 11px; overflow-x: auto;
  background: var(--code-bg); border-radius: 7px;
  font-size: .82rem; color: var(--muted);
}}
.args {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
.args {{ table-layout: auto; }}
.args th {{
  width: 1%; text-align: left; vertical-align: top; white-space: nowrap;
  padding: 4px 18px 4px 0; color: var(--accent); font-weight: 600;
}}
.args td {{ overflow-wrap: anywhere; }}
.args td {{ padding: 4px 0; color: var(--muted); }}
.ret {{ margin: 10px 0 0 !important; font-size: .88rem; color: var(--muted); }}
.ret span {{ color: var(--accent); font-weight: 600; margin-right: 6px; }}
.hidden {{ display: none !important; }}
#empty {{ color: var(--muted); padding: 30px 0; }}
footer {{ border-top: 1px solid var(--line); padding: 22px 0 46px; color: var(--muted); font-size: .87rem; }}
footer a {{ color: var(--accent); }}
@media (max-width: 820px) {{
  .layout {{ grid-template-columns: 1fr; gap: 0; }}
  nav {{ position: static; max-height: none; display: flex; flex-wrap: wrap;
        gap: 4px; padding-bottom: 18px; }}
  nav a {{ border: 1px solid var(--line); }}
}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>blend-ai tool reference</h1>
  <p class="tag">Every tool the blend-ai MCP server exposes to Blender, generated
  directly from the source so it cannot drift out of date.</p>
  <div class="stats">
    <span><b>{count}</b> tools</span>
    <span><b>{modules}</b> modules</span>
    <span class="links"><a href="{repo}">GitHub</a></span>
    <span class="links"><a href="{repo}/releases/latest">Download</a></span>
  </div>
  <input id="q" type="search" placeholder="Filter tools, e.g. bevel, uv, keyframe"
         autocomplete="off" aria-label="Filter tools">
</header>
<div class="layout">
  <nav aria-label="Tool categories">{nav}</nav>
  <main>
    {sections}
    <p id="empty" class="hidden">No tools match that filter.</p>
  </main>
</div>
<footer>
  <p>Generated from the blend-ai source tree.
  <a href="{repo}">github.com/HoldMyBeer-gg/blend-ai</a></p>
</footer>
</div>
<script>
(function () {{
  var q = document.getElementById('q');
  var tools = Array.prototype.slice.call(document.querySelectorAll('.tool'));
  var modules = Array.prototype.slice.call(document.querySelectorAll('.module'));
  var empty = document.getElementById('empty');
  function apply() {{
    var term = q.value.trim().toLowerCase();
    var hits = 0;
    tools.forEach(function (el) {{
      var match = !term || el.dataset.search.indexOf(term) !== -1;
      el.classList.toggle('hidden', !match);
      if (match) hits++;
    }});
    modules.forEach(function (sec) {{
      var any = sec.querySelector('.tool:not(.hidden)');
      var self = !term || sec.dataset.module.indexOf(term) !== -1;
      if (self && !any) {{
        sec.querySelectorAll('.tool').forEach(function (t) {{
          t.classList.remove('hidden');
        }});
        hits++;
        any = true;
      }}
      sec.classList.toggle('hidden', !any);
    }});
    empty.classList.toggle('hidden', hits > 0);
  }}
  q.addEventListener('input', apply);
}})();
</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="Exit non-zero if the committed page is out of date.")
    args = parser.parse_args()

    tools = collect_tools()
    page = render(tools)
    target = OUT_DIR / "index.html"

    if args.check:
        if not target.exists():
            print(f"{target} is missing. Run: python {Path(__file__).name}")
            return 1
        if target.read_text(encoding="utf-8") != page:
            print(f"{target} is out of date. Run: python {Path(__file__).name}")
            return 1
        print(f"{target} is current ({len(tools)} tools).")
        return 0

    OUT_DIR.mkdir(exist_ok=True)
    target.write_text(page, encoding="utf-8")
    (OUT_DIR / "CNAME").write_text("blend-ai.holdmybeer.gg\n", encoding="utf-8")
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {target} ({len(tools)} tools, {os.path.getsize(target)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
