# Architecture Research

**Domain:** Blender MCP Server (AI-to-Blender bridge)
**Researched:** 2026-03-23
**Confidence:** HIGH — based on direct codebase analysis + verified Blender 5.x API documentation

---

## Existing Architecture (Baseline)

The current system is a three-tier bridge: MCP server (stdio) → TCP socket → Blender addon (main thread queue).

```
┌────────────────────────────────────────────────────────────────┐
│                    AI CLIENT (Claude, etc.)                     │
│                 MCP protocol over stdio (JSON-RPC)             │
└──────────────────────────┬─────────────────────────────────────┘
                           │ stdio
┌──────────────────────────▼─────────────────────────────────────┐
│                    MCP SERVER LAYER                             │
│  src/blend_ai/                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
│  │  tools/    │  │ resources/ │  │  prompts/  │  │validators│  │
│  │ (24 mods)  │  │ scene_info │  │ workflows  │  │  .py     │  │
│  └─────┬──────┘  └─────┬──────┘  └────────────┘  └──────────┘  │
│        └───────────────┴──────────────────────────────────┐     │
│                                              connection.py │     │
└──────────────────────────────────────────────────────────┬┘     │
                                                           │ TCP   │
                                                127.0.0.1:9876     │
┌──────────────────────────────────────────────────────────▼──────┐
│                    BLENDER ADDON LAYER                           │
│  addon/                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐  │
│  │ server.py  │  │dispatcher.py│  │thread_     │  │render_    │  │
│  │ (TCP)      │→ │(allowlist) │→ │safety.py   │  │guard.py   │  │
│  └────────────┘  └─────┬──────┘  │(queue)     │  │(events)   │  │
│                        │         └─────┬───────┘  └───────────┘  │
│                        │               │ main thread              │
│                  ┌─────▼───────────────▼──────────────────────┐  │
│                  │          handlers/ (24 modules)             │  │
│                  │     bpy API calls — all on main thread      │  │
│                  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## New Feature Integration Architecture

Four features must be integrated into the existing bridge without breaking it. Each maps cleanly to a specific tier.

### System Overview (After Milestone)

```
┌──────────────────────────────────────────────────────────────────┐
│                    AI CLIENT (Claude, etc.)                       │
└───────────────────────────────┬──────────────────────────────────┘
                                │ stdio
┌───────────────────────────────▼──────────────────────────────────┐
│                    MCP SERVER LAYER  [src/blend_ai/]              │
│                                                                   │
│  tools/           resources/         prompts/        validators/  │
│  ┌────────────┐   ┌────────────┐    ┌────────────┐               │
│  │screenshot  │   │ scene_info │    │ workflows  │ (EXPAND)       │
│  │(existing)  │   │            │    │ modeling   │               │
│  └────────────┘   └────────────┘    │ materials  │               │
│                                     │ lighting   │               │
│  NEW: feedback loop is LLM-driven   │ topology   │               │
│  via tool sequencing in prompts.    └────────────┘               │
│  No new tool needed — prompts                                     │
│  instruct WHEN to call screenshot.  NEW: extension_suggestions/  │
│                                     ┌────────────────────────┐   │
│                                     │ suggest_extensions.py  │   │
│                                     │ (static knowledge base │   │
│                                     │  + bpy introspection)  │   │
│                                     └────────────────────────┘   │
└────────────────────────┬─────────────────────────────────────────┘
                         │ TCP 127.0.0.1:9876
