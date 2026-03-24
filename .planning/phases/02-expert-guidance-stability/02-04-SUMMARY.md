---
phase: 02-expert-guidance-stability
plan: 04
subsystem: extensions
tags: [extensions, suggestions, proactive, keyword-matching, addon-detection]
dependency_graph:
  requires: []
  provides: [suggest_extensions, handle_get_installed_extensions, EXTENSION_CATALOG, KNOWN_EXTENSIONS]
  affects: [addon/handlers/scene.py, src/blend_ai/tools/scene.py]
tech_stack:
  added: []
  patterns: ["keyword matching against task description", "dual namespace detection (legacy + bl_ext)"]
key_files:
  created:
    - tests/test_tools/test_extensions.py
    - tests/test_addon/test_handlers/test_scene_handler.py
  modified:
    - addon/handlers/scene.py
    - src/blend_ai/tools/scene.py
decisions:
  - "Scoped to 3 extensions (Bool Tool, LoopTools, Node Wrangler) — third-party extensions deferred"
  - "Empty task_description returns all non-installed extensions as suggestions"
  - "Keyword matching uses simple substring containment on lowercased task description"
metrics:
  duration: "~15 minutes"
  completed: "2026-03-24"
  tasks_completed: 2
  files_modified: 4
---

# Phase 02 Plan 04: Extension Suggestion System Summary

Implemented proactive extension suggestion system with Blender-side addon detection (both legacy and 4.2+ `bl_ext` namespace keys) and MCP-side keyword-based task matching with installed-extension filtering.

## Tasks Completed

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1 | Extension detection handler and handler tests | b022a97 (tests + handler) | addon/handlers/scene.py, tests/test_addon/test_handlers/test_scene_handler.py |
| 2 | MCP suggest_extensions tool with keyword matching | f748109 (impl) | src/blend_ai/tools/scene.py, tests/test_tools/test_extensions.py |

## What Was Built

**Handler layer (GUIDE-05):**

1. `KNOWN_EXTENSIONS` dict in `addon/handlers/scene.py` — Maps 3 extensions (bool_tool, looptools, node_wrangler) with both legacy module keys and `bl_ext.blender_org.*` keys for Blender 4.2+ compatibility.

2. `handle_get_installed_extensions(params)` — Queries `bpy.context.preferences.addons` using both legacy and bl_ext namespace keys. Returns `{"installed": ["bool_tool", ...]}` for detected extensions. Registered as `get_installed_extensions` command.

**MCP tool layer (GUIDE-04):**

3. `EXTENSION_CATALOG` dict in `src/blend_ai/tools/scene.py` — Maps 3 extensions with name, description, and keyword lists for task matching.

4. `suggest_extensions(task_description)` MCP tool — Queries Blender for installed extensions via `get_installed_extensions` command, then matches task description against extension keywords. Returns `{"suggestions": [...], "installed": [...]}`. Empty task returns all non-installed extensions. Each suggestion includes `extension_id`, `name`, and `description`.

## Test Coverage

17 tests across 4 test classes in 2 test files. All pass.

**tests/test_addon/test_handlers/test_scene_handler.py (5 tests):**
- TestGetInstalledExtensions: no extensions, legacy key detection, bl_ext key detection, all three detected, command registered in dispatcher

**tests/test_tools/test_extensions.py (12 tests):**
- TestSuggestExtensions (9 tests): boolean→Bool Tool, loop→LoopTools, shader→Node Wrangler, unrelated task→empty, empty task→all, calls get_installed_extensions, required keys, error raises RuntimeError, result contains installed list
- TestInstalledSkipped (3 tests): installed excluded from boolean suggestions, all installed→empty, partial install shows only non-installed

## Deviations from Plan

None. Implementation matched the plan exactly.

## Known Stubs

None. All functions return real data. Extension catalog is intentionally scoped to 3 verified extensions — can be expanded later.

## Self-Check: PASSED

- FOUND: addon/handlers/scene.py contains `KNOWN_EXTENSIONS` and `handle_get_installed_extensions`
- FOUND: addon/handlers/scene.py contains `legacy_key` and `bl_ext.blender_org`
- FOUND: src/blend_ai/tools/scene.py contains `EXTENSION_CATALOG` and `suggest_extensions`
- FOUND: tests/test_tools/test_extensions.py contains `TestSuggestExtensions` and `TestInstalledSkipped`
- FOUND: tests/test_addon/test_handlers/test_scene_handler.py contains `TestGetInstalledExtensions`
- COMMIT b022a97 confirmed in git log
- COMMIT f748109 confirmed in git log
