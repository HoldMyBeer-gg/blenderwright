"""Tests for blend_ai.connection."""

import json
import struct
import pytest

from blend_ai.connection import BlenderConnection, BlenderConnectionError


class TestConnect:
    def test_connect_success(self, mock_socket):
        conn = BlenderConnection()
        conn.connect()
        mock_socket.settimeout.assert_called_once_with(30.0)
        mock_socket.connect.assert_called_once_with(("127.0.0.1", 9876))
        assert conn.is_connected

    def test_connect_refused(self, mock_socket):
        mock_socket.connect.side_effect = ConnectionRefusedError("refused")
        conn = BlenderConnection()
        with pytest.raises(BlenderConnectionError, match="Cannot connect to Blender"):
            conn.connect()

    def test_connect_os_error(self, mock_socket):
        mock_socket.connect.side_effect = OSError("network error")
        conn = BlenderConnection()
        with pytest.raises(BlenderConnectionError, match="Cannot connect to Blender"):
            conn.connect()

    def test_connect_already_connected_is_noop(self, mock_socket):
        conn = BlenderConnection()
        conn.connect()
        # Second call should not create a new socket
        mock_socket.connect.assert_called_once()
        conn.connect()
        mock_socket.connect.assert_called_once()


class TestDisconnect:
    def test_disconnect_closes_socket(self, mock_socket):
        conn = BlenderConnection()
        conn.connect()
        assert conn.is_connected
        conn.disconnect()
        mock_socket.close.assert_called_once()
        assert not conn.is_connected

    def test_disconnect_when_not_connected_is_noop(self):
        conn = BlenderConnection()
        conn.disconnect()  # Should not raise
        assert not conn.is_connected

    def test_disconnect_handles_os_error(self, mock_socket):
        conn = BlenderConnection()
        conn.connect()
        mock_socket.close.side_effect = OSError("close failed")
        conn.disconnect()  # Should not raise
        assert not conn.is_connected


class TestSendCommand:
    def _make_response_bytes(self, response_dict: dict) -> bytes:
        """Helper: create a length-prefixed JSON response."""
        payload = json.dumps(response_dict).encode("utf-8")
        return struct.pack(">I", len(payload)) + payload

    def test_send_command_success(self, mock_socket):
        response = {"status": "ok", "result": {"name": "Cube"}}
        raw = self._make_response_bytes(response)

        # Mock recv to return header then payload in chunks
        mock_socket.recv.side_effect = [raw[:4], raw[4:]]

        conn = BlenderConnection()
        conn.connect()
        result = conn.send_command("get_object", {"name": "Cube"})

        assert result == response
        # Verify sendall was called with length-prefixed JSON
        call_args = mock_socket.sendall.call_args[0][0]
        # First 4 bytes are the length header
        sent_payload = json.loads(call_args[4:].decode("utf-8"))
        assert sent_payload["command"] == "get_object"
        assert sent_payload["params"] == {"name": "Cube"}

    def test_send_command_not_connected_auto_connects(self, mock_socket):
        response = {"status": "ok", "result": {}}
        raw = self._make_response_bytes(response)
        mock_socket.recv.side_effect = [raw[:4], raw[4:]]

        conn = BlenderConnection()
        # Don't call connect() explicitly
        result = conn.send_command("ping")
        assert result["status"] == "ok"
        # connect was called implicitly
        mock_socket.connect.assert_called_once()

    def test_send_command_without_params(self, mock_socket):
        response = {"status": "ok", "result": "pong"}
        raw = self._make_response_bytes(response)
        mock_socket.recv.side_effect = [raw[:4], raw[4:]]

        conn = BlenderConnection()
        conn.connect()
        conn.send_command("ping")

        call_args = mock_socket.sendall.call_args[0][0]
        sent_payload = json.loads(call_args[4:].decode("utf-8"))
        assert "params" not in sent_payload

    def test_send_command_invalid_response(self, mock_socket):
        """Non-dict JSON response raises error."""
        payload = json.dumps([1, 2, 3]).encode("utf-8")
        raw = struct.pack(">I", len(payload)) + payload
        mock_socket.recv.side_effect = [raw[:4], raw[4:]]

        conn = BlenderConnection()
        conn.connect()
        with pytest.raises(BlenderConnectionError, match="Invalid response format"):
            conn.send_command("bad_command")

    def test_send_command_communication_error(self, mock_socket):
        # recv raises OSError persistently (send_command retries once)
        mock_socket.recv.side_effect = OSError("broken pipe")
        conn = BlenderConnection()
        conn.connect()
        with pytest.raises(BlenderConnectionError, match="Connection to Blender lost"):
            conn.send_command("test")
        # Should have disconnected after error
        assert not conn.is_connected


