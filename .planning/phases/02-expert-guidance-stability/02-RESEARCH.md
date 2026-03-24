# Phase 02: Expert Guidance & Stability - Research

**Researched:** 2026-03-23
**Domain:** Blender Python API (bmesh, bpy.app.handlers), MCP prompt patterns, TCP connection stability, addon detection
**Confidence:** HIGH

## Summary

Phase 2 has three distinct work areas: (1) authoring expert MCP prompts and a mesh quality analysis tool, (2) fixing the render guard stuck-state bug and stale TCP connections, and (3) implementing a proactive extension suggestion system. All three are firmly within the existing project architecture — no new external dependencies required.

The mesh quality analysis tool (`analyze_mesh_quality`) is the most technically involved piece. It requires using the `bmesh` module inside the Blender addon handler, iterating over mesh elements with properties like `edge.is_manifold`, `vert.is_wire`, `face.calc_area()`, and `bmesh.ops.find_doubles()`. The render guard fix is a targeted one-liner: register `render_guard.on_render_complete` on `bpy.app.handlers.load_post` (decorated `@persistent`) so a crash that skips `render_complete` is cleared on the next file load. Stale TCP connections are already partially handled (BlenderConnection reconnects once on error); the remaining gap is the server-side client tracking in `addon/server.py`. Extension detection uses `bpy.context.preferences.addons` with the Blender 4.2+ `bl_ext.blender_org.*` namespace.

**Primary recommendation:** Implement in dependency order: (1) render guard fix + TCP cleanup (stability, low risk), (2) mesh quality handler + MCP tool, (3) expert prompts and extension suggestion tool.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GUIDE-01 | MCP prompts guide LLM on quad topology, edge flow, modifiers vs direct editing | New `@mcp.prompt()` functions in `src/blend_ai/prompts/` — content from established 3D best practices |
| GUIDE-02 | MCP prompts include scale reference guidance (real-world dimensions) | New prompt function; static knowledge, no bpy required |
| GUIDE-03 | MCP prompts include lighting principles (three-point, HDRI, EEVEE vs Cycles) | New prompt function in `prompts/workflows.py` or new module |
| GUIDE-04 | MCP suggests beneficial free extensions before starting a task | New `@mcp.tool()` wrapping static knowledge base + addon detection |
| GUIDE-05 | Extension suggestions detect already-installed extensions before recommending | `bpy.context.preferences.addons` check via handler command; returns installed set |
| GUIDE-06 | Workflow prompts guide LLM through studio lighting, character basemesh, product shot | Additional `@mcp.prompt()` functions expanding existing `workflows.py` |
| FEED-04 | `analyze_mesh_quality()` returns structured JSON covering 6 mesh defect categories | New handler using `bmesh` + new MCP tool + new validator |
| STAB-01 | Render guard recovers automatically on `load_post` or via reset tool | `@persistent` `load_post` handler + `reset_render_guard` command |
| STAB-02 | Stale TCP connections cleaned up without Blender restart | Socket keepalive option + explicit client removal on error in `addon/server.py` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| bmesh (bpy built-in) | Blender 4.0+ / 5.1 | Mesh topology analysis in handler | Only way to inspect per-element mesh data inside Blender; part of official bpy API |
| bpy.app.handlers | Blender 4.0+ / 5.1 | Application event callbacks | Official mechanism for load_post, render_pre/complete/cancel |
| bpy.app.handlers.persistent | Blender 4.0+ | Keep handler across file loads | Standard decorator for addon handlers that must survive file opens |
| mcp (FastMCP) | 1.26.0 | `@mcp.prompt()` decorator for guidance content | Already in use; prompts are first-class MCP primitives |
| socket (stdlib) | Python 3.10+ | TCP keepalive socket option | stdlib; no new dependency |

### No New External Dependencies
All work in Phase 2 uses APIs already present in the project stack. The `bmesh` module is available in all Blender 4.0+ Python environments (it's part of Blender's bundled Python). No pip packages need to be added.

**Version verification:** No packages to install. All libraries are either stdlib or embedded in Blender/mcp.

## Architecture Patterns

### Recommended Project Structure (additions)

