"""Tests for the main-thread bridge: long commands and busy cancellation."""

import importlib.util
import os
import threading
import time

import pytest


def _load_thread_safety():
    """Load addon/thread_safety.py directly without importing addon/__init__.py."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "addon", "thread_safety.py",
    )
    spec = importlib.util.spec_from_file_location("thread_safety_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def ts():
    return _load_thread_safety()


def _call_in_thread(ts, func):
    """Run execute_on_main_thread on a worker thread, as the TCP server does."""
    outcome = {}

    def worker():
        try:
            outcome["result"] = ts.execute_on_main_thread(func)
        except Exception as e:  # noqa: BLE001
            outcome["error"] = e

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread, outcome


def _wait_until_queued(ts):
    deadline = time.monotonic() + 2.0
    while ts._command_queue.empty():
        assert time.monotonic() < deadline, "command was never queued"
        time.sleep(0.001)


class TestExecuteOnMainThread:
    def test_returns_the_function_result(self, ts):
        thread, outcome = _call_in_thread(ts, lambda: 42)
        _wait_until_queued(ts)
        ts._process_queue()
        thread.join(2.0)
        assert outcome == {"result": 42}

    def test_reraises_the_function_error(self, ts):
        def boom():
            raise ValueError("bad input")

        thread, outcome = _call_in_thread(ts, boom)
        _wait_until_queued(ts)
        ts._process_queue()
        thread.join(2.0)
        assert isinstance(outcome["error"], ValueError)

    def test_running_command_outlives_the_start_timeout(self, ts):
        """A render that has started must be waited for, however long it takes."""
        ts.START_TIMEOUT = 0.05

        def slow_render():
            time.sleep(0.3)
            return "rendered"

        thread, outcome = _call_in_thread(ts, slow_render)
        _wait_until_queued(ts)
        ts._process_queue()
        thread.join(2.0)
        assert outcome == {"result": "rendered"}

    def test_unstarted_command_is_reported_busy(self, ts):
        ts.START_TIMEOUT = 0.05
        thread, outcome = _call_in_thread(ts, lambda: 42)
        thread.join(2.0)
        assert isinstance(outcome["error"], ts.MainThreadBusyError)

    def test_cancelled_command_never_runs(self, ts):
        """The client was told busy and will resend, so a late run would duplicate it."""
        ts.START_TIMEOUT = 0.05
        ran = []
        thread, _ = _call_in_thread(ts, lambda: ran.append(True))
        thread.join(2.0)
        ts._process_queue()
        assert ran == []

    def test_no_request_state_is_left_behind(self, ts):
        ts.START_TIMEOUT = 0.05
        thread, _ = _call_in_thread(ts, lambda: 42)
        thread.join(2.0)
        ts._process_queue()

        thread, _ = _call_in_thread(ts, lambda: 42)
        _wait_until_queued(ts)
        ts._process_queue()
        thread.join(2.0)

        assert ts._response_queues == {}
        assert ts._started == {}
