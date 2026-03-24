# Testing Patterns

**Analysis Date:** 2026-03-23

## Test Framework

**Runner:**
- pytest 7.0+ (configured in `pyproject.toml`)
- Config file: `pyproject.toml` under `[tool.pytest.ini_options]`
- asyncio support: pytest-asyncio 0.21+
- Coverage: pytest-cov 4.0+

**Assertion Library:**
- pytest's built-in assertions (no additional library)

**Run Commands:**
```bash
pytest                  # Run all tests
pytest tests/          # Run tests directory
pytest -v              # Verbose output
pytest --cov           # Generate coverage report
pytest -k "test_name"  # Run specific test by pattern
pytest tests/test_tools/test_camera.py  # Run specific test file
pytest --tb=short      # Shorter traceback format
```

## Test File Organization

**Location:**
- Tests co-located in parallel structure: `tests/test_tools/` mirrors `src/blend_ai/tools/`
- Separate test modules for each tool module: `test_camera.py`, `test_mesh_editing.py`, etc.
- Conftest files at strategic levels: `tests/conftest.py`, `tests/test_tools/conftest.py`

**Naming:**
- Test files named `test_*.py` or `*_test.py`
- Test classes named `Test<FeatureName>` (e.g., `TestCreateCamera`, `TestInsetFaces`)
- Test methods named `test_<scenario>` (e.g., `test_create_camera_defaults`, `test_lens_out_of_range`)

**Structure:**
```
tests/
├── conftest.py                    # Global fixtures (mock_connection, mock_socket)
├── test_tools/
│   ├── conftest.py               # Mocks server module before imports
│   ├── test_camera.py
│   ├── test_objects.py
│   └── [20+ more test files]
├── test_addon/
│   ├── conftest.py               # Mocks bpy module
│   └── test_render_guard.py
├── test_connection.py
└── test_validators.py
```

## Test Structure

**Suite Organization:**
```python
# Typical test file structure
"""Unit tests for camera tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"name": "Camera"}}
    with patch("blend_ai.tools.camera.get_connection", return_value=mock):
        yield mock


class TestCreateCamera:
    def test_create_camera_defaults(self, mock_conn):
        from blend_ai.tools.camera import create_camera

        result = create_camera()
        mock_conn.send_command.assert_called_once_with("create_camera", {
            "name": "Camera",
            "location": [0, 0, 0],
            "rotation": [0, 0, 0],
            "lens": 50.0,
        })
        assert result == {"name": "Camera"}

    def test_create_camera_invalid(self, mock_conn):
        from blend_ai.tools.camera import create_camera

        with pytest.raises(ValidationError):
            create_camera(lens=0.5)
```

**Patterns:**
- Setup: Fixture provides mocked connection with `return_value` set for success cases
- Teardown: pytest handles cleanup via context managers in fixtures (no explicit cleanup)
- Assertion: Mix of mock assertions (`assert_called_once_with`) and value assertions (`assert result ==`)

## Mocking

**Framework:** unittest.mock (standard library)

**Patterns:**
```python
# Mock the connection at import point
@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"name": "Camera"}}
    with patch("blend_ai.tools.camera.get_connection", return_value=mock):
        yield mock

# Mock bpy module for addon tests (conftest.py)
mock_bpy = MagicMock()
mock_bpy.app.timers.is_registered = MagicMock(return_value=False)
sys.modules["bpy"] = mock_bpy

# Mock server module before tool imports (test_tools/conftest.py)
_fake_server = types.ModuleType("blend_ai.server")
_mcp_mock = MagicMock()
_mcp_mock.tool.return_value = lambda fn: fn
_fake_server.mcp = _mcp_mock
sys.modules.setdefault("blend_ai.server", _fake_server)
```

**What to Mock:**
- External connections: `blend_ai.tools.camera.get_connection` → returns MagicMock with configured responses
- System modules: `bpy` (Blender Python API) → fully mocked in conftest
- MCP server components: The `mcp.tool()` decorator → mocked as identity function in conftest
- API responses: `send_command()` return values configured per test scenario

**What NOT to Mock:**
- Validator functions: Tests import and call real validators to test validation logic
- Error exceptions: Real `ValidationError` and `RuntimeError` raised, not mocked
- Standard library: Path, re, os used directly without mocking

## Fixtures and Factories

**Test Data:**
- No factory patterns; minimal test data used
- Fixture returns configured mock, not test data factories
- Test data embedded inline in test methods

