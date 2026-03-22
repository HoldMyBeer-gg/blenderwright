"""Tests for addon.dispatcher."""

import pytest
from addon.dispatcher import register_handler, dispatch, get_registered_commands, _handlers


@pytest.fixture(autouse=True)
def _clear_handlers():
    """Clear the handler registry before and after each test."""
    _handlers.clear()
    yield
    _handlers.clear()


class TestRegisterHandler:
    def test_register_handler(self):
        def my_handler(params):
            return {"done": True}

        register_handler("my_command", my_handler)
        result = dispatch("my_command")
        assert result["status"] == "ok"
        assert result["result"] == {"done": True}

    def test_register_multiple_handlers(self):
        register_handler("cmd_a", lambda p: "a")
        register_handler("cmd_b", lambda p: "b")
        assert len(get_registered_commands()) == 2


class TestDispatchUnknownCommand:
    def test_dispatch_unknown_command(self):
        register_handler("known_cmd", lambda p: "ok")
        result = dispatch("unknown_cmd")
        assert result["status"] == "error"
        assert "Unknown command" in result["result"]
        assert "unknown_cmd" in result["result"]
        # Should list available commands
        assert "known_cmd" in result["result"]

    def test_dispatch_unknown_with_no_handlers(self):
        result = dispatch("anything")
        assert result["status"] == "error"
        assert "Unknown command" in result["result"]


class TestDispatchHandlerException:
    def test_dispatch_handler_exception(self):
        def bad_handler(params):
            raise ValueError("something went wrong")

        register_handler("bad_cmd", bad_handler)
        result = dispatch("bad_cmd")
        assert result["status"] == "error"
        assert "ValueError" in result["result"]
        assert "something went wrong" in result["result"]

    def test_dispatch_handler_runtime_error(self):
        def crash_handler(params):
            raise RuntimeError("crash")

        register_handler("crash", crash_handler)
        result = dispatch("crash")
        assert result["status"] == "error"
        assert "RuntimeError" in result["result"]


class TestGetRegisteredCommands:
    def test_get_registered_commands_empty(self):
        assert get_registered_commands() == []

    def test_get_registered_commands_sorted(self):
        register_handler("zebra", lambda p: None)
        register_handler("alpha", lambda p: None)
        register_handler("middle", lambda p: None)
        assert get_registered_commands() == ["alpha", "middle", "zebra"]


class TestDispatchWithParams:
    def test_dispatch_with_params(self):
        def echo_handler(params):
            return params

        register_handler("echo", echo_handler)
        result = dispatch("echo", {"key": "value", "num": 42})
        assert result["status"] == "ok"
        assert result["result"] == {"key": "value", "num": 42}

    def test_params_passed_correctly(self):
        received = {}

        def capture_handler(params):
            received.update(params)
            return "captured"

        register_handler("capture", capture_handler)
        dispatch("capture", {"x": 1, "y": 2})
        assert received == {"x": 1, "y": 2}


class TestDispatchWithoutParams:
    def test_dispatch_without_params_defaults_to_empty_dict(self):
        received_params = []

        def track_handler(params):
            received_params.append(params)
            return "ok"

        register_handler("track", track_handler)
        dispatch("track")
        assert received_params == [{}]

    def test_dispatch_with_none_params(self):
        received_params = []

        def track_handler(params):
            received_params.append(params)
            return "ok"

        register_handler("track", track_handler)
        dispatch("track", None)
        assert received_params == [{}]
