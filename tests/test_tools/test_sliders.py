"""Tests for sliders: named controls on an object that drive other properties.

A slider is a custom property with a range. Each property it moves gets a
driver that reads it through Blender's simple, Python-free expressions.
"""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.animation import add_slider, remove_slider, set_slider
from blenderwright.validators import ValidationError, validate_data_path


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.animation.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestCustomPropertyPaths:
    @pytest.mark.parametrize("path", ['["pupil_size"]', '["Door Open"]', 'data["x"]'])
    def test_custom_property_paths_pass(self, path):
        assert validate_data_path(path) == path

    @pytest.mark.parametrize("path", ['["a"', '[""]', '["a"]()', '["__class__"]x', "[pupil]"])
    def test_broken_ones_still_fail(self, path):
        with pytest.raises(ValidationError):
            validate_data_path(path)


class TestAddSlider:
    def test_sends_the_slider_and_its_drives(self, mock_conn):
        add_slider("Door", "Open", min=0, max=1, default=0.25, description="Swing the door",
                   drives=[{"data_path": "rotation_euler", "index": 2, "expression": "value * 1.57"}])
        cmd, params = _sent(mock_conn)
        assert cmd == "add_slider"
        assert params == {
            "object_name": "Door", "name": "Open", "min": 0.0, "max": 1.0, "default": 0.25,
            "description": "Swing the door",
            "drives": [{"object": "Door", "data_path": "rotation_euler", "index": 2,
                        "expression": "value * 1.57"}],
        }

    def test_a_drive_can_target_another_object(self, mock_conn):
        add_slider("Rig", "Smile", drives=[
            {"object": "Head", "data_path": 'data.shape_keys.key_blocks["Smile"].value'}])
        drive = _sent(mock_conn)[1]["drives"][0]
        assert drive == {"object": "Head", "data_path": 'data.shape_keys.key_blocks["Smile"].value',
                         "index": -1, "expression": "value"}

    def test_no_drives_is_just_a_slider(self, mock_conn):
        add_slider("Rig", "Mood")
        assert _sent(mock_conn)[1]["drives"] == []

    @pytest.mark.parametrize("name", ["", '"x"', "a]b", "9lives", "x" * 64, "a\nb", "__class__"])
    def test_bad_names_are_refused(self, mock_conn, name):
        with pytest.raises(ValidationError):
            add_slider("Rig", name)
        mock_conn.send_command.assert_not_called()

    def test_range_must_be_a_range(self, mock_conn):
        with pytest.raises(ValidationError):
            add_slider("Rig", "x", min=1, max=1)

    def test_default_must_sit_in_the_range(self, mock_conn):
        with pytest.raises(ValidationError):
            add_slider("Rig", "x", min=0, max=1, default=2)

    @pytest.mark.parametrize("expression", ["__import__('os')", "value ** 2", "x * 2", "value.real"])
    def test_drive_expressions_are_simple_and_use_only_value(self, mock_conn, expression):
        with pytest.raises(ValidationError):
            add_slider("Rig", "x", drives=[{"data_path": "location", "expression": expression}])

    def test_drive_paths_are_checked(self, mock_conn):
        with pytest.raises(ValidationError):
            add_slider("Rig", "x", drives=[{"data_path": "location()"}])

    def test_too_many_drives(self, mock_conn):
        with pytest.raises(ValidationError):
            add_slider("Rig", "x", drives=[{"data_path": "location"}] * 33)


class TestSetAndRemove:
    def test_set_slider(self, mock_conn):
        set_slider("Rig", "Open", 0.5)
        assert _sent(mock_conn) == ("set_slider", {"object_name": "Rig", "name": "Open", "value": 0.5})

    def test_remove_slider(self, mock_conn):
        remove_slider("Rig", "Open")
        assert _sent(mock_conn) == ("remove_slider", {"object_name": "Rig", "name": "Open"})

    def test_names_checked_here_too(self, mock_conn):
        with pytest.raises(ValidationError):
            set_slider("Rig", '"x"', 1)
        with pytest.raises(ValidationError):
            remove_slider("Rig", "")
