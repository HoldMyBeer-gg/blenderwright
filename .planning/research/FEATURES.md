# Feature Research

**Domain:** Blender MCP Server (AI-controlled 3D modeling bridge)
**Researched:** 2026-03-23
**Confidence:** HIGH (Blender 5.1 API via official docs; competitor features via GitHub/web; user pain points via HN and community)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Full Blender 5.1 API compatibility | Blender 5.1 released March 17, 2026 — users run current versions | MEDIUM | Brush properties consolidated into `brush.stroke_method`; `sculpt.sample_color` removed; VSE strip time props renamed; grease pencil/annotation split complete; `BLENDER_EEVEE_NEXT` → `BLENDER_EEVEE`; `scene.node_tree` → `scene.compositing_node_group`; Python 3.13 |
| Viewport screenshot after every build step | Every other MCP server has it; LLM needs to see what it built | LOW | Already partially implemented; needs to be called automatically post-build, not just on request |
| Reliable error messages with context | Scripts fail silently = LLM loops forever; users abandon the tool | LOW | Error must include: what failed, which object, which mode, suggested fix |
| Object selection by name (not index) | All MCP tools require stable references; names are user-facing | LOW | Already implemented; must be consistent across all 161 tools |
| Core primitive creation (mesh, curve, light, camera) | Baseline 3D workflow entry point | LOW | Already implemented |
| Modifier stack (add, configure, apply, remove) | Every Blender workflow uses modifiers (subsurf, mirror, boolean) | LOW | Already implemented |
| Material and shader node control | Without materials, all outputs look like grey clay | MEDIUM | Already implemented with Principled BSDF + node graph |
| Render to file (Cycles + EEVEE) | End goal of almost every workflow | LOW | Already implemented; Blender 5.1 EEVEE identifier changed |
| Import/export (FBX, OBJ, glTF, USD, STL) | Users need assets in and out of the pipeline | LOW | Already implemented |
| Thread-safe Blender command execution | Blender is single-threaded; ignoring this crashes Blender | HIGH | Already implemented via main-thread queue |
| Grease Pencil 3.0 API support | GP3 is the active API in 5.x; old `bpy.data.grease_pencils` is `bpy.data.annotations` now | HIGH | Current gpencil tools likely broken on 5.x due to the full rewrite landed in 4.3+ |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Auto-screenshot feedback loop | LLM captures viewport after each build step and critiques the result before continuing — closes the "blind building" problem | MEDIUM | Competitors either have no feedback or require user to trigger manually. Pattern: `build → screenshot → critique → correct → screenshot`. Key insight: multimodal LLM can spot issues (disconnected geometry, wrong proportions, flat normals) that tool return values cannot. |
| Expert MCP prompts with topology guidance | Instructs the LLM on WHY and HOW: quad topology vs. triangles, proper edge flow for deformation, when to use modifiers vs. direct mesh editing | MEDIUM | No competitor does this. The best-practices prompt is a start; needs topology, proportions, scale reference, lighting principles. Domain: `blender_best_practices`, `character_topology`, `hard_surface_workflow`, `environment_setup`, `lighting_principles`. |
| Mesh quality validation tools | Detects and reports: non-manifold edges, loose vertices, inverted normals, disconnected islands, zero-area faces, duplicate vertices | MEDIUM | Tool: `analyze_mesh_quality(object_name)` returning structured JSON. Enables the LLM to run quality checks post-construction and self-correct. Community pain point: "models need heavy cleanup — non-manifold edges, messy triangles." |
| Context-aware Blender extension suggestions | Before starting a complex task, the server checks if a free extension (Bool Tool, LoopTools, Node Wrangler, ND, Mio3 UV) is installed and suggests it proactively | MEDIUM | Extensions platform has 785 addons. Top by downloads: LoopTools (2M), Bool Tool (943K), Node Arrange (202K). Key insight: suggest-before-starting, not search. Already done for Bool Tool — generalize the pattern. |
| Workflow chaining tools (high-level operations) | Single calls that chain 5-10 low-level steps into expert patterns: "set up studio lighting", "create base mesh for character", "prep scene for product render" | LOW-MEDIUM | Already started in `prompts/workflows.py`. Needs elevation to actual tools (not just prompts) so the LLM executes them as atomic operations with error handling at each step. |
| Blender 5.1 new nodes exposed as tools | Raycast shader node; Geometry Nodes: Bone Info, Grid Dilate/Erode, Cube Grid Topology, Grid Mean/Median, Matrix SVD, Pack UV Islands (custom regions), UV Unwrap SLIM; Compositor: Mask to SDF | MEDIUM | Competitors running on 4.x cannot offer these. These are available only in 5.1+ and represent real workflow wins for NPR shading, procedural rigging, and volume work. |
| EEVEE 5.1 performance-aware rendering | Expose Light Path Intensity controls; leverage 25-50% faster shader compilation; texture pooling means less VRAM thrashing | LOW | Low complexity: expose 2-3 new EEVEE properties added in 5.1. High value: users ask about EEVEE quality/speed constantly. |
| Animation evaluation speed resource (5.1) | 5.1 delivers 2.3-4x faster rig evaluation; expose F-curve Gaussian smoothing modifier | LOW | New `bpy.types.FModifierSmooth` exposed as a configurable tool for non-destructive F-curve cleanup. |
| Granular vertex/edge/face selection by index | Current limitation: all mesh ops operate on "all selected"; users need precise control for complex modeling | HIGH | Requires selection state management across calls. Stateless MCP protocol makes this hard — needs design thought. Can be partially solved with selection sets stored as object custom properties. |
| MCP resources for Blender state | LLM reads scene/objects/materials as structured context before acting, not just tool return values | LOW | Already implemented (scene, objects, materials resources). Add: active modifiers list, render settings summary, active node tree summary. |
| Undo grouping / operation transactions | Wrap multi-step MCP operations into a single undo block — user can undo an "entire workflow" with Ctrl+Z | HIGH | Blender supports `bpy.ops.ed.undo_push(message=...)`. Complex to get right — current tools push individual undo steps. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Arbitrary Python code execution (`code_exec`) without sandboxing | Feels like an escape hatch for anything the API doesn't expose | Allows full filesystem access, network calls, process spawning from inside Blender's Python. A single malicious or confused LLM call can delete files, exfiltrate data, or install malware. Current implementation has this vulnerability. | Harden with an explicit allowlist of permitted `bpy.ops` namespaces and a deny list for `os`, `subprocess`, `socket`, `importlib`. Or remove `code_exec` entirely and fill gaps with explicit tools. |
| Remote/network access (non-localhost) | Power users want to run Blender on a GPU server and control from another machine | Destroys the security model entirely. Exposes Blender's Python environment to the network. Any MCP command = remote code execution. | Document that remote setups should use SSH tunneling to forward localhost:9876. Never bind to 0.0.0.0. |
| Real-time viewport streaming | Demos look impressive with live video of Blender responding | MCP is a stateless request/response protocol. Streaming requires WebSocket or SSE; changes the architecture fundamentally. Token costs explode. Latency is unavoidable. | Use the auto-screenshot feedback loop instead — captures state on demand, not continuously. |
| LLM-generated mesh from text only (no tools) | "Just generate the 3D model" without tool calls | Requires AI-to-3D model (Hyper3D Rodin, Meshy, Tripo) — a separate product category. LLMs cannot generate clean topology purely from text. | Integrate as a suggested external workflow: "For organic meshes, consider Meshy/Tripo then import via glTF." Document in extension suggestions. |
| Multi-user / multi-connection Blender control | Teams want to collaborate on the same Blender file | Blender is fundamentally single-threaded. The addon accepts one TCP connection. Concurrent modifications will corrupt scene state. | Out of scope by design. Document clearly. If needed: use Blender's built-in multi-user linked libraries for collaboration. |
| Auto-install Blender extensions on behalf of the user | "Just install Bool Tool automatically" | Bypasses user consent. Extensions can contain arbitrary Python. Auto-installation is a supply chain attack vector. | Detect if extension is installed and tell the user to install it (with exact URL/name). Never install silently. |
| Node graph "create full graph from description" (single call) | Seems more efficient than sequential node creation | Node graphs have complex topology. A single-call approach requires the LLM to describe the entire graph upfront, which breaks on errors mid-way with no partial rollback. | Keep sequential: add node → connect → add node. The LLM builds incrementally and can recover from individual step failures. Error recovery is impossible with atomic graph creation. |
| Sculpt brush stroke simulation | "Draw strokes programmatically" | `bpy.ops.sculpt.brush_stroke` requires active viewport + mouse context that cannot be reliably injected from a headless TCP server. Crashes Blender when called without proper context. | Use remesh, multi-res, and shape key tools instead. Document this limitation clearly so LLMs don't attempt it. |

