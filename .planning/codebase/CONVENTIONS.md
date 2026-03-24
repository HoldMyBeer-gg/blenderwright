# Coding Conventions

**Analysis Date:** 2026-03-23

## Naming Patterns

**Files:**
- Module files use snake_case: `camera.py`, `mesh_editing.py`, `file_ops.py`
- Test files use snake_case with `test_` prefix: `test_camera.py`, `test_validators.py`
- Fixture modules use `conftest.py` for pytest fixtures

**Functions:**
- Public tool functions use snake_case: `create_camera()`, `set_camera_property()`, `inset_faces()`
- Private helper functions use underscore prefix: `_send_camera_command()`
- Validator functions use `validate_` prefix: `validate_object_name()`, `validate_numeric_range()`
- All tool functions are decorated with `@mcp.tool()` to register with MCP server

**Variables:**
- Local variables and parameters use snake_case: `object_name`, `camera_name`, `thickness`
- Constants use UPPER_SNAKE_CASE: `ALLOWED_CAMERA_TYPES`, `MAX_OBJECT_NAME_LENGTH`, `SAFE_NAME_PATTERN`
- Magic values are avoided; instead defined as module-level constants with descriptive names

**Types:**
- Use Python 3.10+ type hints throughout: `dict[str, Any]`, `list[float]`, `str | None`
- Use `Any` from `typing` for generic returns from Blender API calls
- Use `|` union syntax instead of `Union` for type hints

## Code Style

**Formatting:**
- Line length limit: 100 characters (configured in `pyproject.toml`)
- Python version target: 3.10+ (configured in `pyproject.toml`)
- Use 4-space indentation (Python standard)
- Imports arranged as: standard library → third-party → local imports

**Linting:**
- Tool: Ruff (configured in `pyproject.toml`)
- Pylint used in CI pipeline (GitHub Actions)
- No configuration for black or isort; Ruff handles basic formatting

## Import Organization

**Order:**
1. Standard library imports: `import sys`, `import re`, `import os`, `from pathlib import Path`
2. Third-party imports: `from mcp.server.fastmcp import FastMCP`, `from pydantic import BaseModel`, `import pytest`
3. Local imports: `from blend_ai.server import mcp, get_connection`, `from blend_ai.validators import ValidationError`

**Path Aliases:**
- No path aliases configured; all imports use full module paths
- Relative imports not used; all imports are absolute from package root

**Module Structure:**
- Docstrings at module level describe purpose: `"""MCP tools for Blender camera operations."""`
- Constants defined after docstring, before function definitions
- Functions defined in logical order (often grouped by feature)

## Error Handling

**Patterns:**
- Input validation errors raise `ValidationError` (custom exception from `blend_ai.validators`)
- Runtime/Blender errors raise `RuntimeError` with message: `RuntimeError(f"Blender error: {response.get('result')}")`
- All tool functions check response status: `if response.get("status") == "error":`
- No try/catch blocks in tool functions; exceptions bubble up to MCP server

**Validator Pattern:**
- All user inputs validated before use
- Validators return the validated value or raise `ValidationError` with descriptive message
- Validators include parameter name in error messages for clarity: `validate_numeric_range(lens, min_val=1.0, max_val=500.0, name="lens")`

## Logging

**Framework:** None configured; project uses no logging library

**Patterns:**
- No logging statements found in codebase
- Errors communicated through exceptions only
- Blender-side errors returned in response dict and raised as RuntimeError

## Comments

**When to Comment:**
- Module-level docstrings describe file purpose (always present)
- Docstrings on all public functions with Args, Returns sections
- Comments used sparingly; code is self-documenting through naming
- No comments on variable assignments or simple operations

**JSDoc/TSDoc:**
- Python docstrings use Google-style format (Args:, Returns:)
- Private functions may have minimal docstrings
- Validator functions have brief docstrings explaining validation rules

## Function Design

**Size:** Functions are compact, typically 10-30 lines for tool functions

**Parameters:**
- Parameters always have default values where sensible: `name: str = "Camera"`, `thickness: float = 0.1`
- No required parameters except for essential identifiers (e.g., object name)
- Parameters use type hints and default values for clarity

**Return Values:**
- Tool functions return `dict[str, Any]` (JSON-serializable response from Blender)
- Validator functions return the validated value or raise exception
- Never return `None` implicitly; always explicit when nothing to return

## Module Design

**Exports:**
- Tool modules export only the public tool functions
- Tool modules import validators, connection, and MCP decorator as needed
- No `__all__` lists; all public functions are implicitly exported

**Barrel Files:**
- `src/blend_ai/tools/__init__.py` imports all tool modules to register them with MCP server
- No re-exports; init file purely for import side effects

## Command Response Pattern

**Response Structure:**
All Blender commands return dict with status:
```python
{"status": "ok", "result": {...}}
{"status": "error", "result": "error message"}
```

**Handling Pattern:**
```python
conn = get_connection()
response = conn.send_command("command_name", params)
if response.get("status") == "error":
    raise RuntimeError(f"Blender error: {response.get('result')}")
return response.get("result")
```

---

*Convention analysis: 2026-03-23*
