"""The MCP side sends the token with every command and fails loud on rejection."""

import json
import struct

import pytest

from blenderwright.connection import BlenderAuthError
from blenderwright.connection import BlenderConnection
from tests.conftest import TEST_TOKEN

UNAUTHORIZED = {"status": "error", "code": "unauthorized", "result": "Bad token"}


def _frames(*responses):
    """recv() chunks for a sequence of length-prefixed JSON replies."""
    chunks = []
    for r in responses:
        raw = json.dumps(r).encode("utf-8")
        chunks += [struct.pack(">I", len(raw)), raw]
    return chunks


def _sent_messages(mock_socket):
    out = []
    for call in mock_socket.sendall.call_args_list:
        data = call[0][0]
        out.append(json.loads(data[4:].decode("utf-8")))
    return out


def test_every_command_carries_the_token(mock_socket):
    mock_socket.recv.side_effect = _frames({"status": "ok", "result": {}})
    BlenderConnection().send_command("get_scene_info")
    assert _sent_messages(mock_socket)[0]["token"] == TEST_TOKEN


def test_restarted_blender_is_picked_up(mock_socket, token_file):
    """Blender restarted with a new token: re-read the file once and carry on."""
    conn = BlenderConnection()
    mock_socket.recv.side_effect = _frames({"status": "ok", "result": {}})
    conn.send_command("get_scene_info")

    token_file.write_text("b" * 64)
    mock_socket.recv.side_effect = _frames(UNAUTHORIZED, {"status": "ok", "result": {}})
    response = conn.send_command("get_scene_info")

    assert response["status"] == "ok"
    assert _sent_messages(mock_socket)[-1]["token"] == "b" * 64


def test_rejected_token_fails_loud(mock_socket, token_file):
    mock_socket.recv.side_effect = _frames(UNAUTHORIZED, UNAUTHORIZED, UNAUTHORIZED)
    with pytest.raises(BlenderAuthError) as err:
        BlenderConnection().send_command("delete_object", {"object_name": "Cube"})
    message = str(err.value)
    assert "rejected" in message.lower()
    assert str(token_file) in message


def test_rejected_token_is_not_retried_forever(mock_socket, token_file):
    token_file.write_text("c" * 64)
    mock_socket.recv.side_effect = _frames(*[UNAUTHORIZED] * 10)
    with pytest.raises(BlenderAuthError):
        BlenderConnection().send_command("get_scene_info")
    assert mock_socket.sendall.call_count <= 2


def test_missing_token_file_fails_loud(mock_socket, token_file):
    token_file.unlink()
    with pytest.raises(BlenderAuthError, match="Start Server"):
        BlenderConnection().send_command("get_scene_info")
