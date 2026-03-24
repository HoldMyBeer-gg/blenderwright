# Roadmap: Blend AI

## Overview

This milestone upgrades blend-ai from v0.2.0 to full Blender 5.1 compatibility, adds visual feedback intelligence, hardens security, and layers expert LLM guidance on top of the existing 161-tool foundation. The four phases follow a strict dependency order: fix what's broken, add intelligence, enable visual feedback, then expand new capabilities.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Blender 5.1 Compatibility** - Fix all breaking API changes so existing tools work on Blender 5.1 / Python 3.13 (completed 2026-03-24)
- [ ] **Phase 2: Expert Guidance & Stability** - Add expert MCP prompts, mesh quality validation, and fix render guard / connection stability issues
- [ ] **Phase 3: Visual Feedback Loop** - Ship fast viewport screenshot and auto-critique so the LLM can see what it built
- [ ] **Phase 4: Extension Suggestions, Security & New 5.1 Tools** - Harden code_exec, add proactive extension suggestions, expose Blender 5.1-only nodes

## Phase Details

### Phase 1: Blender 5.1 Compatibility
**Goal**: All existing tools work correctly on Blender 5.1 with Python 3.13, with CI verifying the fixed handlers
**Depends on**: Nothing (first phase)
**Requirements**: COMPAT-01, COMPAT-02, COMPAT-03, COMPAT-04, COMPAT-05, COMPAT-06
**Success Criteria** (what must be TRUE):
  1. A user on Blender 5.1 can start the server, connect an MCP client, and render with EEVEE without errors
  2. Compositor node tools function against `scene.compositing_node_group` on 5.1 without AttributeError
  3. Sculpt tools accept brush input without referencing removed 5.0 individual properties
  4. Grease Pencil annotation tools work against the split Annotation API on 5.1
  5. CI runs the full handler test suite against `bpy==5.1.0` on Python 3.13 with zero failures
**Plans:** 3/3 plans complete
Plans:
- [x] 01-01-PLAN.md — EEVEE rename, sculpt stroke_method, compositor/VSE audits (COMPAT-01, COMPAT-02, COMPAT-03, COMPAT-05)
- [x] 01-02-PLAN.md — Grease Pencil to Annotation API rewrite (COMPAT-04)
- [x] 01-03-PLAN.md — Handler tests and bpy 5.1 CI workflow (COMPAT-06)

### Phase 2: Expert Guidance & Stability
**Goal**: The LLM receives expert modeling/lighting/material guidance via MCP prompts, can run structured mesh quality checks, and the server no longer gets stuck from render guard or stale connections
**Depends on**: Phase 1
**Requirements**: GUIDE-01, GUIDE-02, GUIDE-03, GUIDE-04, GUIDE-05, GUIDE-06, FEED-04, STAB-01, STAB-02
**Success Criteria** (what must be TRUE):
  1. An LLM using the server receives topology, lighting, and material guidance before starting a modeling task
  2. User can call `analyze_mesh_quality()` on any object and receive a structured JSON report covering non-manifold edges, inverted normals, loose vertices, zero-area faces, and duplicate vertices
  3. When a task would benefit from Bool Tool, LoopTools, Node Wrangler, or similar free extensions, the MCP suggests them before starting (and skips suggestions for already-installed extensions)
  4. A render that crashes mid-way no longer leaves the render guard permanently stuck — the server recovers on `load_post` or via a reset tool
  5. Stale TCP connections are cleaned up automatically without requiring a Blender restart
**Plans:** 4/4 plans complete
Plans:
- [x] 02-01-PLAN.md — Render guard recovery and TCP stale connection cleanup (STAB-01, STAB-02)
- [x] 02-02-PLAN.md — Expert MCP prompts for topology, scale, lighting, and workflows (GUIDE-01, GUIDE-02, GUIDE-03, GUIDE-06)
- [x] 02-03-PLAN.md — Mesh quality analysis tool and handler (FEED-04)
- [x] 02-04-PLAN.md — Extension suggestion system with installed detection (GUIDE-04, GUIDE-05)

### Phase 3: Visual Feedback Loop
**Goal**: The LLM can capture the current viewport state in under 500ms without triggering render cycles, and automatically critiques what it builds
**Depends on**: Phase 2
**Requirements**: FEED-01, FEED-02, FEED-03
**Success Criteria** (what must be TRUE):
  1. Calling `get_viewport_screenshot(mode="fast")` returns a viewport image in under 500ms and does not trigger the render guard
  2. After building or modifying an object, the LLM automatically captures a screenshot and reports what it sees (good topology, issues, next steps)
  3. The auto-screenshot prompt prevents token runaway by specifying that screenshots fire only after structural changes (add/delete/boolean/apply), not after metadata-only changes
**Plans**: 2/2 plans complete
Plans:
- [x] 03-01-PLAN.md — Fast viewport capture using render.opengl + mode parameter (FEED-01)
- [x] 03-02-PLAN.md — Auto-critique prompt with token-safety guidelines (FEED-02, FEED-03)

### Phase 4: Extension Suggestions, Security & New 5.1 Tools
**Goal**: `code_exec` is sandboxed against RCE, the extension suggestion system detects installed extensions before recommending, and all Blender 5.1-exclusive nodes and tools are accessible via MCP
**Depends on**: Phase 3
**Requirements**: STAB-03, NEW51-01, NEW51-02, NEW51-03, NEW51-04, NEW51-05, NEW51-06, NEW51-07
**Success Criteria** (what must be TRUE):
  1. Calling `code_exec` with `import os` or `import subprocess` raises a sandboxing error, not a Python exception from inside Blender
  2. User can create Raycast shader nodes, Bone Info geometry nodes, Grid Dilate/Erode nodes, and Mask to SDF compositor nodes via MCP tools
  3. User can unwrap UVs using the SLIM method and configure EEVEE Light Path Intensity controls via MCP tools
  4. The N-panel includes an "unsafe mode" toggle for `code_exec` that defaults to OFF and persists across sessions
**Plans**: 2/2 plans complete
Plans:
- [x] 04-01-PLAN.md — Code exec sandboxing with import blocking (STAB-03, NEW51-07)
- [x] 04-02-PLAN.md — SLIM UV unwrap, new 5.1 shader nodes, EEVEE light path intensity (NEW51-01, NEW51-05, NEW51-06)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Blender 5.1 Compatibility | 3/3 | Complete   | 2026-03-24 |
| 2. Expert Guidance & Stability | 4/4 | Complete   | 2026-03-24 |
| 3. Visual Feedback Loop | 2/2 | Complete | 2026-03-24 |
| 4. Extension Suggestions, Security & New 5.1 Tools | 2/2 | Complete | 2026-03-24 |
