"""Unit tests for sequencer tools: strips, sound, and video output."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.connection import BlenderConnection
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"success": True}}
    with patch("blenderwright.tools.sequencer.get_connection", return_value=mock):
        yield mock


@pytest.fixture
def frame(tmp_path):
    path = tmp_path / "f_0001.png"
    path.write_bytes(b"png")
    return str(path)


@pytest.fixture
def sound(tmp_path):
    path = tmp_path / "roar.mp3"
    path.write_bytes(b"mp3")
    return str(path)


class TestAddImageSequenceStrip:
    def test_sends_the_first_frame_and_placement(self, mock_conn, frame):
        from blenderwright.tools.sequencer import add_image_sequence_strip

        add_image_sequence_strip(frame, name="Launch", channel=3, frame_start=10)
        command, params = mock_conn.send_command.call_args[0]
        assert command == "add_image_sequence_strip"
        assert params["first_frame"].endswith("f_0001.png")
        assert params["name"] == "Launch"
        assert params["channel"] == 3
        assert params["frame_start"] == 10

    def test_defaults(self, mock_conn, frame):
        from blenderwright.tools.sequencer import add_image_sequence_strip

        add_image_sequence_strip(frame)
        params = mock_conn.send_command.call_args[0][1]
        assert params["channel"] == 1
        assert params["frame_start"] == 1
        assert params["name"] == ""

    def test_missing_file_is_refused(self, mock_conn, tmp_path):
        from blenderwright.tools.sequencer import add_image_sequence_strip

        with pytest.raises(ValidationError):
            add_image_sequence_strip(str(tmp_path / "nope_0001.png"))
        mock_conn.send_command.assert_not_called()

    def test_non_image_extension_is_refused(self, mock_conn, tmp_path):
        from blenderwright.tools.sequencer import add_image_sequence_strip

        script = tmp_path / "f_0001.py"
        script.write_text("x")
        with pytest.raises(ValidationError):
            add_image_sequence_strip(str(script))

    def test_relative_path_to_a_missing_file_is_refused(self, mock_conn):
        from blenderwright.tools.sequencer import add_image_sequence_strip

        with pytest.raises(ValidationError):
            add_image_sequence_strip("no_such_folder/f_0001.png")

    @pytest.mark.parametrize("channel", [0, 129, -1])
    def test_channel_out_of_range(self, mock_conn, frame, channel):
        from blenderwright.tools.sequencer import add_image_sequence_strip

        with pytest.raises(ValidationError):
            add_image_sequence_strip(frame, channel=channel)

    def test_unsafe_name_is_refused(self, mock_conn, frame):
        from blenderwright.tools.sequencer import add_image_sequence_strip

        with pytest.raises(ValidationError):
            add_image_sequence_strip(frame, name="bad;name")


class TestAddSoundStrip:
    def test_sends_sound_placement(self, mock_conn, sound):
        from blenderwright.tools.sequencer import add_sound_strip

        add_sound_strip(sound, name="Roar", channel=2, frame_start=1, start_offset=3.5, volume=1.3)
        command, params = mock_conn.send_command.call_args[0]
        assert command == "add_sound_strip"
        assert params["filepath"].endswith("roar.mp3")
        assert params["start_offset"] == 3.5
        assert params["volume"] == 1.3
        assert params["channel"] == 2

    def test_defaults(self, mock_conn, sound):
        from blenderwright.tools.sequencer import add_sound_strip

        add_sound_strip(sound)
        params = mock_conn.send_command.call_args[0][1]
        assert params["channel"] == 2
        assert params["start_offset"] == 0.0
        assert params["volume"] == 1.0

    def test_non_audio_extension_is_refused(self, mock_conn, frame):
        from blenderwright.tools.sequencer import add_sound_strip

        with pytest.raises(ValidationError):
            add_sound_strip(frame)

    def test_missing_file_is_refused(self, mock_conn, tmp_path):
        from blenderwright.tools.sequencer import add_sound_strip

        with pytest.raises(ValidationError):
            add_sound_strip(str(tmp_path / "nope.wav"))

    def test_negative_offset_is_refused(self, mock_conn, sound):
        from blenderwright.tools.sequencer import add_sound_strip

        with pytest.raises(ValidationError):
            add_sound_strip(sound, start_offset=-1.0)

    @pytest.mark.parametrize("volume", [-0.1, 100.1])
    def test_volume_out_of_range(self, mock_conn, sound, volume):
        from blenderwright.tools.sequencer import add_sound_strip

        with pytest.raises(ValidationError):
            add_sound_strip(sound, volume=volume)


class TestListAndRemove:
    def test_list_strips(self, mock_conn):
        from blenderwright.tools.sequencer import list_strips

        mock_conn.send_command.return_value = {"status": "ok", "result": []}
        assert list_strips() == []
        assert mock_conn.send_command.call_args[0][0] == "list_strips"

    def test_remove_strip(self, mock_conn):
        from blenderwright.tools.sequencer import remove_strip

        remove_strip("Launch")
        mock_conn.send_command.assert_called_once_with("remove_strip", {"strip_name": "Launch"})

    def test_remove_strip_unsafe_name(self, mock_conn):
        from blenderwright.tools.sequencer import remove_strip

        with pytest.raises(ValidationError):
            remove_strip("../x")


class TestRenderVideo:
    def test_defaults_to_mp4_with_aac(self, mock_conn):
        from blenderwright.tools.sequencer import render_video

        render_video("/tmp/out.mp4")
        command, params = mock_conn.send_command.call_args[0]
        assert command == "render_video"
        assert params["filepath"].endswith("out.mp4")
        assert params["container"] == "MPEG4"
        assert params["quality"] == "HIGH"
        assert params["audio_codec"] == "AAC"

    def test_waits_as_long_as_an_animation(self, mock_conn):
        from blenderwright.tools.sequencer import render_video

        render_video("/tmp/out.mp4")
        timeout = mock_conn.send_command.call_args.kwargs["timeout"]
        assert timeout == BlenderConnection.ANIMATION_TIMEOUT

    def test_webm_with_opus(self, mock_conn):
        from blenderwright.tools.sequencer import render_video

        render_video("/tmp/out.webm", container="WEBM", audio_codec="OPUS")
        params = mock_conn.send_command.call_args[0][1]
        assert params["container"] == "WEBM"
        assert params["audio_codec"] == "OPUS"

    def test_silent_video(self, mock_conn):
        from blenderwright.tools.sequencer import render_video

        render_video("/tmp/out.mp4", audio_codec="NONE")
        assert mock_conn.send_command.call_args[0][1]["audio_codec"] == "NONE"

    def test_extension_must_match_container(self, mock_conn):
        from blenderwright.tools.sequencer import render_video

        with pytest.raises(ValidationError, match="mp4"):
            render_video("/tmp/out.webm", container="MPEG4")

    def test_webm_refuses_aac(self, mock_conn):
        """Blender writes a broken file rather than failing on this pairing."""
        from blenderwright.tools.sequencer import render_video

        with pytest.raises(ValidationError, match="WEBM"):
            render_video("/tmp/out.webm", container="WEBM", audio_codec="AAC")

    def test_unknown_container(self, mock_conn):
        from blenderwright.tools.sequencer import render_video

        with pytest.raises(ValidationError):
            render_video("/tmp/out.avi", container="AVI")

    def test_unknown_quality(self, mock_conn):
        from blenderwright.tools.sequencer import render_video

        with pytest.raises(ValidationError):
            render_video("/tmp/out.mp4", quality="ULTRA")

    def test_relative_path_is_sent_as_an_absolute_one(self, mock_conn):
        """Blender would resolve a relative path against the .blend instead."""
        import os

        from blenderwright.tools.sequencer import render_video

        render_video("out.mp4")
        sent = mock_conn.send_command.call_args[0][1]["filepath"]
        assert os.path.isabs(sent)
        assert sent.endswith("out.mp4")


class TestBlenderErrors:
    def test_error_response_raises(self, mock_conn):
        from blenderwright.tools.sequencer import list_strips

        mock_conn.send_command.return_value = {"status": "error", "result": "boom"}
        with pytest.raises(RuntimeError, match="Blender error: boom"):
            list_strips()