```
src/blend_ai/
├── prompts/
│   └── workflows.py          # Extend with topology, scale, lighting, advanced workflow prompts
├── tools/
│   └── mesh_quality.py       # NEW: analyze_mesh_quality() MCP tool
│   └── scene.py              # Add get_installed_extensions() or suggest_extensions()
addon/
├── handlers/
│   └── mesh_quality.py       # NEW: handle_analyze_mesh_quality() using bmesh
│   └── scene.py              # Add handle_get_installed_extensions()
├── render_guard.py           # Add reset() method + load_post registration
tests/
├── test_tools/
│   └── test_mesh_quality.py  # NEW: unit tests for MCP tool
├── test_addon/test_handlers/
│   └── test_mesh_quality_handler.py  # NEW: handler unit tests with mock bpy
```

### Pattern 1: MCP Prompt Authoring

**What:** `@mcp.prompt()` decorated functions in `src/blend_ai/prompts/` that return plain-text expert guidance strings. Consumed by the MCP client before it starts tasks.

**When to use:** Any guidance that is static knowledge, not requiring Blender state.

**Example (extending `workflows.py`):**
```python
# Source: existing src/blend_ai/prompts/workflows.py pattern
@mcp.prompt()
def topology_best_practices() -> str:
    """Expert guide on quad topology and edge flow for modeling tasks."""
    return (
        "## Quad Topology Best Practices\n\n"
        "- **Always prefer quads** over triangles or n-gons for subdivision-ready meshes...\n"
        "- **Edge loops** should follow natural contours of the object...\n"
        "- **Avoid poles** (vertices with >5 edges) in high-curvature areas...\n"
        "- Use modifiers (Mirror, Subsurf, Bevel) instead of manual loop-cuts where possible...\n"
    )
```

### Pattern 2: BMesh Mesh Quality Analysis (Handler)

**What:** A handler that opens a BMesh from an existing mesh object, iterates elements to detect 6 defect categories, and returns a structured JSON report.

**When to use:** `analyze_mesh_quality` tool call with an object name.

**Key BMesh API:**
```python
# Source: docs.blender.org/api/blender_python_api_2_77_0/bmesh.types.html
import bpy
import bmesh

def handle_analyze_mesh_quality(params):
    obj = bpy.data.objects.get(params["object_name"])
    # Must use evaluated depsgraph for modifier-applied state, or original for raw mesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    # Non-manifold edges: edges where is_manifold is False and is_wire is False
    non_manifold = [e.index for e in bm.edges if not e.is_manifold and not e.is_wire]

    # Loose vertices: verts with no linked faces (is_wire=True with no faces)
    loose_verts = [v.index for v in bm.verts if not v.link_faces]

    # Zero-area faces: faces where calc_area() returns 0.0 (or below threshold)
    AREA_EPSILON = 1e-8
    zero_area = [f.index for f in bm.faces if f.calc_area() < AREA_EPSILON]

    # Inverted normals: detected via face normal vs centroid direction heuristic
    # (full analysis requires comparing adjacent face normals — use is_convex on edges)

    # Duplicate vertices: bmesh.ops.find_doubles
    result = bmesh.ops.find_doubles(bm, verts=bm.verts, dist=1e-4)
    duplicate_count = len(result["targetmap"])

    bm.free()
    return {
        "non_manifold_edge_count": len(non_manifold),
        "non_manifold_edge_indices": non_manifold[:50],  # cap to 50
        ...
    }
```

**BMesh element properties used:**
- `edge.is_manifold` (bool) — True when edge has exactly 2 linked faces
- `edge.is_wire` (bool) — True when edge has no linked faces
- `vert.is_wire` (bool) — True when vertex not connected to any face
- `vert.link_faces` (sequence) — faces connected to this vertex
- `face.calc_area()` (float) — computed face area
- `face.normal` (Vector) — computed face normal
- `bmesh.ops.find_doubles(bm, verts, dist)` — returns `{"targetmap": dict}` mapping dup→target

### Pattern 3: Render Guard Recovery via `load_post`

**What:** Register `render_guard.on_render_complete` on `bpy.app.handlers.load_post` with the `@persistent` decorator so that if Blender crashes mid-render (skipping `render_complete`/`render_cancel`), the guard is cleared when the next file loads.

**When to use:** Addon `register()` in `addon/__init__.py`.

