# Requirements: Blend AI

**Defined:** 2026-03-23
**Core Value:** An LLM using this MCP should produce professional-quality 3D output without the user needing to know Blender — the MCP provides the expertise.

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Blender 5.1 Compatibility

- [x] **COMPAT-01**: All tools work correctly on Blender 5.1 with the EEVEE engine identifier change (`BLENDER_EEVEE_NEXT` → `BLENDER_EEVEE`)
- [x] **COMPAT-02**: Compositor tools use `scene.compositing_node_group` instead of `scene.node_tree`
- [x] **COMPAT-03**: Sculpting tools handle consolidated `brush.stroke_method` enum replacing 8 individual properties
- [x] **COMPAT-04**: Grease pencil tools work with Annotation API split (`bpy.data.annotations`, `AnnotationStroke`)
- [x] **COMPAT-05**: VSE strip tools handle renamed time properties (`frame_final_duration` → `duration`, etc.)
- [x] **COMPAT-06**: All existing tools pass on Python 3.13 without errors

### Blender 5.1 New Features

- [ ] **NEW51-01**: User can create Raycast shader nodes for NPR/toon shading workflows
- [ ] **NEW51-02**: User can create Bone Info geometry nodes for procedural rigging
- [ ] **NEW51-03**: User can create Grid Dilate/Erode geometry nodes for volume operations
- [ ] **NEW51-04**: User can create Mask to SDF compositor nodes
- [ ] **NEW51-05**: User can unwrap UVs using SLIM method for better organic mesh quality
- [ ] **NEW51-06**: User can configure EEVEE Light Path Intensity controls
- [ ] **NEW51-07**: User can add F-curve Gaussian smoothing modifier for animation cleanup

### Visual Feedback

- [ ] **FEED-01**: Viewport screenshot uses fast capture (not full render) and does not trigger the render guard
- [ ] **FEED-02**: After building or modifying objects, the LLM automatically captures a viewport screenshot and critiques the result
- [ ] **FEED-03**: Auto-feedback prompt includes frequency guidance to prevent token runaway (not after every single tool call)
- [x] **FEED-04**: User can run `analyze_mesh_quality()` on any object to get structured JSON report of non-manifold edges, inverted normals, loose vertices, disconnected islands, zero-area faces, and duplicate vertices

### Expert Guidance

- [x] **GUIDE-01**: MCP prompts guide the LLM on quad topology best practices, proper edge flow, and when to use modifiers vs. direct mesh editing
- [x] **GUIDE-02**: MCP prompts include scale reference guidance (real-world dimensions for common objects)
- [x] **GUIDE-03**: MCP prompts include lighting principles (three-point setup, HDRI usage, EEVEE vs. Cycles tradeoffs)
- [ ] **GUIDE-04**: When a task would benefit from a free Blender extension (Bool Tool, LoopTools, Node Wrangler, ND, Mio3 UV), the MCP suggests it proactively before starting
- [ ] **GUIDE-05**: Extension suggestions detect whether the extension is already installed before recommending
- [x] **GUIDE-06**: Workflow prompts guide the LLM through multi-step expert patterns (studio lighting setup, character basemesh, product shot)

### Security & Stability

- [ ] **STAB-01**: Render guard recovers from stuck state automatically (e.g., via `load_post` handler or manual reset tool)
- [ ] **STAB-02**: Stale TCP connections are handled gracefully with proper cleanup and atomic reconnection
- [ ] **STAB-03**: `code_exec` tool is sandboxed — `os`, `subprocess`, `socket`, `importlib` are blocked; only safe `bpy` operations are permitted

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Modeling

- **ADV-01**: User can select specific vertices, edges, or faces by index for granular mesh editing
- **ADV-02**: Multi-step MCP operations can be wrapped in a single undo group for atomic Ctrl+Z

### Workflow Tools

- **WFLOW-01**: High-level workflow tools elevated from prompts to callable MCP tools (e.g., `setup_product_shot()`)
- **WFLOW-02**: Command audit logging for all dispatched operations

### Performance

- **PERF-01**: Configurable per-command timeouts (some operations need >30s, some should fail fast)
- **PERF-02**: Queue depth monitoring with warnings when backlog exceeds threshold

## Out of Scope

| Feature | Reason |
|---------|--------|
| Remote/network access (non-localhost) | Destroys security model; SSH tunneling is the documented alternative |
| Real-time viewport streaming | MCP is request/response; would require protocol change and token costs explode |
| AI-to-3D mesh generation (Meshy, Tripo) | Separate product category; creates dependency/trust issues |
| Multi-user/multi-connection | Blender is single-threaded; concurrent modifications corrupt scene state |
| Auto-install extensions | Bypasses user consent; supply chain attack vector |
| Sculpt brush stroke simulation | Requires viewport/mouse context that cannot be injected from TCP server |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| COMPAT-01 | Phase 1 | Complete |
| COMPAT-02 | Phase 1 | Complete |
| COMPAT-03 | Phase 1 | Complete |
| COMPAT-04 | Phase 1 | Complete |
| COMPAT-05 | Phase 1 | Complete |
| COMPAT-06 | Phase 1 | Complete |
| NEW51-01 | Phase 4 | Pending |
| NEW51-02 | Phase 4 | Pending |
| NEW51-03 | Phase 4 | Pending |
| NEW51-04 | Phase 4 | Pending |
| NEW51-05 | Phase 4 | Pending |
| NEW51-06 | Phase 4 | Pending |
| NEW51-07 | Phase 4 | Pending |
| FEED-01 | Phase 3 | Pending |
| FEED-02 | Phase 3 | Pending |
| FEED-03 | Phase 3 | Pending |
| FEED-04 | Phase 2 | Complete |
| GUIDE-01 | Phase 2 | Complete |
| GUIDE-02 | Phase 2 | Complete |
| GUIDE-03 | Phase 2 | Complete |
| GUIDE-04 | Phase 2 | Pending |
| GUIDE-05 | Phase 2 | Pending |
| GUIDE-06 | Phase 2 | Complete |
| STAB-01 | Phase 2 | Pending |
| STAB-02 | Phase 2 | Pending |
| STAB-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0

---
*Requirements defined: 2026-03-23*
*Last updated: 2026-03-23 after roadmap creation*