---

## Feature Dependencies

```
[Auto-Screenshot Feedback Loop]
    └──requires──> [Screenshot Tool] (already exists)
    └──requires──> [LLM Vision / Multimodal Client] (Claude, GPT-4o — not our concern)
    └──enhances──> [Mesh Quality Validation] (screenshot shows visual issues; mesh validator shows topology issues)

[Mesh Quality Validation]
    └──requires──> [Mesh Editing Tools] (to fix what it finds)
    └──enhances──> [Expert Prompts] (prompt tells LLM to run validator after every mesh op)

[Expert MCP Prompts]
    └──requires──> [All Tool Modules] (prompts guide use of existing tools)
    └──enhances──> [Auto-Screenshot Feedback Loop] (prompt instructs: "screenshot and critique after building")

[Blender 5.1 Compatibility]
    └──requires──> [All existing handlers fixed] (broken handlers block all tool use)
    └──blocks──> [Blender 5.1 New Nodes/Features] (cannot add new features on broken foundation)

[Blender 5.1 New Nodes]
    └──requires──> [Blender 5.1 Compatibility] (must fix breaking changes first)

[Context-Aware Extension Suggestions]
    └──requires──> [Extension detection tool] (check bpy.context.preferences.addons)
    └──enhances──> [Expert Prompts] (prompt references extensions when available)

[Workflow Chaining Tools]
    └──requires──> [All underlying tool modules] (chains build on primitives)
    └──enhances──> [Expert Prompts] (prompts reference workflow tools)

[Granular Selection by Index]
    └──conflicts──> [Stateless MCP Protocol] (selection state must persist across calls)
    └──requires──> [Selection state stored in object custom properties] (workaround design)

[code_exec Hardening]
    └──conflicts──> [Arbitrary code execution] (hardening reduces escape-hatch utility)
    └──enhances──> [Security posture] (prevents malicious/confused LLM calls)
```