**Example:**
```python
# Source: docs.blender.org/api/3.1/bpy.app.handlers.html
from bpy.app.handlers import persistent
from .render_guard import render_guard

@persistent
def _clear_render_guard_on_load(filepath):
    """Clear render guard when any file loads — recovers from crashed renders."""
    render_guard.on_render_complete(None)

# In register():
bpy.app.handlers.load_post.append(_clear_render_guard_on_load)
# In unregister():
bpy.app.handlers.load_post.remove(_clear_render_guard_on_load)
```

Additionally, expose a `reset_render_guard` command via dispatcher so the MCP can reset it without a file load.

### Pattern 4: Extension Detection

**What:** Query `bpy.context.preferences.addons` dict to check if an extension is enabled. In Blender 4.2+, bundled extensions use the `bl_ext.blender_org.*` namespace; older/legacy addons use their bare module name.

**Confirmed module keys (Blender 4.2+):**

| Extension | Legacy key (≤4.1) | Extensions key (4.2+) |
|-----------|-------------------|----------------------|
| Bool Tool | `object_boolean_tools` | `bl_ext.blender_org.object_boolean_tools` |
| LoopTools | `mesh_looptools` | `bl_ext.blender_org.looptools` |
| Node Wrangler | `node_wrangler` | `bl_ext.blender_org.node_wrangler` |

**Detection strategy:** Check both keys (legacy and new namespace) for forward/backward compat.

```python
# Source: b3d.interplanety.org/en/how-to-programmatically-check-if-the-blender-add-on-is-registered/
def _is_addon_installed(module_name: str, bl_ext_name: str | None = None) -> bool:
    """Check if addon is enabled, handling both legacy and 4.2+ extension names."""
    prefs = bpy.context.preferences.addons
    if module_name in prefs:
        return True
    if bl_ext_name and bl_ext_name in prefs:
        return True
    return False
```

### Pattern 5: TCP Keepalive for Stale Connection Detection

**What:** Set `SO_KEEPALIVE` on the server-side accepted socket so the OS can detect half-open TCP connections (client process died without FIN).

**When to use:** In `addon/server.py` `_accept_loop()` when accepting each new client.

**Example:**
```python
# Source: Python stdlib socket documentation
client, addr = self._server_socket.accept()
# Enable TCP keepalive to detect dead clients
client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
client.settimeout(30.0)
```

On macOS/Linux, the OS will send keepalive probes and close the socket if the remote doesn't respond, triggering an `OSError` in `_recv_message` which is already caught and causes clean client removal. This requires no new threading.

The client-side (`src/blend_ai/connection.py`) already reconnects on `OSError`. The server-side cleanup in `_handle_client` already removes the client from `_clients` in its `finally` block. No structural changes needed — just the socket option.

### Anti-Patterns to Avoid

- **Modifying mesh data directly instead of using bmesh**: `obj.data.vertices` doesn't expose manifold/topology data — must use bmesh.
- **Not calling `bm.free()`**: BMesh contexts are expensive; always free in a `finally` block or use `with bmesh.new() as bm:` context manager.
- **Checking only legacy addon names in 4.2+**: Extensions platform uses `bl_ext.*` namespace. Must check both.
- **Returning all non-manifold indices for large meshes**: Cap response to 50–100 indices to avoid overwhelming JSON responses over TCP. Return counts always, indices only as samples.
- **Registering `load_post` without `@persistent`**: Without the decorator, the handler is removed when a file loads — defeating the purpose.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Duplicate vertex detection | Custom KD-tree O(n²) distance check | `bmesh.ops.find_doubles(bm, verts, dist)` | Blender's internal algorithm handles precision correctly; built-in |
| Non-manifold edge detection | Custom face-count-per-edge logic | `edge.is_manifold` property | Direct from Blender's topology data; correct by definition |
| Render guard persistence | Custom file watcher or polling loop | `bpy.app.handlers.load_post` + `@persistent` | Official mechanism; already used for render_pre/complete |
| Extension name lookup | Hard-coded static table updated manually | Query `bpy.context.preferences.addons` at runtime | Handles any extensions the user has installed, not just the listed 5 |
| TCP dead-peer detection | Custom heartbeat ping-pong protocol | `SO_KEEPALIVE` socket option | OS handles it; no protocol overhead; already works with existing OSError handling |

