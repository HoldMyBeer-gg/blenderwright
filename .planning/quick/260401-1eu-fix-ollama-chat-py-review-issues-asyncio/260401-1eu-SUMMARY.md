---
phase: quick
plan: 260401-1eu
subsystem: ollama_chat
tags: [asyncio, performance, correctness, parsing, vision]
dependency_graph:
  requires: []
  provides: [cached-event-loop, tighter-json-scanner, full-tag-stripping, structured-vision-note]
  affects: [src/blend_ai/ollama_chat.py, tests/test_ollama_chat.py]
tech_stack:
  added: []
  patterns: [cached-asyncio-event-loop, tdd-red-green]
key_files:
  created: [src/blend_ai/tool_registry.py]
  modified: [src/blend_ai/ollama_chat.py, tests/test_ollama_chat.py]
decisions:
  - "Cached event loop uses asyncio.new_event_loop() stored on self._loop; closed in close()"
  - "Pattern 2 JSON scanner requires both 'name' and 'arguments' keys to avoid Blender scene data false positives"
  - "_strip_tool_markup removes both opening <tool_call> and closing </tool_call> tags via two re.sub calls"
  - "Vision note embedded under 'vision_analysis' JSON key when result is parseable JSON; falls back to concat"
metrics:
  duration: 305s
  completed: "2026-04-01"
  tasks_completed: 2
  files_modified: 3
---

# Phase quick Plan 260401-1eu: Fix ollama_chat.py Review Issues (asyncio) Summary

**One-liner:** Four correctness fixes — cached asyncio loop replacing per-call asyncio.run(), tighter JSON tool-call detection, full <tool_call> tag stripping, and structured vision analysis embedding.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write tests for all four fixes (RED) | 2c68ed7 | tests/test_ollama_chat.py, src/blend_ai/tool_registry.py |
| 2 | Apply all four fixes to ollama_chat.py (GREEN) | a2069a8 | src/blend_ai/ollama_chat.py, tests/test_ollama_chat.py |

## What Was Built

### Fix 1: Cached Event Loop (Performance)

`execute_tool` previously called `asyncio.run()` on every tool invocation, which creates and destroys an event loop each time. Now `self._loop: asyncio.AbstractEventLoop | None` is lazily created on first call and reused. The loop is closed in `close()`. `import asyncio` moved to module level.

### Fix 2: Tighter JSON Tool-Call Detection (Correctness)

Pattern 2 in `_parse_text_tool_calls` previously accepted any JSON object with a `"name"` key. Blender scene data like `{"name": "Cube", "vertices": 8}` was triggering false positive tool calls. The condition now requires both `"name"` and `"arguments"` keys.

### Fix 3: Full Tag Stripping (Correctness)

`_strip_tool_markup` removed `</tool_call>` closing tags but not `<tool_call>` opening tags. Added `re.sub(r'<tool_call>', '', cleaned)` before the closing tag removal.

### Fix 4: Structured Vision Note (Correctness)

The vision analysis was concatenated as raw text onto the tool result string (`result + vision_note`). When `result` is valid JSON, this produced malformed output (e.g., `{"image":...}\n\n[Vision Analysis]: ...`). Now the code attempts to merge the analysis as `result_obj["vision_analysis"] = analysis` and re-serializes. Falls back to string concatenation on `JSONDecodeError` or `TypeError`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reconstructed missing tool_registry.py from compiled .pyc**
- **Found during:** Task 1 (test collection)
- **Issue:** `src/blend_ai/tool_registry.py` was missing from the repository but `ollama_chat.py` imports `get_ollama_tools` from it. A compiled `.pyc` existed at `src/blend_ai/__pycache__/tool_registry.cpython-313.pyc`. The file was never in git history.
- **Fix:** Reconstructed `tool_registry.py` by inspecting the `.pyc` (function signatures, variable names, constants) and reimplementing `get_ollama_tools()` and `_map_json_type()`.
- **Files modified:** `src/blend_ai/tool_registry.py` (created)
- **Commit:** 2c68ed7

**2. [Rule 1 - Bug] Updated pre-existing test_execute_tool tests that patched asyncio.run**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** `test_execute_tool` and `test_execute_tool_error` patched `asyncio.run` which is no longer called after Fix 1. Both tests broke.
- **Fix:** Replaced `patch("asyncio.run")` approach with async helper functions that `loop.run_until_complete` can accept natively.
- **Files modified:** `tests/test_ollama_chat.py`
- **Commit:** a2069a8

### Out-of-Scope Issues (Deferred)

Pre-existing ruff F401 violations in `ollama_chat.py` (`BlenderConnection`, `ValidationError`, `get_connection` unused imports) and `test_ollama_chat.py` (`unittest.mock`, `call`, `session` unused). These predate this task and are unrelated to the four fixes.

## Known Stubs

None.

## Self-Check: PASSED

- [x] `src/blend_ai/ollama_chat.py` — exists, modified
- [x] `src/blend_ai/tool_registry.py` — exists, created
- [x] `tests/test_ollama_chat.py` — exists, modified
- [x] Commit 2c68ed7 — exists (RED phase + tool_registry)
- [x] Commit a2069a8 — exists (GREEN phase)
- [x] All 63 tests pass
