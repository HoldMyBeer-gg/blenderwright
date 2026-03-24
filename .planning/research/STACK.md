# Stack Research

**Domain:** Blender MCP Server (Python) — adding auto-screenshot feedback, extension suggestions, Blender 5.1 support, expert prompts, mesh quality improvements
**Researched:** 2026-03-23
**Confidence:** HIGH (core stack verified against live PyPI, official Blender developer docs, and official MCP SDK releases)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.13 | Runtime for MCP server layer | Blender 5.1 bundles Python 3.13 (VFX Platform 2026 alignment). The MCP server process runs in the host Python environment, not inside Blender, so matching 3.13 ensures no version friction when testing addon code against the `bpy` pip module. |
| `mcp` (official Python SDK) | `>=1.26.0,<2` | MCP server protocol implementation | Already in use. Pin `<2` because `main` branch is in pre-alpha v2 development with planned breaking changes. The project already imports `FastMCP` from `mcp.server.fastmcp` — this is the high-level interface baked into the official SDK, not the separate `fastmcp` package. Stick with the official SDK. |
| `pydantic` | `>=2.0` | Parameter validation, schema generation | Already in use. Pydantic v2's Rust core is 5-50x faster than v1 and FastMCP uses it internally for tool schema inference. Do not downgrade to v1. |
| Blender | 5.1 | Target 3D application | Released 2026-03-17. Python 3.13, new Raycast shader node, Geometry Nodes volume/string nodes, Grease Pencil fill-with-holes, EEVEE identifier is `BLENDER_EEVEE` (changed from `BLENDER_EEVEE_NEXT` in 5.0). Bone Info node in Geometry Nodes. |
| `bpy` (pip module) | `5.1.0` | Headless Blender for unit tests | PyPI package by the Blender Foundation — version 5.1.0 released 2026-03-17, requires Python ==3.13. Enables running addon handler tests without a running Blender instance in CI. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `Pillow` | `>=10.0` | Viewport screenshot post-processing | Use in the MCP server layer to resize/crop the raw PNG captured by `bpy.ops.screen.screenshot_area()` before base64-encoding for LLM consumption. Keeps tokens low without losing essential detail. Already exists on PyPI with Python 3.13 wheels. |
| `fake-bpy-module` | latest (2026-xx-xx build) | IDE type stubs for bpy | Dev-only. Install into the host Python environment for autocomplete and type checking when editing addon handlers. Does NOT need to be in `pyproject.toml` dependencies — add as a dev-only tool. The project auto-generates stubs from Blender 5.1 docs. |
| `RestrictedPython` | `>=7.4` (supports CPython 3.9-3.13) | Sandboxed code execution | Use to replace the current bare `exec()` in `code_exec.py`. RestrictedPython defines a restricted subset of Python — it is NOT a full sandbox but it eliminates the most dangerous escape vectors (filesystem access, `__import__`, `os` module). Note: CVE-2025-22153 fix is in >=7.3; use latest 7.x or 8.x. |
| `pytest` | `>=7.0` | Test runner | Already in dev deps. |
| `pytest-asyncio` | `>=0.21` | Async test support | Already in dev deps. FastMCP tools are async; handlers need async test wrappers. |
| `pytest-cov` | `>=4.0` | Coverage reporting | Already in dev deps. |
| `ruff` | `>=0.1.0` | Linting + formatting | Already in dev deps. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` | Dependency management and virtual envs | Already in use (`uv.lock` present). Faster than pip, lock-file driven. Use `uv run pytest` for running tests. |
| Blender (GUI) | Live addon development and manual testing | Install 5.1 from blender.org. The addon zip `blend-ai-v0.2.0.zip` installs via Preferences > Add-ons > Install. |
| MCP Inspector | Debug MCP tools interactively | Bundled with the MCP SDK. Run `mcp dev src/blend_ai/server.py` to launch the inspector — lets you invoke tools and inspect schemas without a full LLM client. |
| `bpy` (pip, Python 3.13 venv) | CI headless addon testing | Create a separate Python 3.13 venv, `pip install bpy==5.1.0`, then run addon handler tests against real bpy. Required for testing `addon/handlers/` since they import `bpy` directly. |

---

## Blender 5.1 API Changes That Affect This Codebase

These are breaking or notable changes verified against official Blender developer docs. Each item notes which module in the existing codebase is affected.

### Breaking Changes from Blender 5.0 (must fix for 5.1 support)

| Change | Old API | New API | Affected Module |
|--------|---------|---------|----------------|
| EEVEE render engine identifier | `BLENDER_EEVEE_NEXT` | `BLENDER_EEVEE` | `addon/handlers/rendering.py` |
| IDProperties dict access | `bpy.context.scene['cycles']` | Use property accessors directly | Any handler reading Cycles settings via dict syntax |
| Bundled modules privatized | `import rna_info`, `import keyingsets_utils`, etc. | Do not import these 13 modules | Verify none are imported in addon handlers |
| BGL API removed | `import bgl` | `gpu.texture.from_image()` | Any GPU/image drawing code |
| Image texture binding | `image.bindcode` | `gpu.texture.from_image(image)` | Screenshot capture handler if using GPU texture |
| Brush type enum suffix | `brush.sculpt_tool` | `brush.sculpt_brush_type` | `addon/handlers/sculpting.py` |
| Unified paint settings location | `scene.tool_settings.unified_paint_settings` | `scene.tool_settings.sculpt.unified_paint_settings` | `addon/handlers/sculpting.py` |
| Scene compositor node tree | `scene.node_tree` | `scene.compositing_node_group` | `addon/handlers/rendering.py` (if compositor tools exist) |
| File Output node base_path | `node.base_path` | `node.directory` + `node.file_name` | Any compositor File Output handler |
| Asset system types | `AssetHandle`, `AssetCatalogPath` | `AssetRepresentation` | Any asset handler |
| Scene `use_nodes` | `scene.use_nodes = True` | Always True; use `scene.compositing_node_group` | Compositor setup tools |
| Sky Texture node inputs | `sun_direction`, `turbidity`, `ground_albedo` | Removed entirely | Lighting/material handlers using Sky Texture |
| VSE context | `context.scene` (in VSE) | `context.sequencer_scene` | Any VSE handler |
| Radial symmetry location | `scene.tool_settings.sculpt.radial_symmetry` | `mesh.radial_symmetry` | `addon/handlers/sculpting.py` |

### New in Blender 5.1 (expose as new tools)

| Feature | Python API | Tool Category |
|---------|-----------|---------------|
| Raycast shader node (Cycles + EEVEE) | `bpy.ops.node.add_node(type='ShaderNodeRaycast')` | `addon/handlers/materials.py` |
| Geometry Nodes: Bone Info node | New node type in Geometry Nodes editor | `addon/handlers/geometry_nodes.py` |
| Geometry Nodes: Volume dilate/erode/clip nodes | New node types | `addon/handlers/geometry_nodes.py` |
| Node Tools now have registered operators | Each node tool has its own `bpy.ops` entry | Tooling reference update |
| `bpy.app.cachedir` | `bpy.app.cachedir` | Utility/diagnostics |
| `bpy.app.handler.exit_pre` | New app handler | Addon lifecycle management |
| `window.find_playing_scene()` | Animation state query | Animation tools |
| `mesh.validate()` now fixes multires tangents | Automatic, no API change needed | Mesh quality improvement |
| Node Tools global unique idname | Must set idname on all Node Tools | Any node tool registration code |
| `sculpt.sample_color` removed | Use `paint.sample_color` instead | `addon/handlers/sculpting.py` |
| VSE strip property renames (deprecated until 6.0) | `frame_final_duration` → `duration`, `frame_final_start` → `left_handle`, etc. | Any VSE handler |

### Blender Extensions API (for context-aware suggestions)

The Blender Extensions platform at `extensions.blender.org` exposes a REST API:

- **Listing endpoint**: `https://extensions.blender.org/api/v1/extensions/`
- **Response format**: JSON with `version`, `blocklist`, and `data` array
- **Extension fields**: `id`, `name`, `tagline`, `version`, `type`, `blender_version_min`, `tags`, `license`, `archive_url`, `archive_hash`, `archive_size`, `maintainer`, `website`
- **Install via Python**: `bpy.ops.extensions.package_install(repo_index=0, pkg_id="extension-id")`
- **Available since**: Blender 4.2