┌────────────────────────▼─────────────────────────────────────────┐
│                    BLENDER ADDON LAYER  [addon/]                  │
│                                                                   │
│  handlers/                                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  [existing 24 modules — updated for 5.x API compat]      │    │
│  │  rendering.py   ← fix BLENDER_EEVEE engine ID            │    │
│  │  sculpting.py   ← fix sculpt_brush_type rename           │    │
│  │  scene.py       ← fix compositing_node_group             │    │
│  │  camera.py      ← screenshot already here, works fine    │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
│  NEW handlers/ modules:                                           │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  extensions.py  ← query installed/available extensions     │  │
│  │                    bpy.context.preferences.addons           │  │
│  │                    bpy.ops.extensions.package_install()    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Tier | Responsibility | Communicates With |
|-----------|------|---------------|-------------------|
| `tools/screenshot.py` | MCP Server | Exposes `get_viewport_screenshot` tool; forwards to addon | `connection.py` → `capture_viewport` handler |
| `prompts/workflows.py` | MCP Server | Expert workflow prompts — instructs LLM WHEN to screenshot, best practices | LLM via MCP protocol (no code path to addon) |
| `prompts/modeling.py` (new) | MCP Server | Modeling-specific expert guidance, topology patterns | LLM via MCP protocol only |
| `prompts/materials.py` (new) | MCP Server | PBR, node setup, shader best practices | LLM via MCP protocol only |
| `tools/extension_suggestions.py` (new) | MCP Server | MCP tool: given a task description, suggest free extensions; reads from static knowledge base | `connection.py` → `get_installed_extensions` handler |
| `addon/handlers/extensions.py` (new) | Blender Addon | Query installed extensions via `bpy.context.preferences.addons`; optionally install via `bpy.ops.extensions` | `dispatcher.py` allowlist, `bpy` API |
| `addon/handlers/rendering.py` (existing) | Blender Addon | Render operations — needs Blender 5.x fixes | `dispatcher.py` |
| `addon/handlers/sculpting.py` (existing) | Blender Addon | Sculpt tools — needs brush_type rename fix | `dispatcher.py` |
| `addon/handlers/scene.py` (existing) | Blender Addon | Scene info — needs compositing_node_group fix | `dispatcher.py` |
| `addon/render_guard.py` (existing) | Blender Addon | Stuck-state fix: add manual reset command | `dispatcher.py`, `bpy.app.handlers` |

---

## Data Flow

### Auto-Screenshot Feedback Loop

The feedback loop is **LLM-driven, not server-driven**. The MCP protocol is stateless request/response — the server cannot push screenshots to the LLM. Instead, expert prompts instruct the LLM to call `get_viewport_screenshot` after modifying scene geometry, completing a workflow stage, or when a task description implies visual verification.

```
LLM executes workflow prompt
    |
    ├─ [build/modify operations] → tool calls → addon → bpy
    |
    └─ prompt instructs: "after completing each modeling step,
       call get_viewport_screenshot to verify the result"
           |
           ▼
    LLM calls get_viewport_screenshot
           |
           ▼
    MCP server → TCP → capture_viewport handler (camera.py)
    bpy.ops.render.render(write_still=True) → base64 PNG
           |
           ▼
    base64 image returned to LLM as tool result
           |
           ▼
    LLM sees viewport, assesses quality, continues or self-corrects
```

**Key constraint:** The current `capture_viewport` handler triggers a full Blender render (`bpy.ops.render.render`). This is slow and blocks the render guard. A new `capture_viewport_fast` handler using `bpy.ops.screen.screenshot_area()` (viewport-only, no render) should be added in the addon for quick feedback captures without triggering the render guard.

```
Fast screenshot path (new):
LLM calls get_viewport_screenshot(mode="fast")
    |
    ▼
MCP tool → send_command("capture_viewport_fast", ...)
    |
    ▼
addon/handlers/camera.py handle_capture_viewport_fast()
    bpy.ops.screen.screenshot_area() — does NOT trigger render guard
    return base64 PNG
```

### Extension Suggestion Flow

```
LLM receives task description
    |
    └─ expert prompt: "if task involves retopology, check for
       RetopoFlow; if task involves hard-surface, check for
       HardOps/BoxCutter; suggest before starting"
           |
           ▼
LLM calls suggest_extensions(task_description="...")
    MCP server tool: matches task keywords against static knowledge base
    calls get_connection().send_command("get_installed_extensions")
           |
           ▼
    addon/handlers/extensions.py
    bpy.context.preferences.addons → list of installed extension IDs
    returns installed list
           |
           ▼
    MCP tool computes: recommended_extensions - installed_extensions
    returns suggestion list with install instructions
           |
           ▼
LLM presents suggestions to user before starting task
```

**Extension knowledge base lives entirely in the MCP server tier** (a Python dict in `tools/extension_suggestions.py`). No Blender API needed for the knowledge base itself — only for checking what is already installed.

### Expert Prompt Invocation

Prompts are passive — they are MCP resources the LLM retrieves, not code paths that run. The LLM's reasoning uses the prompt content to guide its tool selection and sequencing.

```
MCP client retrieves prompt (e.g., "blender_topology_guide")
    |
    ▼
FastMCP returns prompt string
    |
    ▼
LLM incorporates guidance into its reasoning
    |
    ▼
LLM sequences tool calls accordingly (e.g., apply_transform
before boolean, capture screenshot after each major step)
```

### Blender 5.x Compatibility Fix Flow

All fixes are contained to the addon handler layer. No MCP server changes needed for 5.x compat — the TCP protocol and command names do not change.

