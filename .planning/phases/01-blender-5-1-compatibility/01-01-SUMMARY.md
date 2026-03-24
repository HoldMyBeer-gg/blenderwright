---
phase: 01-blender-5-1-compatibility
plan: 01
subsystem: rendering, sculpting
tags: [blender-5.1, eevee, render-engine, sculpt-brush, compatibility]

# Dependency graph
requires: []
provides:
  - BLENDER_EEVEE accepted as valid render engine identifier (5.1 rename from BLENDER_EEVEE_NEXT)
  - BLENDER_EEVEE_NEXT rejected as invalid by MCP tools
  - stroke_method is a settable sculpt brush property via tool and handler
  - Codebase audit confirms no VSE deprecated properties or compositor scene.node_tree usage
affects: [rendering, sculpting, scene]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Enum allowlist pattern extended: ALLOWED_STROKE_METHODS validates stroke_method values in both tool and handler"
    - "Audit tests pattern: pathlib-based codebase scan tests catch API regressions at the source level"

key-files:
  created: []
  modified:
    - src/blend_ai/tools/rendering.py
    - src/blend_ai/tools/scene.py
    - src/blend_ai/tools/sculpting.py
    - addon/handlers/sculpting.py
    - tests/test_tools/test_rendering.py
    - tests/test_tools/test_sculpting.py

key-decisions:
  - "BLENDER_EEVEE_NEXT removed entirely from all allowlists — not kept as alias since 5.1 fully dropped it"
  - "stroke_method validation added at both tool layer (MCP) and handler layer (addon) for defense-in-depth"
  - "Audit tests (COMPAT-02, COMPAT-05) confirmed as no-op — codebase was already clean, tests lock this in"

patterns-established:
  - "Pattern: Codebase audit tests using pathlib.rglob scan addon/ and src/ for banned strings"
  - "Pattern: stroke_method enum validation mirrors size/strength/use_frontface validation style"

requirements-completed: [COMPAT-01, COMPAT-02, COMPAT-03, COMPAT-05]

# Metrics
duration: 8min
completed: 2026-03-24
---

# Phase 01 Plan 01: EEVEE Rename and stroke_method Compatibility Summary

**BLENDER_EEVEE replaces BLENDER_EEVEE_NEXT across all MCP tool allowlists, stroke_method added as settable sculpt brush property, and codebase audit tests lock in COMPAT-02/COMPAT-05 cleanliness**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-24T02:00:00Z
- **Completed:** 2026-03-24T02:08:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Renamed EEVEE identifier: BLENDER_EEVEE is now the only accepted engine name; BLENDER_EEVEE_NEXT raises ValidationError
- Added stroke_method as a valid sculpt brush property with ALLOWED_STROKE_METHODS validation in both tool and handler layers
- Added TestCompatAudit tests that scan the codebase to ensure VSE deprecated properties and compositor scene.node_tree never re-enter the codebase

## Task Commits

Each task was committed atomically:

1. **Task 1: Update tests for EEVEE rename and stroke_method, add audit tests** - `4d0a758` (test)
2. **Task 2: Fix EEVEE constant and add stroke_method to sculpting** - `16bad2e` (feat)

_Note: TDD tasks have two commits (test RED then feat GREEN)_

## Files Created/Modified
- `src/blend_ai/tools/rendering.py` - ALLOWED_RENDER_ENGINES changed from BLENDER_EEVEE_NEXT to BLENDER_EEVEE; docstring updated
- `src/blend_ai/tools/scene.py` - ALLOWED_RENDER_ENGINES: removed BLENDER_EEVEE_NEXT, kept only BLENDER_EEVEE
- `src/blend_ai/tools/sculpting.py` - Added "stroke_method" to ALLOWED_BRUSH_PROPERTIES; added ALLOWED_STROKE_METHODS validation branch
- `addon/handlers/sculpting.py` - Added elif prop == "stroke_method" branch with ALLOWED_STROKE_METHODS guard and brush.stroke_method = value
- `tests/test_tools/test_rendering.py` - Inverted test_set_eevee/test_invalid_engine; added TestCompatAudit with VSE and compositor audit tests
- `tests/test_tools/test_sculpting.py` - Added test_set_brush_property_stroke_method

## Decisions Made
- BLENDER_EEVEE_NEXT removed entirely from all allowlists — not kept as alias since Blender 5.1 fully dropped it
- stroke_method validation added at both tool layer (validate_enum against ALLOWED_STROKE_METHODS) and handler layer (same set) for defense-in-depth consistent with existing pattern
- COMPAT-02 and COMPAT-05 confirmed as no-ops (codebase was already clean); added locking tests so regressions are caught immediately

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- COMPAT-01, COMPAT-02, COMPAT-03, COMPAT-05 complete
- COMPAT-04 (Grease Pencil v3) and remaining 5.1 compatibility fixes remain for Plans 02-03
- All 67 rendering and sculpting tests pass

---
*Phase: 01-blender-5-1-compatibility*
*Completed: 2026-03-24*
