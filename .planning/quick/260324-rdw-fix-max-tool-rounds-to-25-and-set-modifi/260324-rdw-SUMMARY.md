# Quick Task 260324-rdw Summary

**Task:** Fix MAX_TOOL_ROUNDS to 25 and set_modifier_property type coercion
**Date:** 2026-03-25
**Commit:** 228d09f

## What Was Done

### Fix 1: MAX_TOOL_ROUNDS bumped to 25

`src/blend_ai/ollama_chat.py` line 28: `MAX_TOOL_ROUNDS = 10` → `MAX_TOOL_ROUNDS = 25`

Complex Blender tasks (multi-object scenes, material setup, sculpting) routinely need more than 10 tool calls.

### Fix 2: Type coercion in handle_set_modifier_property

`addon/handlers/modeling.py` `handle_set_modifier_property()`: added coercion logic before `setattr` that reads the current property type and casts the incoming value to match.

- `"3"` → `3` (string to int)
- `"2.5"` → `2.5` (string to float)
- `"true"` / `1` → `True` (string/int to bool, with bool-before-int check)
- `None`, `list`, `tuple` current values: coercion skipped
- Failed coercion: falls through to setattr for Blender's own error

### Tests Added

- `tests/test_ollama_chat.py::TestConstants::test_max_tool_rounds_is_25`
- `tests/test_addon/test_handlers/test_modeling_handler.py` — 10 coercion tests

## Result

59 tests pass across affected files.
