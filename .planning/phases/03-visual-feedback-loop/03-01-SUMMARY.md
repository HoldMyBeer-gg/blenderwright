---
phase: 03-visual-feedback-loop
plan: 01
subsystem: screenshot
tags: [viewport, opengl, fast-capture, screenshot, render-guard]
dependency_graph:
  requires: []
  provides: [handle_fast_viewport_capture, fast_viewport_capture command, mode parameter on get_viewport_screenshot]
  affects: [addon/handlers/camera.py, src/blend_ai/tools/screenshot.py]
tech_stack:
  added: []
  patterns: ["bpy.ops.render.opengl(write_still=True)", "bpy.context.temp_override for VIEW_3D context", "validate_enum for mode parameter"]
key_files:
  created:
    - tests/test_addon/test_handlers/test_camera_handler.py
    - tests/test_tools/test_screenshot.py
  modified:
    - addon/handlers/camera.py
    - src/blend_ai/tools/screenshot.py
decisions:
  - "Default mode changed from full render to fast (opengl) — fast is the common case for feedback loops"
  - "Removed unused user_prompt parameter from get_viewport_screenshot — was a telemetry artifact"
  - "Handler uses nested for-loop with found flag instead of for/else for clarity"
metrics:
  duration: "~15 minutes"
  completed: "2026-03-24"
  tasks_completed: 4
  files_modified: 4
---

# Phase 03 Plan 01: Fast Viewport Capture Summary

Added fast viewport screenshot using `bpy.ops.render.opengl()` (captures in milliseconds, doesn't trigger render guard) and updated MCP tool with `mode` parameter defaulting to `"fast"`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1-2 | Tests (RED) | c4378bc | tests/test_addon/test_handlers/test_camera_handler.py, tests/test_tools/test_screenshot.py |
| 3-4 | Implementation (GREEN) | 684ded1 | addon/handlers/camera.py, src/blend_ai/tools/screenshot.py |

## What Was Built

**Handler (addon/handlers/camera.py):**

1. `handle_fast_viewport_capture(params)` — Uses `bpy.ops.render.opengl(write_still=True)` with `bpy.context.temp_override()` to provide VIEW_3D context. Stores/restores resolution in a `finally` block. Returns base64 PNG with `mode="fast"`. Registered as `fast_viewport_capture` command.

**MCP Tool (src/blend_ai/tools/screenshot.py):**

2. `get_viewport_screenshot(max_size, mode)` — Updated with `mode` parameter (`"fast"` or `"full"`, default `"fast"`). Routes to `fast_viewport_capture` or `capture_viewport` command. Added `validate_enum` for mode validation. Removed unused `user_prompt` parameter.

## Test Coverage

22 tests across 2 test files. All pass.

**tests/test_addon/test_handlers/test_camera_handler.py (13 tests):**
- TestFastViewportCapture: calls render.opengl, result keys, mode=fast, format=png, valid base64, resolution restore on success/exception, temp_override with VIEW_3D, default/custom resolution, dispatcher registration, no VIEW_3D raises, no render result raises

**tests/test_tools/test_screenshot.py (9 tests):**
- TestGetViewportScreenshot: fast mode command, full mode command, default is fast, passes width/height, error raises RuntimeError, returns result, max_size validation (too small/large), invalid mode raises

## Deviations from Plan

### Auto-fixed Issues

**1. Dispatcher registration test needed register() call**
- Handler tests use importlib direct-loading which doesn't call register() automatically
- Fixed by calling `mod.register()` and checking `register_handler.call_args_list`
- Followed pattern from `test_scene_handler.py`

## Self-Check: PASSED

- FOUND: addon/handlers/camera.py contains `render.opengl` and `handle_fast_viewport_capture`
- FOUND: addon/handlers/camera.py contains `temp_override`
- FOUND: src/blend_ai/tools/screenshot.py contains `mode` and `ALLOWED_SCREENSHOT_MODES`
- FOUND: src/blend_ai/tools/screenshot.py contains `fast_viewport_capture` and `capture_viewport`
- COMMIT c4378bc (tests) confirmed
- COMMIT 684ded1 (implementation) confirmed