This API enables the context-aware extension suggestion feature: the MCP server can maintain a curated local mapping of task categories to extension IDs and surface suggestions before starting a complex task.

---

## Installation

```bash
# Core (already locked in uv.lock)
uv add "mcp>=1.26.0,<2"
uv add "pydantic>=2.0"

# New additions
uv add "Pillow>=10.0"
uv add --dev "RestrictedPython>=7.4"

# For addon handler testing (separate Python 3.13 venv)
python3.13 -m venv .venv-bpy
.venv-bpy/bin/pip install bpy==5.1.0
.venv-bpy/bin/pip install pytest pytest-cov

# IDE type stubs (not a project dep — install to host Python)
pip install fake-bpy-module-latest
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Official `mcp` SDK (`mcp>=1.26.0`) | `fastmcp` (standalone, v3.1.1 by PrefectHQ) | If you needed MCP client proxying, server chaining, or OpenAPI integration — features in standalone fastmcp that don't exist in the official SDK. Not needed here. The official SDK's FastMCP class covers all required cases. |
| `Pillow` for screenshot processing | OpenCV (`opencv-python`) | If you needed computer vision analysis of the viewport image (e.g., detecting object edges for auto-feedback). Overkill here; Pillow is sufficient for resize/encode. |
| `RestrictedPython` for code sandboxing | Full process isolation (subprocess + resource limits) | If security requirements escalated to "fully isolated execution." Subprocess isolation is stronger but adds latency and complexity. RestrictedPython is proportionate to the current risk surface. |
| `bpy==5.1.0` (pip) for headless testing | `pytest-blender` (runs tests inside Blender's Python) | Use `pytest-blender` if you need to test operators that require a full Blender context (e.g., UI operators). For handler unit tests that primarily call bpy data API, the pip `bpy` module is simpler and faster in CI. |
| `fake-bpy-module` for IDE stubs | `blender-stubs` (PyPI) | Either works. `fake-bpy-module` has more active maintenance and tracks Blender releases faster. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `mcp>=2` (v2 pre-alpha) | Main branch is labeled pre-alpha with breaking changes planned. v2 API is not stable. The project should pin `<2` until v2 reaches stable release. | `mcp>=1.26.0,<2` |
| Bare `exec()` in `code_exec.py` | Current implementation passes `__builtins__` directly to exec — allows full filesystem access, subprocess creation, network calls, and arbitrary imports. This is the critical security vulnerability documented in PROJECT.md. | `RestrictedPython` with an explicit allowlist of permitted globals |
| `import bgl` | Removed entirely in Blender 5.0. Will cause `ImportError` in Blender 5.1. | `gpu` module (`gpu.texture.from_image()`, `gpu.shader.*`) |
| `BLENDER_EEVEE_NEXT` as render engine identifier | Renamed to `BLENDER_EEVEE` in Blender 5.0. Will silently fall back to Cycles in 5.1 if not updated. | `'BLENDER_EEVEE'` |
| `scene.node_tree` for compositor | Removed in Blender 5.0. | `scene.compositing_node_group` |
| `UILayout.template_asset_view()` | Removed in Blender 5.0. | Asset shelf functionality |
| `brush.sculpt_tool` | Renamed to `brush.sculpt_brush_type` in Blender 5.0. | `brush.sculpt_brush_type` |
| `AssetHandle` / `AssetCatalogPath` | Removed in Blender 5.0. | `AssetRepresentation` |
| `bpy.ops.sculpt.sample_color` | Removed in Blender 5.1; merged into `paint.sample_color`. | `bpy.ops.paint.sample_color()` |
| Any of the 13 privatized bundled modules | Private since 5.0; not part of the public API. | Official public bpy modules only |

---

## Stack Patterns by Variant

**Screenshot feedback loop (auto-screenshot after tool calls):**
- Capture with `bpy.ops.screen.screenshot_area()` inside addon handler
- Write to temp file, read back, delete
- Resize with Pillow on MCP server side (not inside Blender) before base64-encoding
- Return as MCP image content type for LLM vision

**Context-aware extension suggestions:**
- Maintain a static curated JSON mapping: `{task_category: [{extension_id, reason, extensions_url}]}`
- Query `https://extensions.blender.org/api/v1/extensions/` at startup or on-demand to verify IDs still exist and get `blender_version_min`
- Surface suggestions as a dedicated MCP tool `suggest_extensions(task_description)` that returns a list of relevant extensions with install instructions
- Do NOT auto-install extensions without explicit user confirmation