### Dependency Notes

- **Blender 5.1 compatibility blocks everything else**: Broken handlers mean users on 5.1 cannot use the server at all. This is P0.
- **Auto-screenshot requires no new Blender-side infrastructure**: The screenshot tool already exists. The loop is implemented in the MCP prompt/workflow layer.
- **Mesh quality validation is standalone**: No dependencies on other new features. Can ship independently.
- **New 5.1 nodes require 5.1 compatibility first**: Adding Raycast node tools while brush property handlers are broken helps nobody.

---

## MVP Definition

This is a subsequent milestone — the "v1" already ships (161 tools, v0.2.0). The milestone MVP is the minimal set that addresses the most painful user gaps.

### Ship First (This Milestone)

- [x] Blender 5.1 API compatibility — all breaking changes fixed (brush stroke consolidation, grease pencil/annotation split, EEVEE identifier, VSE strip props, `scene.compositing_node_group`) — **users on 5.1 cannot use the server without this**
- [x] Auto-screenshot feedback loop — post-build viewport capture + LLM critique pass — **highest impact differentiator, low implementation cost**
- [x] Mesh quality validation tool — `analyze_mesh_quality()` returning non-manifold, normals, loose geo, duplicate verts — **directly addresses the #1 user complaint**
- [x] Expert topology prompts — extend `blender_best_practices` with topology guidance, scale references, lighting principles, when-to-use-which-modifier — **no new tools needed, high ROI**
- [x] Context-aware extension suggestions — detect if Bool Tool, LoopTools, Node Wrangler, ND, Mio3 UV are installed; suggest before task — **proactive, fits the "expert assistant" vision**

### Add After Validation (v0.3.x)