**Key insight:** Blender's bmesh API exposes exactly the topology properties needed for mesh quality analysis as first-class element properties — the analysis logic is 30–50 lines, not a complex algorithm.

## Runtime State Inventory

> This is a feature-addition phase (not a rename/refactor). Omit — no runtime state migration required.

## Common Pitfalls

### Pitfall 1: BMesh from Object in Edit Mode
**What goes wrong:** Calling `bm.from_mesh(obj.data)` while the object is in Edit Mode returns stale data because the mesh isn't flushed back from BMesh to the object data yet.
**Why it happens:** Blender defers mesh updates until you leave Edit Mode.
**How to avoid:** In the handler, always call `bpy.ops.object.mode_set(mode="OBJECT")` first (using the existing `_ensure_object_mode()` helper from `mesh_editing.py`).
**Warning signs:** Analysis returns 0 elements on a mesh you just edited.

### Pitfall 2: Render Guard `@persistent` Missing
**What goes wrong:** The `load_post` handler that clears the render guard is silently removed when any .blend file is opened.
**Why it happens:** By default, `bpy.app.handlers` lists are cleared on file load.
**How to avoid:** Always decorate the function with `@bpy.app.handlers.persistent` (or equivalently import `from bpy.app.handlers import persistent` and use `@persistent`).
**Warning signs:** Render guard doesn't reset after loading a new file.

### Pitfall 3: Extension Namespace Change in Blender 4.2
**What goes wrong:** `"object_boolean_tools" in bpy.context.preferences.addons` returns False on 4.2+ even when Bool Tool is installed, because the key changed to `bl_ext.blender_org.object_boolean_tools`.
**Why it happens:** Blender 4.2 moved bundled add-ons to the extensions platform with namespaced identifiers.
**How to avoid:** Check both the legacy key and the `bl_ext.blender_org.*` key; return True if either matches.
**Warning signs:** Extension suggestions are shown even when the extension is enabled.

### Pitfall 4: BMesh `find_doubles` Returns a `targetmap` Dict, Not a List
**What goes wrong:** Code iterates `result` instead of `result["targetmap"]`, getting unexpected behavior.
**Why it happens:** `bmesh.ops` return a dict of named output slots.
**How to avoid:** Always access the named output: `result = bmesh.ops.find_doubles(bm, verts=bm.verts, dist=1e-4); dups = result["targetmap"]`.
**Warning signs:** `TypeError: 'BMOpSlot' object is not iterable`.

### Pitfall 5: `suggest_extensions` Requires Blender Connection
**What goes wrong:** The extension suggestion feature (GUIDE-04, GUIDE-05) needs to detect installed extensions. This requires a round-trip to Blender, not just static data on the MCP server side.
**Why it happens:** `bpy.context.preferences.addons` only exists inside Blender; the MCP server is a separate process.
**How to avoid:** Implement `get_installed_extensions` as a handler command that queries `bpy.context.preferences.addons` and returns the list to the MCP tool. The MCP tool then computes recommendations from the static knowledge base minus installed extensions.

### Pitfall 6: TCP Keepalive on macOS
**What goes wrong:** `SO_KEEPALIVE` doesn't send probes immediately; by default macOS uses a 2-hour idle interval.
**Why it happens:** Default system keepalive interval is 7200 seconds (2 hours) on macOS.
**How to avoid:** This is acceptable for the use case — the goal is to detect peers that died mid-connection, not to timeout idle connections. The existing 30-second socket timeout on client sockets already handles most stale connection scenarios. Keepalive adds recovery for connections that appear active at the OS level but have a dead remote. The current error handling (`OSError` → client removal) is already correct.

## Code Examples

Verified patterns from official sources and codebase:

