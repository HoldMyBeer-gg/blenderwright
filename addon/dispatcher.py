"""Command dispatcher with allowlist enforcement.

Routes incoming commands to their handler functions.
Only commands in the explicit allowlist are processed.
"""

from typing import Any, Callable

# Registry of allowed commands -> handler functions
_handlers: dict[str, Callable] = {}


def register_handler(command: str, handler: Callable) -> None:
    """Register a command handler.

    Args:
        command: The command name.
        handler: The handler function that takes params dict and returns result.
    """
    _handlers[command] = handler


def dispatch(command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dispatch a command to its registered handler.

    Args:
        command: The command name.
        params: Optional parameters dict.

    Returns:
        Response dict with 'status' and 'result' keys.
    """
    if command not in _handlers:
        return {
            "status": "error",
            "result": f"Unknown command: '{command}'. Available commands: {sorted(_handlers.keys())}",
        }

    try:
        handler = _handlers[command]
        result = handler(params or {})
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "result": f"{type(e).__name__}: {str(e)}"}


def get_registered_commands() -> list[str]:
    """Return list of all registered command names."""
    return sorted(_handlers.keys())