- [ ] Blender 5.1 new tools — Raycast shader node, Bone Info geometry node, Grid Dilate/Erode, Mask to SDF compositor node, UV Unwrap SLIM, F-curve Gaussian smoothing — **add after foundation is solid**
- [ ] Workflow chaining tools (elevated from prompts to tools) — `setup_product_shot()`, `create_character_basemesh()`, `setup_three_point_lighting()` — **trigger: user feedback that prompt-based workflows are too manual**
- [ ] EEVEE 5.1 property exposure — Light Path Intensity controls, AOV limit (now 128) — **low complexity, incremental quality improvement**
- [ ] `code_exec` hardening — namespace allowlist, deny `os`/`subprocess`/`socket` — **trigger: security audit or first reported incident**

### Future Consideration (v1.0+)

- [ ] Granular vertex/edge/face selection by index — requires design work for stateless protocol; significant addon changes — **defer: current all-selected approach covers most use cases**
- [ ] Undo grouping / MCP-level transactions — complex interaction with Blender's undo system; risk of data loss — **defer: needs careful design; current behavior is acceptable**
- [ ] Animation evaluation performance tools (5.1 speed) — expose Gaussian F-curve smoothing as standalone tool — **defer: niche use case until character animation workflows are more common**

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Blender 5.1 API compatibility | HIGH | MEDIUM | P1 |
| Auto-screenshot feedback loop | HIGH | LOW | P1 |
| Mesh quality validation tool | HIGH | MEDIUM | P1 |
| Expert topology/workflow prompts | HIGH | LOW | P1 |
| Context-aware extension suggestions | MEDIUM | LOW | P1 |
| Blender 5.1 new nodes (Raycast, Bone Info, etc.) | MEDIUM | MEDIUM | P2 |
| Workflow chaining tools | MEDIUM | MEDIUM | P2 |
| EEVEE 5.1 property exposure | LOW | LOW | P2 |
| code_exec hardening | HIGH (security) | MEDIUM | P2 |
| Granular selection by index | MEDIUM | HIGH | P3 |
| Undo grouping / transactions | LOW | HIGH | P3 |
| F-curve Gaussian smoothing tool | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for this milestone
- P2: Should have, add when P1 complete
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | ahujasid/blender-mcp | poly-mcp/Blender-MCP-Server | blend-ai (current) | blend-ai (target) |
|---------|----------------------|-----------------------------|--------------------|-------------------|
| Tool count | ~10-15 | ~51 | 161 | 165-175 |
| Blender 5.1 compat | Unknown | Unknown | Partial (bugs) | Full |
| Auto-screenshot feedback | Manual trigger | No | Manual trigger | Auto post-build |
| Mesh quality validation | No | Partial (mesh_stats) | No | Yes — full suite |
| Expert topology prompts | No | No | Basic | Comprehensive |
| Extension suggestions | No | No | Bool Tool only | Multi-extension |
| Thread safety | Unknown | Yes (queue) | Yes | Yes |
| Security model | Localhost | Localhost | Localhost + allowlist | Localhost + hardened |
| Poly Haven / AI asset integration | Yes | No | No | Anti-feature (scope) |
| New 5.1 nodes (Raycast, Bone Info) | No | No | No | Yes (P2) |
| Workflow prompts | No | No | 5 prompts | Expanded |

**Competitive insight:** No competitor implements the auto-screenshot critique loop or comprehensive mesh quality validation. Both are technically straightforward and represent clear differentiation. ahujasid/blender-mcp's strength is integrations (Poly Haven, Hyper3D Rodin, Sketchfab) — we deliberately avoid these (scope creep, dependency, trust issues).

---

## Blender 5.1 Specific Feature Coverage

### Breaking Changes Requiring Fixes