**code_exec sandboxing with RestrictedPython:**
- Define an explicit safe globals dict with only `bpy`, `mathutils`, `math`, `Vector`, `Matrix`, and standard safe builtins
- Use `RestrictedPython.compile_restricted()` instead of `compile()`
- Use `RestrictedPython.safe_globals` as the base, extend with bpy allowlist
- Still captures stdout via `io.StringIO` buffer

**Blender 5.1 addon compatibility:**
- All handlers must be tested against `bpy==5.1.0` pip module in CI
- The addon `__init__.py` `bl_info` should declare `"blender": (5, 1, 0)`
- Node Tools need a `bl_idname` that is globally unique — enforce this in any tool registration that creates node tools

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `mcp>=1.26.0,<2` | Python 3.10-3.13 | Current project requires Python >=3.10; no change needed |
| `bpy==5.1.0` (pip, for testing) | Python ==3.13 exactly | Requires a dedicated Python 3.13 venv for CI tests — cannot mix with host Python if host is 3.11/3.12 |
| `RestrictedPython>=7.4` | CPython 3.9-3.13 | CVE-2025-22153 patched; use >=7.3 minimum, >=7.4 preferred |
| `Pillow>=10.0` | Python 3.8+ | Python 3.13 wheels available on PyPI |
| `fake-bpy-module-latest` | Python >=3.8 | Dev-only; install in host environment alongside IDE |
| Blender 5.1 addon | Blender 5.1.x | `bl_info` version tuple `(5, 1, 0)` — test for backward compat with 4.x is out of scope per PROJECT.md |

