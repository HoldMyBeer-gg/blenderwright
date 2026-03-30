"""Thread-safe execution bridge for Blender's main thread.

Blender's Python API (bpy) can only be called from the main thread.
This module provides a queue-based mechanism to execute functions
on the main thread from background threads.
"""

import queue
from typing import Any, Callable

import bpy

# Command queue: background threads put work here
_command_queue: queue.Queue = queue.Queue()

# Response queues: keyed by request id
_response_queues: dict[int, queue.Queue] = {}
_next_id = 0


def _get_next_id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


def execute_on_main_thread(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Execute a function on Blender's main thread and return the result.

    This blocks the calling thread until the function completes on the main thread.

    Args:
        func: The function to execute.
        *args: Positional arguments.
        **kwargs: Keyword arguments.

    Returns:
        The return value of the function.

    Raises:
        Exception: Any exception raised by the function.
    """
    request_id = _get_next_id()
    response_queue: queue.Queue = queue.Queue()
    _response_queues[request_id] = response_queue

    _command_queue.put((request_id, func, args, kwargs))

    # Block until the main thread processes our request
    success, result = response_queue.get(timeout=60.0)
    del _response_queues[request_id]

    if success:
        return result
    else:
        raise result


def _process_queue() -> float:
    """Timer callback that processes the command queue on the main thread.

    Returns:
        Interval in seconds before next call (0.01 = 10ms).
    """
    try:
        while not _command_queue.empty():
            request_id, func, args, kwargs = _command_queue.get_nowait()
            response_queue = _response_queues.get(request_id)
            if response_queue is None:
                continue
            try:
                result = func(*args, **kwargs)
                response_queue.put((True, result))
            except Exception as e:
                response_queue.put((False, e))
    except queue.Empty:
        pass
    return 0.01  # Run again in 10ms


def register_timer():
    """Register the main-thread timer with Blender."""
    if not bpy.app.timers.is_registered(_process_queue):
        bpy.app.timers.register(_process_queue, persistent=True)


def unregister_timer():
    """Unregister the main-thread timer."""
    if bpy.app.timers.is_registered(_process_queue):
        bpy.app.timers.unregister(_process_queue)
