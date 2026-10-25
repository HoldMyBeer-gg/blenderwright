"""Tool-side tests for add_sequencer_strip, set_strip_property and add_strip_fade.
Behaviour (rendered pixels): tests_live/test_sequencer.py."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.sequencer import add_sequencer_strip, add_strip_fade, set_strip_property
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.sequencer.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestAddSequencerStrip:
    def test_text(self, mock_conn):
        add_sequencer_strip("TEXT", text="Hello", name="Title", channel=2, length=48,
                            font_size=80, color=[1, 1, 0])
        assert _sent(mock_conn) == ("add_sequencer_strip", {
            "kind": "TEXT", "name": "Title", "channel": 2, "frame_start": 1, "length": 48,
            "text": "Hello", "font_size": 80, "color": [1, 1, 0, 1.0]})

    def test_color(self, mock_conn):
        add_sequencer_strip("COLOR", color=[1, 0, 0])
        assert _sent(mock_conn)[1]["color"] == [1, 0, 0]

    def test_movie(self, mock_conn, tmp_path):
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"x")
        add_sequencer_strip("MOVIE", filepath=str(clip))
        assert _sent(mock_conn)[1]["filepath"] == str(clip.resolve())

    @pytest.mark.parametrize("kwargs", [
        {"kind": "SCENE"},
        {"kind": "TEXT"},
        {"kind": "TEXT", "text": "x" * 2001},
        {"kind": "COLOR", "color": [2, 0, 0]},
        {"kind": "MOVIE"},
        {"kind": "MOVIE", "filepath": "/etc/passwd"},
        {"kind": "COLOR", "channel": 0},
        {"kind": "COLOR", "length": 0},
        {"kind": "TEXT", "text": "a", "font_size": 0},
        {"kind": "COLOR", "name": "../x"},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            add_sequencer_strip(**kwargs)
        mock_conn.send_command.assert_not_called()


class TestSetStripProperty:
    def test_settings_transform_and_crop(self, mock_conn):
        set_strip_property("Title", settings={"blend_alpha": 0.5},
                           transform={"offset_x": 100, "scale_x": 2}, crop={"min_x": 10})
        assert _sent(mock_conn) == ("set_strip_property", {
            "strip_name": "Title", "settings": {"blend_alpha": 0.5},
            "transform": {"offset_x": 100, "scale_x": 2}, "crop": {"min_x": 10}})

    @pytest.mark.parametrize("kwargs", [
        {},
        {"settings": {"__class__": 1}},
        {"settings": {"text": ["a"]}},
        {"transform": {"origin": 1}},
        {"crop": {"top": 1}},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            set_strip_property("Title", **kwargs)


class TestAddStripFade:
    def test_in_and_out(self, mock_conn):
        add_strip_fade("Title", fade_in=12, fade_out=24)
        assert _sent(mock_conn) == ("add_strip_fade",
                                    {"strip_name": "Title", "fade_in": 12, "fade_out": 24})

    @pytest.mark.parametrize("kwargs", [{}, {"fade_in": -1}, {"fade_out": 2_000_000}])
    def test_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            add_strip_fade("Title", **kwargs)
