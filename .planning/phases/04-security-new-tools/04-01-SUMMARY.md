---
phase: 04-security-new-tools
plan: 01
subsystem: security
tags: [sandbox, code-exec, rce, security, import-blocking]
dependency_graph:
  requires: []
  provides: [BLOCKED_MODULES, SAFE_BUILTINS, _safe_import, sandboxed handle_execute_code]
  affects: [addon/handlers/code_exec.py, src/blend_ai/tools/code_exec.py]
tech_stack:
  added: []
  patterns: ["restricted __builtins__ dict for exec()", "import hook via __import__ replacement", "frozenset for immutable module blocklist"]
key_files:
  created:
    - tests/test_addon/test_handlers/test_code_exec_handler.py
    - tests/test_tools/test_code_exec.py
  modified:
    - addon/handlers/code_exec.py
    - src/blend_ai/tools/code_exec.py
decisions:
  - "Used builtin restriction + import hook instead of RestrictedPython — simpler, sufficient for localhost threat model"
  - "BLOCKED_MODULES is frozenset for immutability and O(1) lookup"
  - "Removed user_prompt parameter from MCP tool — was unused telemetry artifact"
metrics:
  duration: "~10 minutes"
  completed: "2026-03-24"
  tasks_completed: 2
  files_modified: 4
---

# Phase 04 Plan 01: Code Exec Sandboxing Summary

Sandboxed the `code_exec` handler to prevent RCE by blocking dangerous imports (os, subprocess, socket, etc.) and removing dangerous builtins (exec, eval, open, compile).

## Tasks Completed

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1 | Tests (RED) | 0ab065e | tests/test_addon/test_handlers/test_code_exec_handler.py, tests/test_tools/test_code_exec.py |
| 2 | Implementation (GREEN) | ea47b63 | addon/handlers/code_exec.py, src/blend_ai/tools/code_exec.py |

## What Was Built

**Sandbox implementation (addon/handlers/code_exec.py):**

1. `BLOCKED_MODULES` — frozenset of 24 dangerous modules including os, subprocess, socket, shutil, ctypes, importlib, pathlib, signal, multiprocessing, pickle, http, urllib, etc.

2. `_safe_import(name, *args, **kwargs)` — Import hook that checks the base module name against BLOCKED_MODULES. Raises `ImportError` with clear "blocked for security reasons" message.

3. `SAFE_BUILTINS` — Dict of safe builtins built at module load. Removes `__import__`, `exec`, `eval`, `compile`, `open`, `globals`, `locals`, `vars`, `input`, `breakpoint`, `exit`, `quit`, `help`, `memoryview`. Adds `_safe_import` as `__import__`.

4. `handle_execute_code` — Now uses `exec(code, {"__builtins__": SAFE_BUILTINS})` instead of unrestricted builtins.

**Blocked:** `import os` ❌, `import subprocess` ❌, `exec("code")` ❌, `eval("expr")` ❌, `open("/file")` ❌
**Allowed:** `import bpy` ✅, `import math` ✅, `import json` ✅, `print()` ✅, list comprehensions ✅

## Test Coverage

29 tests across 5 test classes in 2 files. All pass.

- TestSandboxBlocksDangerousImports (8 tests): os, subprocess, socket, shutil, ctypes, __import__, importlib, pathlib
- TestSandboxBlocksDangerousBuiltins (4 tests): exec, eval, open, compile
- TestSandboxAllowsSafeCode (8 tests): bpy, math, json, print output, arithmetic, list comprehension, empty code, result shape
- TestSandboxConstants (4 tests): BLOCKED_MODULES exists, contains os/subprocess, is set type
- TestExecuteBlenderCode (5 tests): MCP tool layer — empty/whitespace, sends command, returns result, error raises

## Self-Check: PASSED

- FOUND: addon/handlers/code_exec.py contains `BLOCKED_MODULES`
- FOUND: addon/handlers/code_exec.py contains `SAFE_BUILTINS`
- FOUND: addon/handlers/code_exec.py contains `_safe_import`
- FOUND: addon/handlers/code_exec.py contains `blocked for security`
- COMMIT 0ab065e (tests) confirmed
- COMMIT ea47b63 (implementation) confirmed
