# Project Research Summary

**Project:** blend-ai — Blender MCP Server
**Domain:** AI-to-3D-application bridge (MCP server + Blender addon)
**Researched:** 2026-03-23
**Confidence:** HIGH

## Executive Summary

blend-ai is a two-process bridge: a FastMCP server (Python, outside Blender) communicates over a local TCP socket to a Blender addon that executes `bpy` API calls on Blender's main thread. The project already ships 161 tools at v0.2.0. This milestone adds five targeted improvements: Blender 5.1 API compatibility, an auto-screenshot feedback loop, mesh quality validation, expanded expert prompts, and context-aware extension suggestions. All five fit cleanly into the existing architecture without protocol changes.

The recommended approach is to treat Blender 5.1 compatibility as a hard prerequisite before any new feature work. Nine breaking API changes (EEVEE engine identifier, compositor node tree access, brush type property names, Grease Pencil type split, and others) affect existing handlers. Any new feature built on broken handler code will be impossible to test against the target Blender version. Once compatibility is established, the remaining features can be added in dependency order: prompts first (zero Blender-side risk), then the fast viewport screenshot handler, then extension suggestions (most new surface area).

The highest-severity risk is the existing `code_exec` handler, which passes real Python builtins to `exec()`, allowing full remote code execution from the MCP layer. This is a known vulnerability documented in PROJECT.md. A secondary risk is the screenshot tool's current use of `bpy.ops.render.render` (full path-traced render) instead of `bpy.ops.render.opengl` (fast viewport capture) — this would make the feedback loop unusable by triggering the render guard on every visual check. Both risks have clear mitigations documented in research.

## Key Findings

### Recommended Stack

