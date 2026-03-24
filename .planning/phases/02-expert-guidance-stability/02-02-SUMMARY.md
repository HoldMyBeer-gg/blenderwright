---
phase: 02-expert-guidance-stability
plan: 02
subsystem: prompts
tags: [prompts, expert-guidance, topology, lighting, materials, characters]
dependency_graph:
  requires: []
  provides: [topology_best_practices, scale_reference_guide, lighting_principles, studio_lighting_setup, character_basemesh_workflow, material_workflow_guide]
  affects: [src/blend_ai/prompts/workflows.py]
tech_stack:
  added: []
  patterns: ["@mcp.prompt() identity decorator pattern", "multi-line string concatenation for prompt content"]
key_files:
  created:
    - tests/test_tools/test_prompts.py
  modified:
    - src/blend_ai/prompts/workflows.py
decisions:
  - "HDRI test assertion uses result.upper() with uppercase 'HDRI' (not lowercase 'hdri') to match the acronym in content"
metrics:
  duration: "~10 minutes"
  completed: "2026-03-24T02:32:00Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 02 Plan 02: Expert Prompt Functions Summary

Six expert @mcp.prompt() functions added to workflows.py providing domain-expert guidance on topology, real-world scale, lighting, studio setup, character modeling, and PBR materials.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write failing tests for expert prompts (RED) | 35a991b | tests/test_tools/test_prompts.py |
| 2 | Implement expert prompts in workflows.py (GREEN) | 0f51459 | src/blend_ai/prompts/workflows.py, tests/test_tools/test_prompts.py |

## What Was Built

**6 new expert @mcp.prompt() functions:**

1. `topology_best_practices` — Quad topology preference, edge loop guidance, poles, Mirror/Subsurf/Bevel modifier usage, n-gon cleanup strategies, face density distribution.

2. `scale_reference_guide` — Blender units = meters, metric unit system setup, 8 real-world object dimensions (person 1.75m, door 2.1m, table 0.75m, chair 0.45m, car 4.5m, cup 9cm, smartphone 15cm, ceiling 2.4m), measurement tool tips.

3. `lighting_principles` — Three-point lighting (key/fill/rim energy ratios), HDRI environment setup via World nodes, EEVEE vs Cycles tradeoffs, color temperature guidance, shadow settings.

4. `studio_lighting_setup` — 6-step numbered workflow: backdrop plane, key light (1000W area), fill light (300W), rim light (500W), black world background, render configuration.

5. `character_basemesh_workflow` — 7-step numbered workflow: cube start, Mirror modifier on X axis, edit mode torso shaping, limb extrusion, head placement, Subdivision Surface modifier, joint edge loop refinement.

6. `material_workflow_guide` — Principled BSDF as standard PBR shader, key parameters (metallic, roughness, base color, normal), material recipes table (metals, plastics, glass, skin), texture workflow with correct color space settings, Node Wrangler tip.

## Test Coverage

21 tests across 6 test classes in `tests/test_tools/test_prompts.py`. All pass.

- TestTopologyPrompt (5 tests): non-empty, quad, edge loop/flow, modifier, n-gon
- TestScalePrompt (3 tests): non-empty, meter/cm, 3+ real-world objects
- TestLightingPrompt (4 tests): non-empty, three-point, HDRI, EEVEE+Cycles
- TestStudioLightingWorkflow (3 tests): non-empty, numbered steps, key light
- TestCharacterBasemeshWorkflow (3 tests): non-empty, numbered steps, mirror
- TestMaterialWorkflowGuide (3 tests): non-empty, Principled BSDF, roughness+metallic

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed HDRI test assertion**
- **Found during:** Task 2 GREEN phase
- **Issue:** Test used `assert "hdri" in result.upper()` — checking lowercase "hdri" in an uppercased string always fails since "hdri" != "HDRI".
- **Fix:** Changed assertion to `assert "HDRI" in result.upper()` so the uppercase acronym is found correctly.
- **Files modified:** tests/test_tools/test_prompts.py
- **Commit:** 0f51459

## Known Stubs

None. All prompt functions return full content strings with no placeholders.

## Pre-existing Failures (Out of Scope)

The following test failures existed before this plan's changes and were not introduced by this work:

- `tests/test_addon/test_server.py::TestSOKeepalive::test_accepted_client_has_keepalive` — socket keepalive constant mismatch on macOS (pre-existing)
- `tests/test_tools/test_extensions.py` — `suggest_extensions` not yet importable from scene.py (parallel agent work, IndentationError in scene.py)

These are logged as deferred and out-of-scope per deviation rules.

## Self-Check: PASSED

- `tests/test_tools/test_prompts.py` exists: FOUND
- `src/blend_ai/prompts/workflows.py` has 6 new prompt functions: FOUND (topology_best_practices, scale_reference_guide, lighting_principles, studio_lighting_setup, character_basemesh_workflow, material_workflow_guide)
- Commit 35a991b exists: FOUND
- Commit 0f51459 exists: FOUND
- All 21 prompt tests pass: CONFIRMED