```
Existing broken 4.x code path (rendering.py):
    bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    bpy.context.scene.eevee.taa_render_samples = n

Fixed 5.x code path:
    bpy.context.scene.render.engine = "BLENDER_EEVEE"  # renamed in 5.0
    bpy.context.scene.eevee.taa_render_samples = n      # still valid in 5.x

Version-gated pattern for cross-version support:
    if bpy.app.version >= (5, 0, 0):
        engine_id = "BLENDER_EEVEE"
    else:
        engine_id = "BLENDER_EEVEE_NEXT"
```

---

## Architectural Patterns

### Pattern 1: Prompt-Driven Feedback (not server-driven)

**What:** The screenshot feedback loop is controlled entirely by LLM reasoning guided by expert prompts. The MCP server does not autonomously trigger screenshots or loop. Each screenshot is an explicit LLM tool call.

**When to use:** All visual verification, quality assessment, topology review.

**Why this approach:** MCP is stateless request/response. The server has no ability to initiate communication. Autonomous loops would require persistent state and background tasks — outside the protocol. Prompt-driven loops require zero new infrastructure and work within existing constraints.

**Trade-off:** The LLM must be instructed to use the loop — it will not happen automatically unless the prompt includes instructions. This is correct behavior; it keeps token usage predictable.

### Pattern 2: Static Knowledge Base for Extension Suggestions

**What:** A Python dict in `src/blend_ai/tools/extension_suggestions.py` maps task keywords to curated extension recommendations. No network access, no extensions.blender.org API calls.

**When to use:** All extension suggestion features.

**Why this approach:** `bpy.ops.extensions` operators for remote repository access are partially undocumented and require `bpy.app.online_access` permission. A static knowledge base is deterministic, zero-latency, and zero-risk. The knowledge base can be updated in code as new extensions gain community trust.

**Trade-off:** Knowledge base goes stale over time. Mitigate by scoping recommendations to stable, widely-used extensions (RetopoFlow, HardOps, BoxCutter, Node Wrangler). These change rarely.

```python
# src/blend_ai/tools/extension_suggestions.py (pattern)
EXTENSION_KNOWLEDGE_BASE = {
    "retopology": {
        "extensions": [
            {
                "name": "RetopoFlow",
                "id": "retopoflow",
                "url": "https://extensions.blender.org/add-ons/retopoflow/",
                "why": "Provides streamlined retopology tools missing from vanilla Blender",
            }
        ],
        "keywords": ["retopo", "retopology", "quad", "topology", "polycount", "low-poly from high"],
    },
    ...
}
```

### Pattern 3: Version-Gated bpy Calls

**What:** Use `bpy.app.version` tuple comparisons to branch between 4.x and 5.x API paths within handler functions.

**When to use:** Any handler that touches a renamed/removed API (render engine IDs, brush type enums, compositor node tree access, EEVEE settings).

**Why this approach:** Keeps backward compatibility (4.0+) while gaining 5.x support without a fork. The version tuple `(major, minor, patch)` is always available in bpy.

```python
# addon/handlers/rendering.py (pattern)
def handle_set_render_engine(params):
    engine = params.get("engine", "CYCLES")

    # Normalize EEVEE engine ID across Blender versions
    if engine == "EEVEE":
        if bpy.app.version >= (5, 0, 0):
            engine = "BLENDER_EEVEE"
        else:
            engine = "BLENDER_EEVEE_NEXT"

    bpy.context.scene.render.engine = engine
    return {"engine": bpy.context.scene.render.engine}
```

### Pattern 4: Fast Viewport Screenshot (No Render Guard Trigger)

**What:** A new `capture_viewport_fast` handler uses `bpy.ops.screen.screenshot_area()` to capture the current viewport without triggering `bpy.ops.render.render`. This does not set the render guard to "busy."

**When to use:** All feedback loop screenshots where the user wants the current viewport state, not a final render.

**Why this approach:** The existing `capture_viewport` handler calls `bpy.ops.render.render(write_still=True)` — this triggers the render guard, causing a busy state for all subsequent commands. For quick visual checks the LLM needs frequent, fast viewport grabs without triggering render cycles.

**Trade-off:** `bpy.ops.screen.screenshot_area()` captures the viewport exactly as displayed (SOLID, MATERIAL, RENDERED shading — whatever is active). It does not produce a clean render. For final output, `capture_viewport` (full render) remains the correct call.

### Pattern 5: Prompt Modularization

**What:** Split the single `prompts/workflows.py` into domain-specific prompt modules. Each module contains prompts relevant to one modeling domain.

**When to use:** When the number of prompts in workflows.py exceeds ~5 or when prompt content is domain-specific enough to confuse across domains.

