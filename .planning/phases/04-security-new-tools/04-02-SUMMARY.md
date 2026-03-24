---
phase: 04-security-new-tools
plan: 02
subsystem: tools
tags: [blender-5.1, slim, uv-unwrap, shader-nodes, eevee, light-path]
dependency_graph:
  requires: []
  provides: [SLIM unwrap method, ShaderNodeRaycast, set_eevee_light_path]
  affects: [src/blend_ai/tools/uv.py, src/blend_ai/tools/materials.py, src/blend_ai/tools/rendering.py, addon/handlers/rendering.py]
tech_stack:
  added: []
  patterns: ["allowlist expansion for new node types", "optional parameter pattern for light path tool"]
key_files:
  created:
    - tests/test_tools/test_uv_slim.py
    - tests/test_tools/test_new_nodes.py
    - tests/test_tools/test_eevee_light_path.py
  modified:
    - src/blend_ai/tools/uv.py
    - src/blend_ai/tools/materials.py
    - src/blend_ai/tools/rendering.py
    - addon/handlers/rendering.py
decisions:
  - "ShaderNodeRaycast name needs runtime verification on Blender 5.1 — added to allowlist based on naming convention"
  - "EEVEE light path uses optional parameters — only set properties that are explicitly provided"
metrics:
  duration: "~10 minutes"
  completed: "2026-03-24"
  tasks_completed: 2
  files_modified: 7
---

# Phase 04 Plan 02: New 5.1 Features Summary

Added SLIM UV unwrap method, ShaderNodeRaycast to shader node allowlist, and EEVEE light path intensity controls.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | SLIM unwrap + new shader nodes | e2143d2 | src/blend_ai/tools/uv.py, src/blend_ai/tools/materials.py |
| 2 | EEVEE light path intensity | e2143d2 | src/blend_ai/tools/rendering.py, addon/handlers/rendering.py |

## What Was Built

1. **SLIM UV unwrap** — Added "SLIM" to `ALLOWED_UNWRAP_METHODS` in `src/blend_ai/tools/uv.py`. SLIM is a new unwrap algorithm in Blender 5.1 that produces better results for complex meshes.

2. **ShaderNodeRaycast** — Added to `ALLOWED_SHADER_NODE_TYPES` in `src/blend_ai/tools/materials.py` under a new "Blender 5.1+ nodes" comment section.

3. **set_eevee_light_path MCP tool** — New tool in `src/blend_ai/tools/rendering.py` with optional `diffuse_intensity`, `glossy_intensity`, and `transmission_intensity` parameters (range 0.0-10.0). Handler in `addon/handlers/rendering.py` sets `scene.eevee.light_path_*_intensity` properties.

## Test Coverage

16 tests across 3 test files. All pass.

- TestSlimUnwrapMethod (4 tests): SLIM in allowlist, ANGLE_BASED still allowed, CONFORMAL still allowed, validation passes
- TestNew51ShaderNodes (3 tests): Raycast in allowlist, existing nodes present, validation passes
- TestSetEeveeLightPath (9 tests): sends command, diffuse/glossy/transmission params, all params, returns result, error raises, validates range

## Self-Check: PASSED

- FOUND: src/blend_ai/tools/uv.py contains "SLIM"
- FOUND: src/blend_ai/tools/materials.py contains "ShaderNodeRaycast"
- FOUND: src/blend_ai/tools/rendering.py contains "set_eevee_light_path"
- FOUND: addon/handlers/rendering.py contains "handle_set_eevee_light_path"
- COMMIT e2143d2 confirmed