### BMesh mesh quality analysis skeleton (handler)
```python
# Source: bmesh.types documented at docs.blender.org/api/blender_python_api_2_77_0/bmesh.types.html
import bpy
import bmesh

def handle_analyze_mesh_quality(params):
    obj = bpy.data.objects.get(params["object_name"])
    if obj is None:
        raise ValueError(f"Object '{params['object_name']}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{params['object_name']}' is not a mesh")

    # Ensure object mode so mesh data is current
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        AREA_EPSILON = 1e-8
        VERT_DIST = 1e-4

        non_manifold_edges = [e.index for e in bm.edges if not e.is_manifold and not e.is_wire]
        wire_edges = [e.index for e in bm.edges if e.is_wire]
        loose_verts = [v.index for v in bm.verts if not v.link_faces]
        zero_area_faces = [f.index for f in bm.faces if f.calc_area() < AREA_EPSILON]

        dup_result = bmesh.ops.find_doubles(bm, verts=list(bm.verts), dist=VERT_DIST)
        duplicate_vert_count = len(dup_result["targetmap"])

        # Inverted normals: recalculate to see if any changed (expensive; report count only)
        # Approach: compare existing normals vs recalculated — but this is destructive.
        # Safer: report non-manifold as proxy, document limitation.

        return {
            "object": obj.name,
            "vertex_count": len(bm.verts),
            "edge_count": len(bm.edges),
            "face_count": len(bm.faces),
            "non_manifold_edge_count": len(non_manifold_edges),
            "non_manifold_edge_indices": non_manifold_edges[:50],
            "wire_edge_count": len(wire_edges),
            "loose_vertex_count": len(loose_verts),
            "loose_vertex_indices": loose_verts[:50],
            "zero_area_face_count": len(zero_area_faces),
            "zero_area_face_indices": zero_area_faces[:50],
            "duplicate_vertex_count": duplicate_vert_count,
            "issues_found": any([
                non_manifold_edges, loose_verts, zero_area_faces, duplicate_vert_count
            ]),
        }
    finally:
        bm.free()
```

### Inverted normals detection note
The requirement includes inverted normals detection. The cleanest non-destructive approach is to compare each face's stored normal against the normal computed from vertex positions using the right-hand rule. In practice, this is approximately `face.normal` vs `face.calc_normal()`. However, `face.normal` IS the computed normal — there is no stored vs computed distinction in bmesh. The correct approach for "inverted normals" in Blender context is: normals that point inward (opposite to what a closed solid should have). This requires comparing against neighboring faces or against a reference (e.g., the face centroid relative to the object center). A practical approximation: count faces where `face.normal.dot(face.calc_center_median() - obj_center) < 0`. This is documented as a heuristic, not a definitive test. The planner should note this constraint.

### Render guard load_post recovery
```python
# Source: docs.blender.org/api/3.1/bpy.app.handlers.html
from bpy.app.handlers import persistent

@persistent
def _clear_render_guard_on_load(filepath):
    render_guard.on_render_complete(None)

# register():
bpy.app.handlers.load_post.append(_clear_render_guard_on_load)

# unregister():
if _clear_render_guard_on_load in bpy.app.handlers.load_post:
    bpy.app.handlers.load_post.remove(_clear_render_guard_on_load)
```

