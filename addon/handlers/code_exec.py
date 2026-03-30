"""Blender addon handler for sandboxed code execution.

Provides a restricted execution environment that blocks dangerous
modules (os, subprocess, socket, etc.) and removes dangerous
builtins (exec, eval, open, compile) while allowing safe Blender
operations (bpy, bmesh, mathutils, math, json).
"""

import sys
import io
from .. import dispatcher


# Modules blocked from import — prevents RCE via import os, subprocess, etc.
BLOCKED_MODULES = frozenset({
    "os", "subprocess", "socket", "shutil", "sys", "ctypes",
    "importlib", "pathlib", "signal", "multiprocessing",
    "pickle", "shelve", "tempfile", "http", "urllib", "ftplib",
    "smtplib", "xmlrpc", "code", "codeop", "compileall",
    "webbrowser", "antigravity", "turtle", "tkinter",
})

# Builtins removed from the sandbox — prevents code injection and file access
_REMOVED_BUILTINS = frozenset({
    "__import__", "exec", "eval", "compile", "open",
    "globals", "locals", "vars", "input", "breakpoint",
    "exit", "quit", "help", "memoryview",
})

# Reference to the real __import__ for the safe import hook
_real_import = builtins_import = __builtins__.__import__ if hasattr(
    __builtins__, "__import__"
) else __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__


def _safe_import(name, *args, **kwargs):
    """Import hook that blocks dangerous modules."""
    base_module = name.split(".")[0]
    if base_module in BLOCKED_MODULES:
        raise ImportError(
            f"Module '{name}' is blocked for security reasons. "
            f"Use the structured MCP tools instead of direct Python imports."
        )
    return _real_import(name, *args, **kwargs)


def _build_safe_builtins():
    """Build a restricted builtins dict for sandboxed execution."""
    # Get all builtins as a dict
    if isinstance(__builtins__, dict):
        raw = dict(__builtins__)
    else:
        raw = {k: getattr(__builtins__, k) for k in dir(__builtins__)}

    # Remove dangerous builtins
    safe = {k: v for k, v in raw.items() if k not in _REMOVED_BUILTINS}

    # Add our safe import hook
    safe["__import__"] = _safe_import

    return safe


# Build once at module load
SAFE_BUILTINS = _build_safe_builtins()


def handle_execute_code(params: dict) -> dict:
    """Execute Python code in a sandboxed Blender environment.

    The sandbox:
    - Blocks dangerous imports (os, subprocess, socket, shutil, etc.)
    - Removes dangerous builtins (exec, eval, open, compile, etc.)
    - Allows safe Blender imports (bpy, bmesh, mathutils, math, json)
    - Captures stdout output
    """
    code = params.get("code", "")
    if not code:
        raise ValueError("No code provided")

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        exec(code, {"__builtins__": SAFE_BUILTINS})
        output = buffer.getvalue()
        return {
            "output": output.strip(),
            "success": True,
        }
    except Exception as e:
        output = buffer.getvalue()
        raise RuntimeError(f"{type(e).__name__}: {e}\nOutput before error: {output}")
    finally:
        sys.stdout = old_stdout


def register():
    """Register code execution handler with the dispatcher."""
    dispatcher.register_handler("execute_code", handle_execute_code)