class TestRecvTooLarge:
    def test_recv_too_large_raises(self, mock_socket):
        """Response over 100MB raises error."""
        # Create a header claiming a payload of 200MB
        huge_length = 200 * 1024 * 1024
        header = struct.pack(">I", huge_length)
        # Provide header for both attempts (send_command retries once)
        mock_socket.recv.side_effect = [header, header]

        conn = BlenderConnection()
        conn.connect()
        with pytest.raises(BlenderConnectionError, match="Connection to Blender lost"):
            conn.send_command("huge")


class TestBusyRetry:
    def _make_response_bytes(self, response_dict: dict) -> bytes:
        payload = json.dumps(response_dict).encode("utf-8")
        return struct.pack(">I", len(payload)) + payload

    def test_busy_then_ok_retries(self, mock_socket):
        """Client retries when server returns busy, succeeds when render finishes."""
        busy = self._make_response_bytes({"status": "busy", "result": "rendering"})
        ok = self._make_response_bytes({"status": "ok", "result": {"done": True}})

        mock_socket.recv.side_effect = [
            busy[:4], busy[4:],   # initial: busy
            busy[:4], busy[4:],   # retry 1: still busy
            ok[:4], ok[4:],       # retry 2: ok
        ]

        conn = BlenderConnection()
        conn.BUSY_RETRY_DELAY = 0.01  # speed up test
        conn.connect()
        result = conn.send_command("test")

        assert result["status"] == "ok"
        assert result["result"]["done"] is True

    def test_busy_timeout_raises(self, mock_socket):
        """Client raises after max retries exhausted."""
        busy = self._make_response_bytes({"status": "busy", "result": "rendering"})

        # Return busy for initial + all retries
        mock_socket.recv.side_effect = [busy[:4], busy[4:]] * 5

        conn = BlenderConnection()
        conn.BUSY_RETRY_DELAY = 0.01
        conn.BUSY_MAX_RETRIES = 3
        conn.connect()

        with pytest.raises(BlenderConnectionError, match="busy rendering for too long"):
            conn.send_command("test")

    def test_busy_immediate_ok(self, mock_socket):
        """Non-busy response is returned immediately without retrying."""
        ok = self._make_response_bytes({"status": "ok", "result": "fast"})
        mock_socket.recv.side_effect = [ok[:4], ok[4:]]

        conn = BlenderConnection()
        conn.connect()
        result = conn.send_command("test")

        assert result["status"] == "ok"


class TestIsConnected:
    def test_not_connected_initially(self):
        conn = BlenderConnection()
        assert not conn.is_connected

    def test_connected_after_connect(self, mock_socket):
        conn = BlenderConnection()
        conn.connect()
        assert conn.is_connected

    def test_not_connected_after_disconnect(self, mock_socket):
        conn = BlenderConnection()
        conn.connect()
        conn.disconnect()
        assert not conn.is_connected


class TestContextManager:
    def test_enter_connects(self, mock_socket):
        conn = BlenderConnection()
        result = conn.__enter__()
        assert result is conn
        assert conn.is_connected

    def test_exit_disconnects(self, mock_socket):
        conn = BlenderConnection()
        conn.__enter__()
        conn.__exit__(None, None, None)
        assert not conn.is_connected
        mock_socket.close.assert_called_once()

    def test_with_statement(self, mock_socket):
        with BlenderConnection() as conn:
            assert conn.is_connected
        assert not conn.is_connected
