"""Tests for sandboxed code execution handler."""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_code_exec_handler():
    """Load addon.handlers.code_exec directly."""
    mock_dispatcher = MagicMock()
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "code_exec.py",
    )
    spec = importlib.util.spec_from_file_location(
        "addon.handlers.code_exec", handler_path
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.code_exec"] = mod
    spec.loader.exec_module(mod)
    return mod, mock_dispatcher


@pytest.fixture(scope="module")
def code_exec_handler():
    """Provide loaded code_exec handler module."""
    mod, _dispatcher = _load_code_exec_handler()
    return mod


@pytest.fixture(autouse=True)
def raw_python_enabled(code_exec_handler):
    """Turn the per-session switch on for the sandbox tests below.

    The switch lives on bpy.types.WindowManager so it is never saved into a
    .blend. The mock bpy would otherwise return a truthy MagicMock, so the
    handler must only honour a real bool True; set it explicitly here.
    """
    import bpy
    bpy.context.window_manager.blenderwright_allow_code_exec = True
    yield
    bpy.context.window_manager.blenderwright_allow_code_exec = False


class TestSandboxBlocksDangerousImports:
    """Verify that dangerous modules are blocked."""

    def test_blocks_os_import(self, code_exec_handler):
        """import os raises error with 'blocked' or 'security' message."""
        with pytest.raises(RuntimeError, match="(?i)blocked|security"):
            code_exec_handler.handle_execute_code({"code": "import os"})

    def test_blocks_subprocess_import(self, code_exec_handler):
        """import subprocess raises error."""
        with pytest.raises(RuntimeError, match="(?i)blocked|security"):
            code_exec_handler.handle_execute_code({"code": "import subprocess"})

    def test_blocks_socket_import(self, code_exec_handler):
        """import socket raises error."""
        with pytest.raises(RuntimeError, match="(?i)blocked|security"):
            code_exec_handler.handle_execute_code({"code": "import socket"})

    def test_blocks_shutil_import(self, code_exec_handler):
        """import shutil raises error."""
        with pytest.raises(RuntimeError, match="(?i)blocked|security"):
            code_exec_handler.handle_execute_code({"code": "import shutil"})

    def test_blocks_ctypes_import(self, code_exec_handler):
        """import ctypes raises error."""
        with pytest.raises(RuntimeError, match="(?i)blocked|security"):
            code_exec_handler.handle_execute_code({"code": "import ctypes"})

    def test_blocks_dunder_import(self, code_exec_handler):
        """__import__('os') raises error."""
        with pytest.raises(RuntimeError, match="(?i)blocked|security"):
            code_exec_handler.handle_execute_code(
                {"code": "__import__('os')"}
            )

    def test_blocks_importlib(self, code_exec_handler):
        """import importlib raises error."""
        with pytest.raises(RuntimeError, match="(?i)blocked|security"):
            code_exec_handler.handle_execute_code({"code": "import importlib"})

    def test_blocks_pathlib(self, code_exec_handler):
        """import pathlib raises error."""
        with pytest.raises(RuntimeError, match="(?i)blocked|security"):
            code_exec_handler.handle_execute_code({"code": "import pathlib"})


class TestSandboxBlocksDangerousBuiltins:
    """Verify that dangerous builtins are removed."""

    def test_blocks_exec(self, code_exec_handler):
        """exec() is not available in sandboxed code."""
        with pytest.raises(RuntimeError):
            code_exec_handler.handle_execute_code(
                {"code": "exec('print(1)')"}
            )

    def test_blocks_eval(self, code_exec_handler):
        """eval() is not available in sandboxed code."""
        with pytest.raises(RuntimeError):
            code_exec_handler.handle_execute_code(
                {"code": "result = eval('1+1')"}
            )

    def test_blocks_open(self, code_exec_handler):
        """open() is not available in sandboxed code."""
        with pytest.raises(RuntimeError):
            code_exec_handler.handle_execute_code(
                {"code": "f = open('/etc/passwd')"}
            )

    def test_blocks_compile(self, code_exec_handler):
        """compile() is not available in sandboxed code."""
        with pytest.raises(RuntimeError):
            code_exec_handler.handle_execute_code(
                {"code": "compile('print(1)', '<string>', 'exec')"}
            )


class TestSandboxAllowsSafeCode:
    """Verify that safe operations work."""

    def test_allows_bpy_import(self, code_exec_handler):
        """import bpy succeeds."""
        result = code_exec_handler.handle_execute_code({"code": "import bpy"})
        assert result["success"] is True

    def test_allows_math_import(self, code_exec_handler):
        """import math succeeds."""
        result = code_exec_handler.handle_execute_code({"code": "import math"})
        assert result["success"] is True

    def test_allows_json_import(self, code_exec_handler):
        """import json succeeds."""
        result = code_exec_handler.handle_execute_code({"code": "import json"})
        assert result["success"] is True

    def test_print_output_captured(self, code_exec_handler):
        """print() output is captured in result."""
        result = code_exec_handler.handle_execute_code(
            {"code": "print('hello world')"}
        )
        assert result["success"] is True
        assert "hello world" in result["output"]

    def test_basic_arithmetic(self, code_exec_handler):
        """Basic arithmetic works."""
        result = code_exec_handler.handle_execute_code(
            {"code": "x = 1 + 2\nprint(x)"}
        )
        assert result["success"] is True
        assert "3" in result["output"]

    def test_list_comprehension(self, code_exec_handler):
        """List comprehensions work."""
        result = code_exec_handler.handle_execute_code(
            {"code": "print([x**2 for x in range(5)])"}
        )
        assert result["success"] is True
        assert "[0, 1, 4, 9, 16]" in result["output"]

    def test_empty_code_raises(self, code_exec_handler):
        """Empty code raises ValueError."""
        with pytest.raises(ValueError):
            code_exec_handler.handle_execute_code({"code": ""})

    def test_result_dict_shape(self, code_exec_handler):
        """Result has output and success keys."""
        result = code_exec_handler.handle_execute_code(
            {"code": "print('test')"}
        )
        assert "output" in result
        assert "success" in result


class TestSandboxConstants:
    """Verify that sandbox constants are properly defined."""

    def test_blocked_modules_exists(self, code_exec_handler):
        """BLOCKED_MODULES constant exists."""
        assert hasattr(code_exec_handler, "BLOCKED_MODULES")

    def test_blocked_modules_contains_os(self, code_exec_handler):
        """BLOCKED_MODULES contains 'os'."""
        assert "os" in code_exec_handler.BLOCKED_MODULES

    def test_blocked_modules_contains_subprocess(self, code_exec_handler):
        """BLOCKED_MODULES contains 'subprocess'."""
        assert "subprocess" in code_exec_handler.BLOCKED_MODULES

    def test_blocked_modules_is_set(self, code_exec_handler):
        """BLOCKED_MODULES is a set (for O(1) lookup)."""
        assert isinstance(code_exec_handler.BLOCKED_MODULES, (set, frozenset))


class TestRawPythonIsOffByDefault:
    """execute_code refuses unless the user ticked the box this session."""

    def test_disabled_when_switch_is_false(self, code_exec_handler):
        import bpy
        bpy.context.window_manager.blenderwright_allow_code_exec = False
        with pytest.raises(PermissionError, match="(?i)disabled|Allow raw Python"):
            code_exec_handler.handle_execute_code({"code": "print('x')"})

    def test_disabled_when_switch_is_missing(self, code_exec_handler):
        """No property registered (or a non-bool stand-in) means off."""
        import bpy
        bpy.context.window_manager.blenderwright_allow_code_exec = MagicMock()
        with pytest.raises(PermissionError):
            code_exec_handler.handle_execute_code({"code": "print('x')"})

    def test_disabled_when_bpy_context_raises(self, code_exec_handler, monkeypatch):
        """Any failure reading the switch is treated as off, never on."""

        class _NoContext:
            @property
            def context(self):
                raise AttributeError("no context yet")

        monkeypatch.setitem(sys.modules, "bpy", _NoContext())
        assert code_exec_handler.is_enabled() is False

    def test_refusal_does_not_run_code(self, code_exec_handler):
        import bpy
        bpy.context.window_manager.blenderwright_allow_code_exec = False
        code_exec_handler._exec_log.clear()
        before = 0
        with pytest.raises(PermissionError):
            code_exec_handler.handle_execute_code({"code": "print('never')"})
        assert len(code_exec_handler.get_exec_log()) == before

    def test_refusal_message_names_the_panel(self, code_exec_handler):
        import bpy
        bpy.context.window_manager.blenderwright_allow_code_exec = False
        with pytest.raises(PermissionError, match="blenderwright"):
            code_exec_handler.handle_execute_code({"code": "print('x')"})

    def test_enabled_runs(self, code_exec_handler):
        result = code_exec_handler.handle_execute_code({"code": "print('on')"})
        assert result["success"] is True
        assert "on" in result["output"]


class TestExecLog:
    """Every run is recorded so the user can see what the model did."""

    def test_records_each_run(self, code_exec_handler):
        code_exec_handler._exec_log.clear()
        code_exec_handler.handle_execute_code({"code": "print('a')\nprint('b')"})
        log = code_exec_handler.get_exec_log()
        assert len(log) == 1
        entry = log[-1]
        assert entry["first_line"] == "print('a')"
        assert entry["lines"] == 2
        assert entry["ok"] is True
        assert "time" in entry

    def test_records_failed_run(self, code_exec_handler):
        with pytest.raises(RuntimeError):
            code_exec_handler.handle_execute_code({"code": "raise ValueError('x')"})
        assert code_exec_handler.get_exec_log()[-1]["ok"] is False

    def test_log_is_capped(self, code_exec_handler):
        for i in range(code_exec_handler.EXEC_LOG_SIZE + 5):
            code_exec_handler.handle_execute_code({"code": f"x = {i}"})
        assert len(code_exec_handler.get_exec_log()) == code_exec_handler.EXEC_LOG_SIZE

    def test_echoes_code_to_console(self, code_exec_handler, capsys):
        """The snippet is printed to the real stdout, not the captured buffer."""
        code_exec_handler.handle_execute_code({"code": "print('seen')"})
        err = capsys.readouterr().err
        assert "[blenderwright] execute_code" in err
        assert "print('seen')" in err

    def test_get_exec_log_returns_copy(self, code_exec_handler):
        log = code_exec_handler.get_exec_log()
        log.clear()
        assert isinstance(code_exec_handler.get_exec_log(), list)
