"""Thread-safe execution bridge for Blender's main thread.

Blender's Python API (bpy) can only be called from the main thread.
This module provides a queue-based mechanism to execute functions
on the main thread from background threads.
"""

import queue
import threading
from typing import Any, Callable

import bpy

# Seconds a queued command may wait for the main thread to pick it up. Kept
# under the client's 30s socket timeout so the client hears "busy" first.
START_TIMEOUT = 20.0

# Command queue: background threads put work here
_command_queue: queue.Queue = queue.Queue()

# Response queues: keyed by request id
_response_queues: dict[int, queue.Queue] = {}
# Set once the main thread has begun running a request
_started: dict[int, threading.Event] = {}
_state_lock = threading.Lock()
_next_id = 0


class MainThreadBusyError(Exception):
    """The main thread did not start a queued command in time."""


def _get_next_id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


def execute_on_main_thread(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Execute a function on Blender's main thread and return the result.

    This blocks the calling thread until the function completes on the main
    thread. Once the function has started it is waited for however long it
    takes, so a render is never cut off. A function the main thread has not
    picked up within START_TIMEOUT is cancelled instead, and will not run.

    Args:
        func: The function to execute.
        *args: Positional arguments.
        **kwargs: Keyword arguments.

    Returns:
        The return value of the function.

    Raises:
        MainThreadBusyError: The main thread never started the function.
        Exception: Any exception raised by the function.
    """
    response_queue: queue.Queue = queue.Queue()
    started = threading.Event()
    with _state_lock:
        request_id = _get_next_id()
        _response_queues[request_id] = response_queue
        _started[request_id] = started

    _command_queue.put((request_id, func, args, kwargs))

    try:
        try:
            success, result = response_queue.get(timeout=START_TIMEOUT)
        except queue.Empty:
            with _state_lock:
                if not started.is_set():
                    # Unregistering makes _process_queue skip the request.
                    del _response_queues[request_id]
                    raise MainThreadBusyError(
                        "Blender's main thread is busy and did not start the command."
                    ) from None
            success, result = response_queue.get()
    finally:
        with _state_lock:
            _response_queues.pop(request_id, None)
            _started.pop(request_id, None)

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
            with _state_lock:
                response_queue = _response_queues.get(request_id)
                if response_queue is None:
                    continue  # cancelled while it waited
                _started[request_id].set()
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
