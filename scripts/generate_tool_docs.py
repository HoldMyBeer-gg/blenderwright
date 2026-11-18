#!/usr/bin/env python3
"""Generate the public tool reference from the source tree.

The tool count in the README drifted by eleven before anyone noticed,
because it was maintained by hand. A page listing every tool would rot the
same way, so this reads the tools out of the AST instead: nothing here is
written twice.

Usage:
    python scripts/generate_tool_docs.py            # write docs/ (landing + tools/)
    python scripts/generate_tool_docs.py --check    # exit 1 if it is stale
"""

from __future__ import annotations

import argparse
import ast
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "src" / "blenderwright" / "tools"
OUT_DIR = ROOT / "docs"
SITE_URL = "https://blenderwright.holdmybeer.gg/"
TOOLS_URL = SITE_URL + "tools/"
REPO_URL = "https://github.com/HoldMyBeer-gg/blenderwright"

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
    "selection": "Selection",
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


def render_sitemap() -> str:
    """A sitemap for the landing page and the tool reference.

    No lastmod: it would change on every run and the staleness guard
    compares generated output byte for byte.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{SITE_URL}</loc><changefreq>weekly</changefreq>"
        "<priority>1.0</priority></url>\n"
        f"  <url><loc>{TOOLS_URL}</loc><changefreq>weekly</changefreq>"
        "<priority>0.8</priority></url>\n"
        "</urlset>\n"
    )


def render_robots() -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n"


def render(tools: list[Tool]) -> str:
    by_module: dict[str, list[Tool]] = {}
    for tool in tools:
        by_module.setdefault(tool.module, []).append(tool)
    for group in by_module.values():
        group.sort(key=lambda t: t.name)

    modules = sorted(by_module, key=lambda m: MODULE_TITLES.get(m, m).lower())
    count = len(tools)

    description = (
        f"Complete reference for all {count} tools in blenderwright, the MCP server "
        f"for Blender. Modeling, mesh editing, materials, shader nodes, lighting, "
        f"camera, animation, rendering, sculpting, UV mapping, physics, geometry "
        f"nodes and rigging, driven by Claude or any MCP client. Signed socket "
        f"(HMAC-SHA256, per-start token) and raw Python off by default."
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
        tools_url=TOOLS_URL,
        repo=REPO_URL,
        structured=count - 1,
        nav=nav,
        sections="\n".join(sections),
    )


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>blenderwright tool reference: {count} Blender MCP tools</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{tools_url}">
<meta name="robots" content="index, follow">
<meta property="og:title" content="blenderwright tool reference">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{tools_url}">
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
.security {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  padding: 14px 18px; margin: 20px 0; max-width: 72ch; font-size: .92rem; }}
.security h2 {{ font-size: 1rem; margin: 0 0 8px; }}
.security p {{ margin: 0 0 8px; color: var(--muted); }}
.security p:last-child {{ margin-bottom: 0; }}
.security b {{ color: var(--text); }}
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
  <h1>blenderwright tool reference</h1>
  <p class="tag">Every tool the blenderwright MCP server exposes to Blender, generated
  directly from the source so it cannot drift out of date.</p>
  <div class="stats">
    <span><b>{count}</b> tools</span>
    <span><b>{modules}</b> modules</span>
    <span class="links"><a href="{site}">Home</a></span>
    <span class="links"><a href="{repo}">GitHub</a></span>
    <span class="links"><a href="{repo}/releases/latest">Download</a></span>
  </div>
  <section id="security" class="security" aria-label="Security">
    <h2>Security</h2>
    <p><b>Signed socket.</b> The MCP server and Blender prove a shared token to each
    other with HMAC-SHA256, then sign and number every command and reply. The token
    is regenerated on every Start Server and never crosses the wire, so no other
    local program can drive your Blender or replay a command.</p>
    <p><b>Raw Python is off by default.</b> <code>execute_blender_code</code> refuses
    to run until you tick &quot;Allow raw Python&quot; in the N-panel. The switch
    lasts one Blender session and is never saved into a .blend. Every snippet is
    echoed to the console. The other {structured} tools never need it.</p>
    <p><b>Files never auto-run scripts.</b> Anything the model opens, imports or
    links loads with script auto-run off. <a href="{repo}#security">Full security
    model</a></p>
  </section>
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
  <p>Generated from the blenderwright source tree.
  <a href="{repo}">github.com/HoldMyBeer-gg/blenderwright</a></p>
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

def render_landing(tools: list[Tool]) -> str:
    """The front page: what blenderwright is, how to install it, how it is secured."""
    count = len(tools)
    modules = len({tool.module for tool in tools})
    description = (
        f"blenderwright is an open-source MCP server for Blender with {count} tools. "
        f"Claude, Cursor, Codex, Ollama or any MCP client models, textures, lights, "
        f"animates and renders in Blender 5.2 over a signed local socket, with raw "
        f"Python off by default."
    )
    return LANDING_TEMPLATE.format(
        count=count,
        modules=modules,
        description=_esc(description),
        site=SITE_URL,
        repo=REPO_URL,
    )


LANDING_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>blenderwright: MCP server for Blender</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{site}">
<meta name="robots" content="index, follow">
<meta property="og:title" content="blenderwright: MCP server for Blender">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{site}">
<meta property="og:type" content="website">
<meta property="og:image" content="{site}img/shuttle-launch.jpg">
<script type="application/ld+json">
{{"@context": "https://schema.org", "@type": "SoftwareApplication",
 "name": "blenderwright", "applicationCategory": "DeveloperApplication",
 "operatingSystem": "macOS, Windows, Linux", "license": "https://opensource.org/licenses/MIT",
 "url": "{site}", "codeRepository": "{repo}",
 "description": "{description}",
 "offers": {{"@type": "Offer", "price": "0", "priceCurrency": "USD"}}}}
</script>
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
body {{ margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
.wrap {{ max-width: 960px; margin: 0 auto; padding: 0 16px; }}
a {{ color: var(--accent); }}
header {{ padding: 56px 0 32px; }}
h1 {{ font-size: 2.4rem; line-height: 1.15; margin: 0 0 12px; }}
h2 {{ font-size: 1.5rem; margin: 0 0 14px; }}
h3 {{ font-size: 1.05rem; margin: 0 0 6px; }}
.lede {{ font-size: 1.15rem; color: var(--muted); max-width: 62ch; margin: 0 0 24px; }}
.cta {{ display: flex; gap: 12px; flex-wrap: wrap; }}
.btn {{ display: inline-block; padding: 10px 18px; border-radius: 6px; text-decoration: none;
  border: 1px solid var(--accent); font-weight: 600; }}
.btn.primary {{ background: var(--accent); color: #fff; }}
section {{ border-top: 1px solid var(--line); padding: 40px 0; }}
figure {{ margin: 0 0 24px; }}
video, img {{ display: block; width: 100%; height: auto; border-radius: 8px;
  border: 1px solid var(--line); }}
figcaption {{ color: var(--muted); font-size: .9rem; margin-top: 8px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }}
.card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  padding: 16px 18px; }}
.card p {{ margin: 0; color: var(--muted); font-size: .95rem; }}
code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .9em;
  background: var(--code-bg); border-radius: 4px; }}
code {{ padding: 1px 5px; }}
pre {{ padding: 12px 14px; overflow-x: auto; }}
ol {{ padding-left: 22px; }}
ol li {{ margin-bottom: 10px; }}
.table {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: .92rem; min-width: 620px; }}
th, td {{ text-align: left; vertical-align: top; padding: 10px 12px;
  border-bottom: 1px solid var(--line); }}
thead th {{ color: var(--muted); font-weight: 600; }}
.note {{ color: var(--muted); font-size: .85rem; }}
footer {{ border-top: 1px solid var(--line); padding: 28px 0 48px; color: var(--muted);
  font-size: .9rem; }}
@media (max-width: 600px) {{ h1 {{ font-size: 1.9rem; }} header {{ padding-top: 36px; }} }}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>blenderwright: an MCP server for Blender</h1>
  <p class="lede">Describe a scene to Claude, Cursor, Codex, Ollama or any MCP client and
  watch it get built in Blender. {count} tools across {modules} modules cover modeling,
  materials, lighting, animation, physics and rendering, with expert prompts that steer
  the model toward clean topology, real-world scale and good lighting.</p>
  <div class="cta">
    <a class="btn primary" href="#install">Install</a>
    <a class="btn" href="tools/">Browse all {count} tools</a>
    <a class="btn" href="{repo}">GitHub</a>
  </div>
</header>

<section id="demos" aria-label="Examples">
  <h2>Built from one sentence</h2>
  <figure>
    <video controls preload="none" poster="img/shuttle-launch.jpg" width="1600" height="1200">
      <source src="shuttle-launch.mp4" type="video/mp4">
    </video>
    <figcaption>A shuttle launch from two questions: "do you want to have a go at the space
    shuttle launch?" and "could you animate the launch?" Orbiter, tank, boosters, tower,
    emissive plumes and a metaball exhaust cloud, 60 Cycles frames from one
    <code>render_animation</code> call. Launch audio: NASA, STS-131.</figcaption>
  </figure>
  <div class="grid">
    <figure>
      <img src="img/saloon.jpg" alt="A two-storey Western saloon at dusk rendered in Blender"
           width="1600" height="898" loading="lazy">
      <figcaption>"Create a Western style 2-story saloon." About twenty minutes, no manual
      modelling.</figcaption>
    </figure>
    <figure>
      <img src="img/shader-preview.jpg" alt="Fifteen procedural material spheres and a node graph"
           width="1600" height="907" loading="lazy">
      <figcaption>Fifteen procedural materials, each node graph built and wired by a single
      <code>create_procedural_material</code> call.</figcaption>
    </figure>
  </div>
</section>

<section id="features" aria-label="Features">
  <h2>What it does</h2>
  <div class="grid">
    <div class="card"><h3>{count} structured tools</h3><p>Modeling, mesh editing, shader
    nodes, UVs, sculpting, rigging, geometry nodes, physics, compositing and rendering, each
    with validated inputs. <a href="tools/">Full reference</a>.</p></div>
    <div class="card"><h3>Visual feedback</h3><p>Fast viewport captures let the model look
    at its own work and fix what it sees before you do.</p></div>
    <div class="card"><h3>Mesh quality checks</h3><p>Reports non-manifold edges, loose and
    duplicate vertices and zero-area faces, plus 3D-print checks.</p></div>
    <div class="card"><h3>Any MCP client</h3><p>Claude Code, Claude Desktop, Cursor, Codex,
    Ollama and llama.cpp. Toolsets trim the schema for small local models.</p></div>
    <div class="card"><h3>Local and private</h3><p>No telemetry, no cloud. Everything stays
    on <code>127.0.0.1</code>. The Blender addon uses only the Python standard
    library.</p></div>
    <div class="card"><h3>Tested in real Blender</h3><p>Thousands of unit tests plus a live
    suite that runs every tool against Blender 5.2 LTS.</p></div>
  </div>
</section>

<section id="install" aria-label="Install">
  <h2>Install</h2>
  <ol>
    <li>Install <a href="https://docs.astral.sh/uv/">uv</a>. The MCP server then runs with
    <code>uvx blenderwright</code>, nothing else to install.</li>
    <li>Download the addon zip from <a href="{repo}/releases/latest">GitHub Releases</a>.
    In Blender 5.2 LTS open Edit &gt; Preferences &gt; Get Extensions, choose Install from
    Disk, and pick the zip.</li>
    <li>In the 3D Viewport press <code>N</code>, open the blenderwright tab and click
    Start Server.</li>
    <li>Connect your client. For Claude Code:
    <pre><code>claude mcp add blenderwright -- uvx blenderwright</code></pre>
    Other clients use the command <code>uvx</code> with the argument
    <code>blenderwright</code>. <a href="{repo}#quickstart">Setup for every
    client</a>.</li>
  </ol>
</section>

<section id="security" aria-label="Security">
  <h2>Security</h2>
  <div class="grid">
    <div class="card"><h3>Signed socket</h3><p>Any program on your machine can reach
    <code>127.0.0.1</code>, so the connection is authenticated. Start Server writes a fresh
    random token to a file only your user can read. Blender and the MCP server prove they
    know it with an HMAC-SHA256 challenge, then sign and number every command and reply.
    The token never crosses the wire, and commands cannot be injected, altered or
    replayed.</p></div>
    <div class="card"><h3>Raw Python is off by default</h3><p><code>execute_blender_code</code>
    refuses to run until you tick "Allow raw Python" in the N-panel. The switch lasts one
    Blender session and is never saved into a .blend. Every snippet is echoed to the
    console. A restricted namespace blocks 25 imports and 14 builtins to catch mistakes;
    it is not a sandbox.</p></div>
    <div class="card"><h3>Files never auto-run scripts</h3><p>Anything the model opens,
    imports, links or appends loads with script auto-run off for that session. Paths,
    names, numbers and enums are validated before they reach Blender, and only registered
    commands run.</p></div>
  </div>
  <p><a href="{repo}#security">Full security model</a></p>
</section>

<section id="compare" aria-label="Comparison">
  <h2>How it compares</h2>
  <p>All three servers talk to Blender over a TCP socket on <code>localhost:9876</code>.
  They differ in who may use that socket and what it will run.</p>
  <div class="table">
  <table>
    <thead><tr><th></th><th>blenderwright</th>
      <th><a href="https://projects.blender.org/lab/blender_mcp">Blender Lab lab/blender_mcp</a></th>
      <th><a href="https://github.com/ahujasid/mcp-for-blender">ahujasid/mcp-for-blender</a>
      (formerly blender-mcp)</th></tr></thead>
    <tbody>
      <tr><th>Socket authentication</th><td>HMAC-SHA256 handshake, every message signed and
      numbered</td><td>None</td><td>None (its README says so)</td></tr>
      <tr><th>Raw Python</th><td>Off until "Allow raw Python" is ticked, per session</td>
      <td>On, no switch</td><td>On by default. <code>BLENDER_MCP_SAFE_MODE=1</code> limits
      the MCP server, not the add-on socket</td></tr>
      <tr><th>Guard on raw Python</th><td>25 imports and 14 builtins removed (not a
      sandbox)</td><td><code>sys.exit</code> and 4 operators blocked (its docs: "isn't
      really a sandbox")</td><td>AST allowlist in safe mode only</td></tr>
    </tbody>
  </table>
  </div>
  <p class="note">Checked against each project's main branch on 2026-11-18. If a row is
  out of date, <a href="{repo}/issues">open an issue</a>.</p>
</section>

<footer>
  <p>blenderwright is open source under the MIT license.
  <a href="{repo}">GitHub</a> &middot; <a href="tools/">Tool reference</a> &middot;
  <a href="https://pypi.org/project/blenderwright/">PyPI</a></p>
</footer>
</div>
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
    outputs = {
        OUT_DIR / "index.html": render_landing(tools),
        OUT_DIR / "tools" / "index.html": render(tools),
        OUT_DIR / "sitemap.xml": render_sitemap(),
        OUT_DIR / "robots.txt": render_robots(),
    }

    if args.check:
        stale = [
            path for path, want in outputs.items()
            if not path.exists() or path.read_text(encoding="utf-8") != want
        ]
        if stale:
            names = ", ".join(str(p.relative_to(OUT_DIR)) for p in stale)
            print(f"out of date: {names}. Run: python {Path(__file__).name}")
            return 1
        print(f"docs/ is current ({len(tools)} tools).")
        return 0

    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (OUT_DIR / "CNAME").write_text("blenderwright.holdmybeer.gg\n", encoding="utf-8")
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote docs/index.html and docs/tools/index.html ({len(tools)} tools)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
