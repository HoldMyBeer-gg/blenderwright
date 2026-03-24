---
phase: 03-visual-feedback-loop
plan: 02
subsystem: prompts
tags: [auto-critique, visual-feedback, screenshot, token-budget, prompts]
dependency_graph:
  requires: [03-01 (fast viewport screenshot)]
  provides: [auto_critique_workflow prompt]
  affects: [src/blend_ai/prompts/workflows.py]
tech_stack:
  added: []
  patterns: ["@mcp.prompt() identity decorator pattern"]
key_files:
  created:
    - tests/test_tools/test_auto_critique_prompt.py
  modified:
    - src/blend_ai/prompts/workflows.py
decisions:
  - "Auto-critique is prompt-driven (MCP prompt), not server-side logic — MCP is stateless"
  - "Token budget limits critique to 2-3 sentences and one screenshot per batch"
  - "Multi-step sequences capture once at end, not after every individual step"
metrics:
  duration: "~5 minutes"
  completed: "2026-03-24"
  tasks_completed: 2
  files_modified: 2
---

# Phase 03 Plan 02: Auto-Critique Prompt Summary

Added `auto_critique_workflow` MCP prompt that instructs the LLM to capture and self-critique its work after structural changes, with explicit token-safety guidelines.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Tests (RED) | c4378bc | tests/test_tools/test_auto_critique_prompt.py |
| 2 | Implementation (GREEN) | 684ded1 | src/blend_ai/prompts/workflows.py |

## What Was Built

**auto_critique_workflow prompt function** in `src/blend_ai/prompts/workflows.py`:

- Lists **structural operations requiring auto-critique**: adding objects, deleting, boolean operations, modifiers, sculpting, materials/shaders, lighting, camera positioning, mesh editing
- Lists **operations excluded from auto-critique**: renaming, querying scene info, collection organization, file save/export, keyframe insertion, non-visual properties
- Provides **critique checklist**: correct shape, proportions, topology, lighting, next steps
- Includes **token budget rules**: 2-3 sentences, one screenshot per operation/batch, capture once at end of multi-step sequences, respect user skip preference

## Test Coverage

8 tests in `tests/test_tools/test_auto_critique_prompt.py`. All pass.

- TestAutoCritiquePrompt: returns non-empty string, mentions get_viewport_screenshot, mentions fast mode, lists structural operations, lists excluded operations, mentions token budget, prevents multi-capture, includes critique checklist

## Deviations from Plan

### Auto-fixed Issues

**1. Mock mcp.prompt() decorator needed identity setup**
- Test file needed `_server.mcp.prompt.return_value = lambda fn: fn` before import
- Followed existing pattern from `test_prompts.py`

## Self-Check: PASSED

- FOUND: src/blend_ai/prompts/workflows.py contains `auto_critique_workflow`
- FOUND: src/blend_ai/prompts/workflows.py contains `get_viewport_screenshot`
- FOUND: src/blend_ai/prompts/workflows.py contains `Token Budget`
- COMMIT c4378bc (tests) confirmed
- COMMIT 684ded1 (implementation) confirmed
