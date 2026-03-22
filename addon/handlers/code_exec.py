"""Blender addon handler for arbitrary code execution."""

import bpy
import sys
import io
from .. import dispatcher


def handle_execute_code(params: dict) -> dict:
    """Execute arbitrary Python code in Blender and capture stdout."""
    code = params.get("code", "")
    if not code:
        raise ValueError("No code provided")

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        exec(code, {"__builtins__": __builtins__})
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