**Structure:**
```
src/blend_ai/prompts/
    workflows.py      # high-level workflow chains (existing)
    modeling.py       # mesh topology, subdivision, boolean strategy (new)
    materials.py      # PBR workflow, node setup patterns (new)
    lighting.py       # three-point, HDRI, studio setups (new)
    feedback.py       # when/how to use screenshots for self-correction (new)
```

Each module registers prompts with `@mcp.prompt()` and is imported in `server.py`. No other changes to the loading mechanism are needed.

---

## Blender 5.x Compatibility: Affected Components

The following handlers have confirmed API breakage in Blender 5.0+. All fixes stay within the addon handler layer.

| Handler File | Breaking Change | Fix |
|---|---|---|
| `addon/handlers/rendering.py` | `BLENDER_EEVEE_NEXT` → `BLENDER_EEVEE` | Version-gate engine ID normalization |
| `addon/handlers/rendering.py` | `scene.eevee.gtao_distance` → `view_layer.eevee.ambient_occlusion_distance` | Version-gate AO property access |
| `addon/handlers/sculpting.py` | `brush.sculpt_tool` → `brush.sculpt_brush_type` (prefix change) | Version-gate brush type property name |
| `addon/handlers/scene.py` | `scene.node_tree` → `scene.compositing_node_group` | Version-gate compositor access |
| `addon/handlers/sculpting.py` | `sculpt.sample_color` operator removed (merged into `paint.sample_color`) | Use `paint.sample_color` on 5.1+ |
| `addon/handlers/materials.py` | Sky Texture node inputs `sun_direction`, `turbidity` removed | Flag/document in node allowlist |
| Any handler with render pass names | Pass names changed (e.g., `DiffCol` → `Diffuse Color`) | Update pass name constants |

---

## Suggested Build Order (Phase Implications)

The four features have different dependency profiles. This ordering minimizes risk at each phase.

### Phase 1: Blender 5.x Compatibility Fixes
**Why first:** Every other feature builds on handler code. Broken handlers in 5.x mean all testing and development must be done on 4.x. Fix the foundation before adding to it.

- Fix EEVEE engine ID (`BLENDER_EEVEE_NEXT` → `BLENDER_EEVEE`)
- Fix `scene.compositing_node_group`
- Fix brush type property names
- Fix `scene.eevee.gtao_distance` location
- Fix render pass name constants
- Add version-gate pattern to all affected handlers
- Verify `capture_viewport` still works in 5.x (render guard interaction)

**Deliverable:** All existing 161 tools pass tests on Blender 5.1.

### Phase 2: Expert Prompt System
**Why second:** Prompts are pure Python string data — zero Blender API risk, zero TCP protocol changes. They deliver immediate LLM quality improvement without touching any fragile code paths. Once prompts are in place, they guide how the feedback loop is used.

- Add `prompts/modeling.py` (topology patterns, boolean strategy, subdivision rules)
- Add `prompts/materials.py` (PBR workflow, node setup)
- Add `prompts/feedback.py` (when to call `get_viewport_screenshot`, self-correction patterns)
- Expand `prompts/workflows.py` with improved defaults and realistic proportions guidance
- Test: verify all prompts register correctly, return expected content

**Deliverable:** LLM receives expert guidance on workflow quality without any new tools.

### Phase 3: Auto-Screenshot Feedback Loop
**Why third:** Requires the fast viewport screenshot handler (new addon code) and the feedback prompt (Phase 2). The feedback prompt defines the pattern the LLM uses to invoke screenshots.

- Add `capture_viewport_fast` handler in `addon/handlers/camera.py`
  - Uses `bpy.ops.screen.screenshot_area()` — does not trigger render guard
  - Returns base64 PNG of current viewport (not a full render)