**Location:**
- Shared fixtures: `tests/conftest.py` (global fixtures)
- Module-specific fixtures: `tests/test_tools/conftest.py` (server mocking)
- File-local fixtures: Each test file defines `mock_conn` fixture specific to its module

**Fixture Pattern (Global):**
```python
# tests/conftest.py
@pytest.fixture
def mock_connection():
    """Mock BlenderConnection that returns configurable responses."""
    with patch("blend_ai.server._connection") as mock_conn:
        conn = MagicMock()
        conn.send_command = MagicMock(return_value={"status": "ok", "result": {}})
        mock_conn.return_value = conn
        with patch("blend_ai.server.get_connection", return_value=conn):
            yield conn

@pytest.fixture
def mock_socket():
    """Mock socket for connection tests."""
    with patch("socket.socket") as mock_sock_class:
        mock_sock = MagicMock()
        mock_sock_class.return_value = mock_sock
        yield mock_sock
```

## Coverage

**Requirements:** None enforced in CI/pre-commit

**View Coverage:**
```bash
pytest --cov=blend_ai --cov-report=html
pytest --cov=blend_ai --cov-report=term-missing
```

**Approach:**
- Comprehensive test coverage for validators (all edge cases tested)
- All tool functions tested for happy path and error conditions
- Mock-heavy approach means no coverage gap analysis needed (everything tested)

## Test Types

**Unit Tests:**
- Scope: Individual functions (validators, tools)
- Approach: Mock external dependencies (Blender connection, MCP server)
- Location: `tests/test_tools/`, `tests/test_validators.py`
- Count: 20+ test modules, hundreds of individual test methods

**Integration Tests:**
- Scope: Tool + validator + connection interaction
- Approach: Mock Blender response, test full request flow
- Example: `test_create_camera_defaults` validates input AND checks mock was called with correct params

**E2E Tests:**
- Not used; project requires running in Blender context which isn't available in test environment
- Real Blender validation happens when addon is loaded

## Common Patterns

**Validation Testing Pattern:**
```python
def test_lens_out_of_range(self, mock_conn):
    from blend_ai.tools.camera import create_camera

    with pytest.raises(ValidationError):
        create_camera(lens=0.5)  # Below min_val=1.0
    with pytest.raises(ValidationError):
        create_camera(lens=501.0)  # Above max_val=500.0
```

**Async Testing:**
- Not explicitly used; project configured with `asyncio_mode = "auto"` for async test support
- No async tool functions detected in codebase

**Error Response Testing:**
```python
def test_error_response_raises(self, mock_conn):
    mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
    with pytest.raises(RuntimeError):
        create_camera()
```

**Mock Assertion Pattern:**
```python
mock_conn.send_command.assert_called_once_with(
    "create_camera",
    {
        "name": "Camera",
        "location": [0, 0, 0],
        "rotation": [0, 0, 0],
        "lens": 50.0,
    },
)
```

## Validator Test Structure

**File:** `tests/test_validators.py`

**Pattern:**
```python
# Test grouped by validator function
class TestValidateObjectName:
    def test_valid_simple_name(self):
        assert validate_object_name("Cube") == "Cube"

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            validate_object_name("")

    def test_invalid_chars_raises(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_object_name("Cube@#!")
```

**Coverage:**
- Validators tested directly (no mocks)
- All boundary conditions tested (empty, too long, invalid chars, etc.)
- Error messages checked with `match=` parameter

## Tool Function Test Pattern

**Per-function structure:**
```python
# Separated by comment block
# ---------------------------------------------------------------------------
# function_name
# ---------------------------------------------------------------------------

class TestFunctionName:
    def test_valid_defaults(self, mock_conn):
        """Happy path with default parameters."""
        function_name("Cube")
        mock_conn.send_command.assert_called_once_with(
            "command_name",
            {"object_name": "Cube", "param": default_value},
        )

    def test_custom_params(self, mock_conn):
        """Custom parameters passed through."""
        function_name("Cube", param=custom_value)
        args = mock_conn.send_command.call_args[0][1]
        assert args["param"] == custom_value

    def test_invalid_param_raises(self, mock_conn):
        """Parameter validation catches bad input."""
        with pytest.raises(ValidationError):
            function_name("Cube", param=out_of_range_value)

    def test_error_response_raises(self, mock_conn):
        """Blender errors converted to RuntimeError."""
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            function_name("Cube")
```

---

*Testing analysis: 2026-03-23*