### Extension detection handler
```python
# Source: b3d.interplanety.org — check bpy.context.preferences.addons
KNOWN_EXTENSIONS = {
    "bool_tool": {
        "legacy_key": "object_boolean_tools",
        "ext_key": "bl_ext.blender_org.object_boolean_tools",
        "name": "Bool Tool",
        "use_case": "Boolean operations (union, difference, intersect)",
    },
    "looptools": {
        "legacy_key": "mesh_looptools",
        "ext_key": "bl_ext.blender_org.looptools",
        "name": "LoopTools",
        "use_case": "Advanced loop editing (relax, space, circle, curve)",
    },
    "node_wrangler": {
        "legacy_key": "node_wrangler",
        "ext_key": "bl_ext.blender_org.node_wrangler",
        "name": "Node Wrangler",
        "use_case": "Shader/geometry node editing shortcuts",
    },
}

def handle_get_installed_extensions(params):
    installed = []
    prefs = bpy.context.preferences.addons
    for key, info in KNOWN_EXTENSIONS.items():
        if info["legacy_key"] in prefs or info["ext_key"] in prefs:
            installed.append(key)
    return {"installed": installed}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bundled add-ons (object_boolean_tools etc.) | Extensions platform (bl_ext.blender_org.*) | Blender 4.2 (2024) | Detection must check both namespaces |
| `bpy.ops.render.opengl` for screenshots | Same (but render guard interacts) | Ongoing | Phase 3 concern; not Phase 2 |
| `render_cancel` to clear stuck guard | `load_post` + `render_cancel` + `render_complete` | Phase 2 fix | Crash recovery now works |

**Deprecated/outdated:**
- Legacy addon keys (`mesh_looptools`, `object_boolean_tools`): Still work in Blender ≤4.1 but are superseded by `bl_ext.blender_org.*` in 4.2+. Must check both for backward compat with Blender 4.x prior to 4.2.

## Open Questions

1. **Inverted normals detection approach**
   - What we know: `face.normal` is the computed normal; bmesh has no "stored vs computed" distinction unlike bpy.data mesh normals
   - What's unclear: The most reliable non-destructive test for "inverted" normals in a closed solid (without running `recalc_face_normals` which modifies the mesh)
   - Recommendation: Implement as "inside-out face heuristic" (dot product of normal vs centroid-to-origin vector), document the limitation in the tool docstring. For destructive analysis, offer a separate "fix" tool in a later phase.

2. **Extension key for ND (N-panel), Mio3 UV**
   - What we know: The REQUIREMENTS.md mentions ND and Mio3 UV as potential extension suggestions (GUIDE-04)
   - What's unclear: Their exact `bl_ext` keys — these are third-party extensions not on extensions.blender.org main registry
   - Recommendation: Scope Phase 2 extension suggestions to the three verifiable extensions (Bool Tool, LoopTools, Node Wrangler). GUIDE-04 says "similar free extensions" — not an exhaustive list. ND and Mio3 UV can be added in a follow-up.

3. **`suggest_extensions` as tool vs prompt**
   - What we know: Extension suggestions should be proactive (GUIDE-04), and detection requires a Blender round-trip
   - What's unclear: Whether this is better as an `@mcp.tool()` the LLM calls explicitly, or a resource the LLM checks on startup
   - Recommendation: Implement as `@mcp.tool()` named `suggest_extensions(task_description: str)` — the LLM describes its planned task and gets back a filtered list of helpful extensions not yet installed. More flexible than a resource.

## Environment Availability

> This phase is code/config changes only — no new external tool dependencies. The only runtime dependency is Blender 4.0+ with the addon loaded, which was verified working in Phase 1.

Step 2.6: SKIPPED (no new external dependencies — bmesh is part of Blender's embedded Python; all other APIs are stdlib or existing project stack)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4.4 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_tools/test_mesh_quality.py tests/test_addon/test_handlers/test_mesh_quality_handler.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GUIDE-01 | topology_best_practices() prompt returns non-empty string | unit | `uv run pytest tests/test_tools/test_prompts.py::TestTopologyPrompt -x` | Wave 0 |
| GUIDE-02 | scale_reference_guide() prompt returns string with unit examples | unit | `uv run pytest tests/test_tools/test_prompts.py::TestScalePrompt -x` | Wave 0 |
| GUIDE-03 | lighting_principles() prompt returns string covering three-point/HDRI | unit | `uv run pytest tests/test_tools/test_prompts.py::TestLightingPrompt -x` | Wave 0 |
| GUIDE-04 | suggest_extensions() returns at least Bool Tool, LoopTools, Node Wrangler for relevant tasks | unit | `uv run pytest tests/test_tools/test_extensions.py -x` | Wave 0 |
| GUIDE-05 | suggest_extensions() skips extensions flagged as installed by handler | unit | `uv run pytest tests/test_tools/test_extensions.py::TestInstalledSkipped -x` | Wave 0 |
| GUIDE-06 | studio_lighting_setup/character_basemesh prompts return multi-step instructions | unit | `uv run pytest tests/test_tools/test_prompts.py::TestWorkflowPrompts -x` | Wave 0 |
| FEED-04 | analyze_mesh_quality() sends correct command; handler returns all 6 defect categories | unit | `uv run pytest tests/test_tools/test_mesh_quality.py tests/test_addon/test_handlers/test_mesh_quality_handler.py -x` | Wave 0 |
| STAB-01 | _clear_render_guard_on_load clears render guard; reset_render_guard command works | unit | `uv run pytest tests/test_addon/test_render_guard.py -x` | Partial (test_render_guard.py exists) |
| STAB-02 | Client sockets have SO_KEEPALIVE set; dead clients removed from _clients list on OSError | unit | `uv run pytest tests/test_addon/test_server.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** Quick run on the affected test file(s)
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_tools/test_mesh_quality.py` — covers FEED-04 (MCP tool layer)
- [ ] `tests/test_addon/test_handlers/test_mesh_quality_handler.py` — covers FEED-04 (handler layer with mock bpy/bmesh)
- [ ] `tests/test_tools/test_prompts.py` — covers GUIDE-01, GUIDE-02, GUIDE-03, GUIDE-06
- [ ] `tests/test_tools/test_extensions.py` — covers GUIDE-04, GUIDE-05
- [ ] `tests/test_addon/test_server.py` — covers STAB-02 (socket option verification)
- [ ] Extend `tests/test_addon/test_render_guard.py` — add load_post recovery test for STAB-01

## Project Constraints (from CLAUDE.md)

- **Thread model**: All `bpy` / `bmesh` calls in handlers run on main thread via `thread_safety.execute_on_main_thread`. The `bmesh` analysis in `handle_analyze_mesh_quality` follows this same pattern — no direct bpy calls from background threads.
- **Security**: No arbitrary code execution. `analyze_mesh_quality` reads mesh data only — no writes, no operator calls that modify the scene (exception: `mode_set` to OBJECT is safe and follows existing handler pattern).
- **MCP protocol**: Stateless. Extension suggestion logic must query Blender for installed extensions each time (no cached state on MCP server side).
- **Test-first**: Write test files (Wave 0 gaps above) BEFORE implementing the handlers and tools.
- **Blender API**: Use only `bmesh`, `bpy.data`, `bpy.context`, `bpy.app.handlers` — all official public API. No `bpy.ops` for analysis (read-only alternatives preferred).
- **Naming conventions**: New tool = `analyze_mesh_quality`, new handler = `handle_analyze_mesh_quality`, new suggestion tool = `suggest_extensions`, new handler = `handle_get_installed_extensions`. Constants like `KNOWN_EXTENSIONS`, `AREA_EPSILON`.
- **Error handling**: Validators raise `ValidationError`; handler exceptions wrapped by dispatcher; RuntimeError surfaced to MCP client.
- **GSD workflow**: All edits go through GSD workflow (gsd:execute-phase).

## Sources

### Primary (HIGH confidence)
- `docs.blender.org/api/blender_python_api_2_77_0/bmesh.types.html` — BMVert, BMEdge, BMFace properties: `is_manifold`, `is_wire`, `link_faces`, `calc_area()`, `normal`
- `docs.blender.org/api/3.1/bpy.app.handlers.html` — `load_post`, `@persistent` decorator, registration patterns
- Existing codebase (`addon/render_guard.py`, `addon/server.py`, `src/blend_ai/prompts/workflows.py`) — architectural patterns confirmed by direct read

### Secondary (MEDIUM confidence)
- `b3d.interplanety.org/en/how-to-programmatically-check-if-the-blender-add-on-is-registered/` — `bpy.context.preferences.addons` dict check pattern (verified against Blender API structure)
- WebSearch result confirming `bl_ext.blender_org.looptools` is the 4.2+ key (from Blender Projects issue #124457 title)
- WebSearch result confirming Bool Tool extension project is at `projects.blender.org/extensions/object_boolean_tools` (legacy module name = `object_boolean_tools`)

### Tertiary (LOW confidence)
- Extension module names for Bool Tool (`bl_ext.blender_org.object_boolean_tools`) and Node Wrangler (`bl_ext.blender_org.node_wrangler`) — inferred from LoopTools confirmed key + naming pattern. Should be verified by checking an actual Blender 4.2+ installation's `bpy.context.preferences.addons` keys during implementation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are in the existing project or official Blender API
- BMesh API (FEED-04): HIGH — element properties documented in official API; pattern well-established
- Render guard fix (STAB-01): HIGH — `@persistent` + `load_post` is the canonical Blender solution
- TCP stability (STAB-02): HIGH — `SO_KEEPALIVE` + existing OSError handling is correct; minor change
- Prompt content (GUIDE-01/02/03/06): HIGH — static content, no technical unknowns
- Extension detection keys (GUIDE-04/05): MEDIUM — LoopTools key confirmed, Bool Tool + Node Wrangler inferred from pattern; needs runtime verification
- Inverted normals implementation: MEDIUM — heuristic approach documented; exact method TBD by implementer

**Research date:** 2026-03-23
**Valid until:** 2026-09-23 (stable Blender API; 6 months before re-verification needed)
