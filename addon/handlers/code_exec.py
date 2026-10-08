"""Blender addon handler for raw Python execution (off by default).

What this is: a restricted namespace that blocks the obvious footguns
(import os/subprocess/socket..., exec/eval/open/compile) so a model
that makes a mistake fails loudly instead of touching the filesystem
or the network by accident.

What this is NOT: a security boundary. The code runs in-process inside
Blender with full `bpy`, and `bpy` alone can save files anywhere and
run any operator. A denylist cannot contain a determined adversary in
the same interpreter, and this module does not claim to.

So the real control is the switch, not the list:

- `execute_code` is refused unless the user has ticked "Allow raw
  Python" in the blenderwright N-panel. The flag lives on
  `bpy.types.WindowManager`, so it is per session and is never saved
  into a .blend file that could be handed to someone else.
- Every snippet that runs is echoed to the system console and kept in
  a short log that the panel displays, so the user can see what the
  model actually did.
"""

import sys
import io
import time
from collections import deque
from .. import dispatcher


# Name of the per-session switch registered on bpy.types.WindowManager
# by ui_panel.register(). Not a Scene property on purpose: Scene props
# are written into the .blend.
SWITCH_PROP = "blenderwright_allow_code_exec"

# How many recent runs the panel can show.
EXEC_LOG_SIZE = 20
_exec_log: deque = deque(maxlen=EXEC_LOG_SIZE)


def is_enabled() -> bool:
    """True only if the user turned raw Python on for this Blender session.

    Anything other than a real `True` (missing property, wrong type, no
    window manager yet, bpy not importable) counts as off.
    """
    try:
        import bpy
        flag = getattr(bpy.context.window_manager, SWITCH_PROP, False)
    except Exception:
        return False
    return isinstance(flag, bool) and flag


def get_exec_log() -> list:
    """Copy of the recent-run log, oldest first."""
    return list(_exec_log)


def _record(code: str, ok: bool) -> None:
    lines = code.strip().splitlines() or [""]
    _exec_log.append({
        "time": time.strftime("%H:%M:%S"),
        "first_line": lines[0].strip(),
        "lines": len(lines),
        "ok": ok,
    })


# Modules refused by the import hook. A guard against accidental misuse by
# the model, not a security control: see the module docstring.
BLOCKED_MODULES = frozenset({
    "os", "subprocess", "socket", "shutil", "sys", "ctypes",
    "importlib", "pathlib", "signal", "multiprocessing",
    "pickle", "shelve", "tempfile", "http", "urllib", "ftplib",
    "smtplib", "xmlrpc", "code", "codeop", "compileall",
    "webbrowser", "antigravity", "turtle", "tkinter",
})

# Builtins removed from the restricted namespace. Same caveat as above.
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
    """Import hook that refuses the modules in BLOCKED_MODULES."""
    base_module = name.split(".")[0]
    if base_module in BLOCKED_MODULES:
        raise ImportError(
            f"Module '{name}' is blocked inside execute_blender_code. "
            f"Use the structured MCP tools instead of direct Python imports."
        )
    return _real_import(name, *args, **kwargs)


def _build_safe_builtins():
    """Build the restricted builtins dict."""
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
    """Run Python inside Blender, if the user has allowed it this session.

    - Refuses with PermissionError while "Allow raw Python" is unticked.
    - Echoes the snippet to the system console (stderr) and records it
      in the exec log before running it.
    - Runs in the restricted namespace (see module docstring for what
      that does and does not mean) and captures stdout.
    """
    code = params.get("code", "")
    if not code:
        raise ValueError("No code provided")

    if not is_enabled():
        raise PermissionError(
            "execute_blender_code is disabled. Raw Python is off by default; "
            "tick 'Allow raw Python' in the blenderwright panel "
            "(View3D > Sidebar > blenderwright) to enable it for this Blender "
            "session, or use the structured tools instead."
        )

    # Echo to the real console so the user can see what ran, regardless
    # of whether the MCP client shows tool inputs. Goes to stderr so it
    # is never mixed into the captured stdout returned to the model.
    print(
        f"[blenderwright] execute_code ({time.strftime('%H:%M:%S')}):\n{code}",
        file=sys.stderr,
    )

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        exec(code, {"__builtins__": SAFE_BUILTINS})
        output = buffer.getvalue()
        _record(code, ok=True)
        return {
            "output": output.strip(),
            "success": True,
        }
    except Exception as e:
        output = buffer.getvalue()
        _record(code, ok=False)
        raise RuntimeError(f"{type(e).__name__}: {e}\nOutput before error: {output}")
    finally:
        sys.stdout = old_stdout


def register():
    """Register code execution handler with the dispatcher."""
    dispatcher.register_handler("execute_code", handle_execute_code)
