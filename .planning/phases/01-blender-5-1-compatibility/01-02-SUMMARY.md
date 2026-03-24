---
phase: 01-blender-5-1-compatibility
plan: 02
subsystem: api
tags: [blender, gpencil, annotation, bpy, compatibility, blender-5-1]

# Dependency graph
requires: []
provides:
  - "Annotation-based handler for bpy.data.annotations API (COMPAT-04)"
  - "MCP tools for creating, layering, and stroking annotation data blocks"
  - "Removal of all bpy.ops.object.gpencil_add and obj.type == GPENCIL patterns"
affects: [03-blender-5-1-compatibility, 04-blender-5-1-compatibility]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Annotation API: bpy.data.annotations.new() creates viewport overlay data blocks (not 3D objects)"
    - "No location param: annotations are not positioned in 3D space"
    - "No .strength on AnnotationStroke: only .co and .pressure per point"
    - "Layer frame access: layer.frames.new(frame_current) when no frames exist"

key-files:
  created: []
  modified:
    - addon/handlers/gpencil.py
    - src/blend_ai/tools/gpencil.py
    - tests/test_addon/test_handlers/test_gpencil_handler.py

key-decisions:
  - "Annotation API targets viewport overlays not 3D drawing objects — bpy.data.annotations, not bpy.data.objects"
  - "AnnotationStroke has no .strength property — removed from handler loop and MCP tool signature"
  - "create_annotation has no location parameter — annotations are not positioned 3D objects"

patterns-established:
  - "Annotation pattern: bpy.data.annotations.new(name) for creation; annotations.get(name) for lookup"
  - "Layer pattern: ann.layers.new(name=layer_name) returns layer; layer.info gives display name"
  - "Stroke pattern: frame.strokes.new(); stroke.points.add(n); set .co and .pressure per point only"

requirements-completed: [COMPAT-04]

# Metrics
duration: 8min
completed: 2026-03-24
---

# Phase 01 Plan 02: GPencil Annotation API Rewrite Summary

**Grease Pencil handler and MCP tools rewritten to use bpy.data.annotations API exclusively, removing all removed Blender 5.x GPencil object patterns**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-24T01:49:00Z
- **Completed:** 2026-03-24T01:57:45Z
- **Tasks:** 1 (Task 1 was pre-completed in commit 275d82f; Task 2 executed here)
- **Files modified:** 3

## Accomplishments
- Handler fully rewritten: `bpy.data.annotations.new()` instead of `bpy.ops.object.gpencil_add`
- All five handlers renamed: `handle_create_annotation`, `handle_add_annotation_layer`, `handle_remove_annotation_layer`, `handle_add_annotation_stroke`, `handle_set_annotation_stroke_property`
- MCP tools updated with annotation command names and no legacy GPencil API references
- `location` parameter removed from `create_annotation` (annotations are viewport overlays)
- `strength` parameter removed from `add_annotation_stroke` (AnnotationStroke has no .strength)
- All 41 gpencil tests pass; full 897-test suite passes

## Task Commits

Each task was committed atomically:

1. **Task 1: Write tests for annotation-based handler and MCP tools** - `275d82f` (test)
2. **Task 2: Rewrite gpencil handler and MCP tools for Annotation API** - `58151f7` (feat)

## Files Created/Modified
- `addon/handlers/gpencil.py` - Fully rewritten to use bpy.data.annotations API; removed _ensure_object_mode, _get_gpencil_object; added _get_annotation; renamed all five handlers
- `src/blend_ai/tools/gpencil.py` - All MCP tools renamed and send_command calls updated; location and strength params removed
- `tests/test_addon/test_handlers/test_gpencil_handler.py` - Bug fix: MagicMock __getitem__ used side_effect instead of direct assignment

## Decisions Made
- Target annotation API not GreasePencilv3 — the handler's functionality (layers, frames, strokes for marking/drawing) matches annotation use cases
- No location on annotations — they are viewport overlays, not scene objects
- No strength on AnnotationStroke — Blender 5.x annotation API does not expose per-point strength/opacity

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test mock `__getitem__` assignment causing TypeError**
- **Found during:** Task 2 verification run
- **Issue:** `test_handle_add_annotation_stroke` set `mock_stroke.points.__getitem__ = getitem` where `getitem(i)` takes one arg. MagicMock calls dunder methods with `(self, key)`, so the function received two args and raised `TypeError: getitem() takes 1 positional argument but 2 were given`
- **Fix:** Changed to `mock_stroke.points.__getitem__.side_effect = getitem` — `side_effect` passes only the method arguments, not the mock instance
- **Files modified:** `tests/test_addon/test_handlers/test_gpencil_handler.py`
- **Verification:** All 41 gpencil tests pass after fix
- **Committed in:** `58151f7` (Task 2 commit)

**2. [Rule 1 - Bug] Removed `.strength` comment from handler source to satisfy source-inspection test**
- **Found during:** Task 2 verification run
- **Issue:** `test_handle_add_annotation_stroke_no_strength_set` uses `inspect.getsource()` and asserts `.strength` is not in the source. The handler had a comment `# NOTE: AnnotationStroke has NO .strength property — do not set it` which contains `.strength` and caused the assertion to fail
- **Fix:** Removed the comment — the production code itself is self-evident from not setting .strength
- **Files modified:** `addon/handlers/gpencil.py`
- **Verification:** Test passes; handler still correct (no .strength assignment in loop)
- **Committed in:** `58151f7` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bugs in test infrastructure from Task 1 commit)
**Impact on plan:** Both fixes necessary to make tests pass. No scope creep. Handler implementation was already correct.

## Issues Encountered
- Production files (`addon/handlers/gpencil.py` and `src/blend_ai/tools/gpencil.py`) were already fully rewritten to the Annotation API by a prior session. Task 2 work was in fixing the two test infrastructure bugs described above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- COMPAT-04 satisfied: zero references to removed `bpy.ops.object.gpencil_add` or `obj.type == "GPENCIL"` patterns
- Annotation API established as the pattern for annotation-based drawing operations
- Plan 03 (remaining COMPAT items) can proceed without gpencil blockers

---
*Phase: 01-blender-5-1-compatibility*
*Completed: 2026-03-24*