- Add `mode` parameter to `get_viewport_screenshot` MCP tool (`"fast"` vs `"render"`)
- Write `prompts/feedback.py` instructions for the screenshot-assess-correct loop
- Fix the known bug: screenshot tool should retry on busy state (currently it doesn't)

**Deliverable:** LLM can visually verify its work after each modeling step without triggering render cycles.

### Phase 4: Extension Suggestions
**Why fourth:** Independent of phases 1-3 at the code level. Placed last because it requires the most new surface area (new MCP tool + new addon handler + knowledge base data). Lower risk to build after the core is stable.

- Build static extension knowledge base in `src/blend_ai/tools/extension_suggestions.py`
- Add `suggest_extensions(task_description: str)` MCP tool
- Add `get_installed_extensions` command + `addon/handlers/extensions.py` handler
  - Uses `bpy.context.preferences.addons` to enumerate installed extensions
  - Returns list of addon IDs
- Add extension suggestion instruction to relevant workflow prompts (e.g., retopology prompt mentions RetopoFlow)

**Deliverable:** LLM proactively suggests free extensions before starting tasks that benefit from them.

---

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|---|---|---|
| MCP tools ↔ Blender addon | TCP JSON-RPC (length-prefixed) via `BlenderConnection` | No change needed for new features |
| Prompts ↔ LLM | MCP prompt protocol via FastMCP `@mcp.prompt()` | Prompts add zero protocol complexity |
| Extension suggestions ↔ Blender | TCP command `get_installed_extensions` | New command, must register in dispatcher allowlist |
| Fast screenshot ↔ Render guard | `bpy.ops.screen.screenshot_area()` — bypasses render guard by design | Must verify this operator does not set render guard state |
| Version-gated handlers ↔ bpy | `bpy.app.version` tuple at runtime | Standard Blender addon pattern; no external dependency |

### No External Integration Required

All four features remain fully local. No network access, no extensions.blender.org API calls at runtime, no new dependencies. The static extension knowledge base is bundled with the MCP server package.

---

## Anti-Patterns

### Anti-Pattern 1: Server-Initiated Screenshot Loops

**What people do:** Try to make the MCP server autonomously capture screenshots and inject them into the conversation after every tool call.

**Why it's wrong:** MCP is strictly request/response — the server cannot push data to the client unsolicited. Implementing a server-side loop would require protocol modifications, persistent state, and a streaming transport. This is out of scope and contradicts the architecture.

**Do this instead:** Use expert prompts to instruct the LLM to call `get_viewport_screenshot` at the appropriate points in its reasoning. The LLM controls the loop; the server only serves requests.

### Anti-Pattern 2: Live Extension Repository Queries

**What people do:** Call `bpy.ops.extensions` to search the live extensions.blender.org repository for suggestions at runtime.

**Why it's wrong:** The `bpy.ops.extensions` API is partially undocumented as of Blender 5.1. It requires `bpy.app.online_access = True`, which users may have disabled. It introduces latency and network dependency into what should be an offline-first tool.

**Do this instead:** Maintain a curated static knowledge base of trusted, stable extensions. Update it in code when new extensions warrant inclusion. Prompt the user to install manually using the Blender extensions browser.

### Anti-Pattern 3: Bypassing the Command Allowlist for Extension Installation

**What people do:** Use the `execute_blender_code` tool to run arbitrary `bpy.ops.extensions.package_install()` calls.

**Why it's wrong:** `execute_blender_code` is already a known security vulnerability. Allowing it to install arbitrary extensions compounds the risk — an adversarial prompt could install malicious code.

**Do this instead:** If extension installation is added, implement it as a registered handler in the dispatcher allowlist with a specific command name (`install_extension`) that accepts only a validated extension ID string (alphanumeric + underscore, max 64 chars). Require the extension to be on an explicit allowlist of known-safe IDs.

### Anti-Pattern 4: Putting Version-Compat Logic in the MCP Server Tier

**What people do:** Add version detection and branching in `src/blend_ai/tools/` to send different commands to different Blender versions.

**Why it's wrong:** The MCP server tier does not have access to `bpy.app.version` — it runs outside Blender as a separate Python process. Version information can only be queried from within Blender.

**Do this instead:** All version-gated code lives in `addon/handlers/`. The MCP server sends a stable command name; the handler internally branches on `bpy.app.version`. Optionally, expose `get_blender_version` as a new query command so the MCP server can log the version for debugging.

---

## Sources

- Blender 5.1 Python API release notes: [https://developer.blender.org/docs/release_notes/5.1/python_api/](https://developer.blender.org/docs/release_notes/5.1/python_api/)
- Blender 5.0 Python API release notes: [https://developer.blender.org/docs/release_notes/5.0/python_api/](https://developer.blender.org/docs/release_notes/5.0/python_api/)
- Blender Extensions Operators API: [https://docs.blender.org/api/current/bpy.ops.extensions.html](https://docs.blender.org/api/current/bpy.ops.extensions.html)
- Blender bpy.types.Addons: [https://docs.blender.org/api/current/bpy.types.Addons.html](https://docs.blender.org/api/current/bpy.types.Addons.html)
- Blender Python API (current): [https://docs.blender.org/api/current/](https://docs.blender.org/api/current/)
- Existing codebase analysis: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONCERNS.md`
- PROJECT.md requirements: `.planning/PROJECT.md`

---

*Architecture research for: Blender MCP Server (AI-to-Blender bridge)*
*Researched: 2026-03-23*