| Change | Impact on blend-ai | Handler/Tool Affected |
|--------|-------------------|-----------------------|
| `brush.stroke_method` enum consolidates 8 properties | `set_brush_property` calls for `use_airbrush` etc. will fail silently or error | `tools/sculpting.py`, `addon/handlers/sculpting.py` |
| `sculpt.sample_color` operator removed | Any code calling this op will throw `RuntimeError` | `addon/handlers/sculpting.py` (if referenced) |
| Grease Pencil → Annotation API split | `bpy.data.grease_pencils` → `bpy.data.annotations`; `GPencilStroke` → `AnnotationStroke` | `tools/gpencil.py`, `addon/handlers/gpencil.py` |
| `BLENDER_EEVEE_NEXT` → `BLENDER_EEVEE` | Engine enum string mismatch breaks render engine selection | `tools/rendering.py`, `addon/handlers/rendering.py` |
| `scene.node_tree` → `scene.compositing_node_group` | Compositor node access broken | Any compositor-adjacent tool |
| VSE strip time properties renamed | `frame_final_duration` → `duration`, etc. (8 renames, deprecated until 6.0) | `tools/animation.py` if VSE strips referenced |
| `template_list` columns param deprecated | UI-only; no tool impact | `addon/ui_panel.py` (cosmetic) |
| Python 3.13 | Syntax or stdlib changes unlikely to break current code but need verification | All Python files |
| `scene.use_nodes` deprecated (removal in 6.0) | Low urgency; deprecated not removed | Compositor tools |

### New 5.1 Features to Expose (P2)

| Feature | Blender API | New Tool Name | Value |
|---------|------------|---------------|-------|
| Raycast shader node | `ShaderNodeRaycast` | `add_shader_node(type='RAYCAST')` | NPR outlines, decals, toon shading |
| Bone Info geometry node | `GeometryNodeInputBone` | `add_geometry_node(type='INPUT_BONE')` | Procedural rigging workflows |
| Grid Dilate/Erode node | `GeometryNodeGridDilateErode` | `add_geometry_node(type='GRID_DILATE_ERODE')` | Volume sculpting/SDF ops |
| Cube Grid Topology node | `GeometryNodeCubeGridTopology` | `add_geometry_node(type='CUBE_GRID_TOPOLOGY')` | Volume grid creation |
| Mask to SDF compositor node | `CompositorNodeMaskToSDF` | `add_compositor_node(type='MASK_TO_SDF')` | Procedural compositing effects |
| UV Unwrap SLIM | `minimum_stretch=True` param on unwrap op | `unwrap_uv(method='SLIM')` | Better UV quality for organic meshes |
| F-curve Gaussian smoothing | `bpy.types.FModifierSmooth` | `add_fcurve_modifier(type='SMOOTH')` | Non-destructive animation cleanup |
| Light Path Intensity controls | `eevee.light_path_*` properties | `set_eevee_property(name='light_threshold', ...)` | Direct/indirect light balance |
| `bpy.app.cachedir` | New app property | Resource: `blender://system/cache` | Useful for debugging |
| `window.find_playing_scene()` | New window method | Internal use in render guard | Better render state detection |

---

## Sources

- [Blender 5.1 Release Notes](https://developer.blender.org/docs/release_notes/5.1/) — HIGH confidence, official
- [Blender 5.1 Python API Changes](https://developer.blender.org/docs/release_notes/5.1/python_api/) — HIGH confidence, official
- [Blender 5.1 Geometry Nodes](https://developer.blender.org/docs/release_notes/5.1/geometry_nodes/) — HIGH confidence, official
- [Blender 5.1 EEVEE & Viewport](https://developer.blender.org/docs/release_notes/5.1/eevee/) — HIGH confidence, official
- [Blender 5.0 Python API Changes](https://developer.blender.org/docs/release_notes/5.0/python_api/) — HIGH confidence, official
- [CG Channel: 5 Key Features in Blender 5.1](https://www.cgchannel.com/2026/03/discover-5-key-features-in-blender-5-1/) — MEDIUM confidence, editorial
- [ahujasid/blender-mcp GitHub](https://github.com/ahujasid/blender-mcp) — HIGH confidence for competitor feature set
- [poly-mcp/Blender-MCP-Server GitHub](https://github.com/poly-mcp/Blender-MCP-Server) — HIGH confidence for competitor feature set
- [Blender Extensions Platform](https://extensions.blender.org/add-ons/) — HIGH confidence, official; top addons by download count
- [HN discussion on blender-mcp](https://news.ycombinator.com/item?id=44622374) — MEDIUM confidence; reflects real user pain points
- [LoopTools: 2M downloads; Bool Tool: 943K downloads](https://extensions.blender.org/add-ons/) — HIGH confidence, official platform data

---

*Feature research for: Blender MCP Server (blend-ai)*
*Researched: 2026-03-23*