The project is correctly built on the official MCP Python SDK (`mcp>=1.26.0,<2`), Pydantic v2, and Python 3.13 (required by Blender 5.1's bundled Python). Two additions are needed for this milestone: `Pillow>=10.0` for screenshot resize/encode on the MCP server side, and `RestrictedPython>=7.4` to replace the bare `exec()` in `code_exec.py`. The `bpy==5.1.0` pip module enables headless addon handler testing in CI without a running Blender instance, but requires a dedicated Python 3.13 virtual environment. The MCP SDK v2 is in pre-alpha with planned breaking changes — the `<2` pin is mandatory.

**Core technologies:**
- `Python 3.13`: Runtime — required by Blender 5.1's bundled Python; matches `bpy==5.1.0` pip module for CI testing
- `mcp>=1.26.0,<2`: MCP protocol — already in use; v2 pre-alpha must be excluded
- `pydantic>=2.0`: Validation — already in use; Rust core required by FastMCP internals
- `Pillow>=10.0`: Screenshot processing — resize/encode viewport images before LLM consumption; keeps token costs low
- `RestrictedPython>=7.4`: Code sandboxing — replaces bare `exec()`; CVE-2025-22153 patched in >=7.3
- `bpy==5.1.0` (pip, CI only): Headless testing — run handler unit tests without Blender GUI in CI

### Expected Features

Research confirms no competitor implements the auto-screenshot critique loop or comprehensive mesh quality validation. The closest competitor (poly-mcp) has ~51 tools vs. blend-ai's 161. blend-ai's differentiating angle is depth of Blender API coverage plus LLM workflow intelligence.

**Must have (table stakes) — this milestone:**
- Blender 5.1 API compatibility — users on 5.1 cannot use the server at all without this
- Auto-screenshot feedback loop — every comparable tool has it; the current manual-trigger implementation is insufficient
- Reliable, structured error messages — without them, the LLM loops on failed operations
- Mesh quality validation (`analyze_mesh_quality`) — the number one user complaint is models with non-manifold geometry

**Should have (competitive differentiators):**
- Expert topology and workflow prompts — no competitor does this; high ROI at low implementation cost
- Context-aware extension suggestions — proactively suggest Bool Tool, LoopTools, Node Wrangler, etc. before relevant tasks
- Blender 5.1 new nodes as tools (Raycast shader, Bone Info geometry node, Grid Dilate/Erode) — available only in 5.1+
- Workflow chaining tools elevated from prompts to callable tools with per-step error handling
- `code_exec` hardening — security must be addressed before further tool expansion

**Defer (v0.4+):**
- Granular vertex/edge/face selection by index — conflicts with MCP's stateless protocol; requires design work
- Undo grouping / MCP-level transactions — complex interaction with Blender's undo system; risk of data loss
- F-curve Gaussian smoothing as a standalone tool — niche use case
- Animation evaluation performance tools — deferred until character animation workflows are more common

### Architecture Approach

The three-tier architecture (AI client → MCP server over stdio → TCP socket → Blender addon main-thread queue) is sound and requires no structural changes for this milestone. All Blender 5.x compatibility fixes live entirely in `addon/handlers/` — the MCP server tier sends the same command names; handlers branch internally on `bpy.app.version`. The auto-screenshot feedback loop is prompt-driven, not server-driven, because MCP is stateless request/response and the server cannot push data unsolicited. The extension suggestion knowledge base lives entirely in the MCP server tier as a static Python dict, avoiding undocumented `bpy.ops.extensions` operators and network dependencies.

**Major components:**
1. `src/blend_ai/tools/` — MCP tool definitions; add `extension_suggestions.py` here
2. `src/blend_ai/prompts/` — expert prompt modules; split into `modeling.py`, `materials.py`, `lighting.py`, `feedback.py`
3. `addon/handlers/` — all bpy API calls; all version-gating logic; add `extensions.py`; fix 7 breaking API renames
4. `addon/handlers/camera.py` — add `capture_viewport_fast` using `bpy.ops.render.opengl` (not `render.render`)
5. `addon/render_guard.py` — add `force_clear()` method and `reset_render_guard` MCP tool; register with `persistent=True`

### Critical Pitfalls

1. **Screenshot uses `bpy.ops.render.render` (full render, blocking)** — replace with `bpy.ops.render.opengl` in viewport context; verify latency is under 500ms; do not set render guard during opengl capture. This must be fixed before the feedback loop ships or every visual check will deadlock workflows.

2. **`code_exec` passes real `__builtins__` to `exec()`** — full RCE: filesystem access, subprocess execution, network calls from inside Blender's Python. Restrict to an explicit allowlist (`bpy`, `mathutils`, `math`, safe builtins) using `RestrictedPython`. Add a user-facing "unsafe mode" toggle defaulting to OFF.

3. **Render guard stuck state not auto-cleared** — if Blender crashes or is force-quit mid-render, `threading.Event` stays set permanently; all subsequent commands return `busy`. Fix: add `force_clear()`, register a `load_post` handler, add `reset_render_guard` tool.

4. **Blender 5.x breaking API changes in 9 areas** — hard-coded `"BLENDER_EEVEE_NEXT"`, `scene.node_tree`, `brush.sculpt_tool`, `bpy.data.grease_pencils`, and 5 others will raise errors or silently misbehave. Apply version-gated shims using `bpy.app.version` in all affected handlers before any other work.

5. **Token runaway from unbounded screenshot calls** — prompting the LLM to "verify visually" without frequency constraints can produce 30-60 base64 PNG frames per session, exhausting context windows. The expert prompt must specify: screenshot only after structural changes (add/delete/boolean/apply), not after metadata-only changes. Cap feedback screenshot size at 800px.

## Implications for Roadmap

Based on the dependency graph from research, four phases are strongly indicated. The ordering is not preference — it is determined by what is broken and what blocks what.

### Phase 1: Blender 5.1 Compatibility
**Rationale:** Nine confirmed breaking API changes mean users on Blender 5.1 (released 2026-03-17) cannot reliably use the server. All subsequent development, testing, and feature work must happen on a working foundation. No new feature should be built until the existing 161 tools pass against `bpy==5.1.0`.
**Delivers:** All existing tools work correctly on Blender 5.1; `bl_info` declares `(5, 1, 0)`; CI runs against `bpy==5.1.0`.
**Addresses:** Table stakes — Blender 5.1 compatibility (P1 from FEATURES.md)
**Avoids:** Pitfall 3 (EEVEE identifier), Pitfall 4 (GreasePencil types), all version-specific breakage
**Key changes:**
- Fix `BLENDER_EEVEE_NEXT` → `BLENDER_EEVEE` in `rendering.py`
- Fix `scene.node_tree` → `scene.compositing_node_group` in `scene.py`
- Fix `brush.sculpt_tool` → `brush.sculpt_brush_type` in `sculpting.py`
- Fix `sculpt.sample_color` → `paint.sample_color`
- Fix `scene.eevee.gtao_distance` → `view_layer.eevee.ambient_occlusion_distance`
- Full audit and fix of `gpencil.py` handler against the Grease Pencil v3 / Annotation split
- Add render guard `force_clear()` + `load_post` handler registration with `persistent=True`
- Set up CI with `bpy==5.1.0` Python 3.13 virtual environment

### Phase 2: Expert Prompt System + Mesh Quality Validation
**Rationale:** Prompts are pure Python string data — zero bpy API risk, zero protocol changes. They are the fastest path to measurable LLM quality improvement on a fixed foundation. Mesh quality validation is also standalone with no dependencies on phases 3 or 4. Both ship together because the expert prompt can immediately instruct the LLM to run `analyze_mesh_quality` after construction.
**Delivers:** LLM receives topology, material, lighting, and feedback guidance; `analyze_mesh_quality()` tool reports non-manifold edges, inverted normals, loose vertices, duplicate verts, zero-area faces.
**Uses:** No new dependencies; `bpy.ops.mesh.select_non_manifold`, `bpy.ops.mesh.normals_make_consistent`, `bpy.ops.mesh.remove_doubles`
**Implements:** Prompt modularization pattern from ARCHITECTURE.md; standalone mesh analysis handler
**Avoids:** Pitfall 6 (token runaway) — screenshot budget must be defined in `prompts/feedback.py` before the loop ships
**Key changes:**
- Add `prompts/modeling.py` (topology patterns, boolean strategy, subdivision rules)
- Add `prompts/materials.py` (PBR workflow, node setup)
- Add `prompts/lighting.py` (three-point, HDRI, studio setups)
- Add `prompts/feedback.py` (when/how to screenshot; explicit frequency budget)
- Expand `prompts/workflows.py` with proportions guidance and realistic scale references
- Add `analyze_mesh_quality(object_name)` tool in `tools/mesh_quality.py` + handler in `addon/handlers/`

### Phase 3: Auto-Screenshot Feedback Loop
**Rationale:** Requires both a working Blender 5.1 handler layer (Phase 1) and the `prompts/feedback.py` screenshot budget specification (Phase 2). Building this before Phase 2 would ship an unbounded token sink. The fast viewport capture handler is a targeted addition to existing camera.py.
**Delivers:** LLM can capture the current viewport state after any modeling step in under 500ms without triggering render cycles.
**Uses:** `bpy.ops.render.opengl` with `temp_override` context; `Pillow>=10.0` for resize/encode on MCP server side
**Implements:** Fast Viewport Screenshot pattern from ARCHITECTURE.md; `mode` parameter on `get_viewport_screenshot` tool
**Avoids:** Pitfall 1 (blocking screenshot), Pitfall 5 (headless context check), Pitfall 6 (token runaway)
**Key changes:**
- Add `capture_viewport_fast` handler in `addon/handlers/camera.py` using `bpy.ops.render.opengl`
- Add pre-flight `bpy.context.screen` check; return structured error if headless
- Add `mode` parameter (`"fast"` vs `"render"`) to `get_viewport_screenshot` MCP tool
- Add `Pillow>=10.0` to project dependencies
- Write CI mock fixture for headless capture testing

### Phase 4: Context-Aware Extension Suggestions + `code_exec` Hardening
**Rationale:** Extension suggestions have the most new surface area (new MCP tool + new addon handler + static knowledge base). Placing them last reduces risk — the core is stable before adding new command routes. `code_exec` hardening is grouped here because it is a security fix that reduces the urgency of the `code_exec` escape hatch as the tool set grows; addressing it alongside suggestions limits disruption.
**Delivers:** LLM proactively suggests free extensions (Bool Tool, LoopTools, Node Wrangler, RetopoFlow, ND, Mio3 UV) before tasks that benefit from them; `code_exec` rejects `import os`, `import subprocess`, file I/O.
**Uses:** `RestrictedPython>=7.4`; `bpy.context.preferences.addons` for installed extension detection
**Implements:** Static Knowledge Base pattern from ARCHITECTURE.md; restricted builtins allowlist
**Avoids:** Pitfall 7 (code_exec RCE); anti-pattern of live extension repository queries; auto-install without user consent
**Key changes:**
- Build `src/blend_ai/tools/extension_suggestions.py` with static knowledge base
- Add `suggest_extensions(task_description: str)` MCP tool
- Add `get_installed_extensions` command + `addon/handlers/extensions.py`
- Register `get_installed_extensions` in dispatcher allowlist
- Replace `exec(code, {"__builtins__": __builtins__})` with `RestrictedPython.compile_restricted()` + safe globals
- Add user-facing "unsafe mode" toggle in N-panel defaulting to OFF

### Phase 5: Blender 5.1 New Tools (P2, post-validation)
**Rationale:** New 5.1 API surface should only be exposed after the compatibility foundation is stable and validated. This phase is lower priority and can be deferred until Phase 1-4 user feedback is collected.
**Delivers:** Raycast shader node, Bone Info geometry node, Grid Dilate/Erode node, UV Unwrap SLIM, F-curve Gaussian smoothing, EEVEE Light Path Intensity controls.
**Addresses:** P2 features from FEATURES.md; competitive differentiation on Blender 5.1-only capabilities
**Key changes:** New node tools in `tools/materials.py`, `tools/geometry_nodes.py`; new EEVEE property accessors in `tools/rendering.py`

### Phase Ordering Rationale

- Phase 1 before everything: broken handlers block all testing on the target Blender version
- Phase 2 before Phase 3: `prompts/feedback.py` must define screenshot frequency budget before the feedback loop ships, or every tool call triggers a screenshot
- Phase 3 before Phase 4: fast screenshot is a lower-risk addon change than the new command route required for extension suggestions; validate core patterns first
- Phase 4 last: most new surface area (3 new files, 2 new command routes); lowest risk when built on a stable base
- Phase 5 separate: entirely additive, no migration risk, can slip without blocking other work

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (gpencil handler):** Grease Pencil v3 / Annotation split is a significant API change; the target handler behavior (GP3 drawing objects vs. annotation overlays) requires a design decision before implementation
- **Phase 3 (OpenGL/Vulkan capture):** Blender 4.5 migrated from OpenGL to Vulkan; `bpy.ops.render.opengl` behavior under Vulkan on different platforms is not fully verified in research — needs a test pass on Linux + macOS
- **Phase 4 (RestrictedPython exact API):** RestrictedPython's compile/exec API was noted as MEDIUM confidence; verify the exact `compile_restricted()` + `safe_globals` pattern against the 7.4 release before implementation

Phases with standard patterns (can proceed without phase research):
- **Phase 2 (prompts + mesh quality):** Prompt registration with `@mcp.prompt()` is fully documented; mesh quality operators (`bpy.ops.mesh.*`) are stable bpy API; no unknown territory
- **Phase 5 (new 5.1 nodes):** Node addition follows identical patterns to existing node tools; all node type identifiers verified against official 5.1 release notes

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core stack verified against live PyPI, official Blender developer docs, and official MCP SDK releases; RestrictedPython API patterns rated MEDIUM by STACK researcher — verify exact `compile_restricted()` usage |
| Features | HIGH | Based on official Blender 5.1 release notes, direct competitor GitHub analysis, and official extensions platform download data |
| Architecture | HIGH | Based on direct codebase analysis plus verified Blender 5.x API documentation; all component boundaries reflect existing code structure |
| Pitfalls | HIGH | Six of seven pitfalls identified directly from codebase analysis of affected files; one (token runaway) from community postmortems |

**Overall confidence:** HIGH

### Gaps to Address

- **Grease Pencil v3 scope decision:** Research identified the API split but did not resolve whether blend-ai should target `bpy.types.GreasePencilv3` (3D drawing objects) or `bpy.types.Annotation` (viewport overlays) or both. This requires a product decision before Phase 1 gpencil work begins.
- **Vulkan viewport capture behavior:** `bpy.ops.render.opengl` under Blender 5.1's Vulkan backend on Linux has not been verified. Phase 3 planning should include a discovery task to test capture on all supported platforms.
- **RestrictedPython compile API:** The exact safe globals dict structure and `compile_restricted()` call signature for Blender's `bpy`-heavy code patterns needs a proof-of-concept before Phase 4 implementation to avoid unexpected restriction errors on legitimate bpy usage.
- **Handler test coverage:** `test_addon/test_handlers/` is empty. Any Phase 1 fix that cannot be verified in CI is at risk of regression. Setting up the `bpy==5.1.0` CI test environment and writing at least one test per fixed handler should be a Phase 1 deliverable, not an afterthought.

## Sources

### Primary (HIGH confidence)
- [Blender 5.1 Python API release notes](https://developer.blender.org/docs/release_notes/5.1/python_api/) — breaking API changes, new node types, brush consolidation, VSE renames
- [Blender 5.0 Python API release notes](https://developer.blender.org/docs/release_notes/5.0/python_api/) — EEVEE identifier, BGL removal, asset system, compositor changes, GreasePencil split
- [MCP Python SDK PyPI](https://pypi.org/project/mcp/) — version 1.26.0, Python >=3.10, v2 pre-alpha status
- [bpy PyPI](https://pypi.org/project/bpy/) — 5.1.0 released 2026-03-17, requires Python 3.13
- [Blender Extensions API Listing](https://developer.blender.org/docs/features/extensions/api_listing/) — v1 endpoint URL, JSON schema
- [Blender 5.1 Release](https://www.blender.org/press/blender-5-1-release/) — Raycast node, Geometry Nodes additions, EEVEE improvements
- [Blender Extensions Platform](https://extensions.blender.org/add-ons/) — download counts: LoopTools 2M, Bool Tool 943K, Node Arrange 202K
- [ahujasid/blender-mcp GitHub](https://github.com/ahujasid/blender-mcp) — competitor feature set
- [poly-mcp/Blender-MCP-Server GitHub](https://github.com/poly-mcp/Blender-MCP-Server) — competitor feature set
- Codebase analysis: `addon/handlers/camera.py`, `addon/render_guard.py`, `addon/thread_safety.py`, `addon/handlers/code_exec.py`

### Secondary (MEDIUM confidence)
- [RestrictedPython PyPI](https://pypi.org/project/RestrictedPython/) — CPython 3.9-3.13 support, CVE-2025-22153; exact API patterns not re-verified against source
- [fake-bpy-module GitHub](https://github.com/nutti/fake-bpy-module) — IDE stubs, active maintenance
- [FastMCP vs MCP SDK discussion](https://github.com/jlowin/fastmcp/discussions/2557) — relationship between official SDK FastMCP and standalone fastmcp package
- [HN discussion on blender-mcp](https://news.ycombinator.com/item?id=44622374) — user pain points (non-manifold geometry, missing visual feedback)
- [CG Channel: 5 Key Features in Blender 5.1](https://www.cgchannel.com/2026/03/discover-5-key-features-in-blender-5-1/) — feature list confirmation

### Tertiary (LOW confidence)
- MCP security breach timeline — informed `code_exec` threat modeling; general reference, not Blender-specific

---
*Research completed: 2026-03-23*
*Ready for roadmap: yes*