---

## Sources

- [Blender 5.1 Python API — developer.blender.org](https://developer.blender.org/docs/release_notes/5.1/python_api/) — Python 3.13 upgrade, removed operators, VSE renames, brush consolidation — HIGH confidence
- [Blender 5.0 Python API — developer.blender.org](https://developer.blender.org/docs/release_notes/5.0/python_api/) — EEVEE identifier, BGL removal, paint system restructure, asset system changes, compositor changes — HIGH confidence
- [MCP Python SDK PyPI — pypi.org/project/mcp](https://pypi.org/project/mcp/) — current version 1.26.0, Python >=3.10 — HIGH confidence
- [MCP Python SDK releases — github.com/modelcontextprotocol/python-sdk/releases](https://github.com/modelcontextprotocol/python-sdk/releases) — v2 pre-alpha status, pin `<2` rationale — HIGH confidence
- [bpy PyPI — pypi.org/project/bpy](https://pypi.org/project/bpy/) — 5.1.0 released 2026-03-17, requires Python 3.13 — HIGH confidence
- [Blender Extensions API Listing — developer.blender.org/docs/features/extensions/api_listing/](https://developer.blender.org/docs/features/extensions/api_listing/) — v1 endpoint URL, JSON schema, available since Blender 4.2 — HIGH confidence
- [RestrictedPython PyPI — pypi.org/project/RestrictedPython](https://pypi.org/project/RestrictedPython/) — CPython 3.9-3.13 support, CVE-2025-22153 — MEDIUM confidence (description of capabilities verified, exact API patterns not re-verified against source)
- [Blender 5.1 Release — blender.org/press/blender-5-1-release](https://www.blender.org/press/blender-5-1-release/) — feature list, Raycast node, Geometry Nodes additions — HIGH confidence
- [fake-bpy-module GitHub — github.com/nutti/fake-bpy-module](https://github.com/nutti/fake-bpy-module) — IDE stubs, active maintenance — MEDIUM confidence
- [FastMCP vs MCP SDK discussion — github.com/jlowin/fastmcp/discussions/2557](https://github.com/jlowin/fastmcp/discussions/2557) — relationship between official SDK FastMCP and standalone fastmcp — MEDIUM confidence

---

*Stack research for: Blender MCP Server — milestone additions (auto-screenshot, extension suggestions, Blender 5.1, expert prompts, mesh quality)*
*Researched: 2026-03-23*
