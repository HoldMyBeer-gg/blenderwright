"""Tests for set_light_group and manage_aov."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.render_settings import manage_aov, set_light_group
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.render_settings.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestSetLightGroup:
    def test_assign_objects(self, mock_conn):
        set_light_group("Key", objects=["Sun", "Lamp"])
        assert _sent(mock_conn) == ("set_light_group", {
            "group": "Key", "objects": ["Sun", "Lamp"], "world": False, "remove": False})

    def test_world_only(self, mock_conn):
        set_light_group("Sky", world=True)
        assert _sent(mock_conn)[1] == {"group": "Sky", "objects": [], "world": True,
                                       "remove": False}

    def test_remove(self, mock_conn):
        set_light_group("Key", remove=True)
        assert _sent(mock_conn)[1]["remove"] is True

    @pytest.mark.parametrize("kwargs", [
        {"group": ""},
        {"group": "../x"},
        {"objects": "Sun"},
        {"objects": ["../x"]},
        {"objects": ["a"] * 1001},
        {"world": "yes"},
        {"remove": 1},
        {"remove": True, "objects": ["Sun"]},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        args = {"group": "Key"} | kwargs
        with pytest.raises(ValidationError):
            set_light_group(**args)
        mock_conn.send_command.assert_not_called()


class TestManageAOV:
    def test_list(self, mock_conn):
        manage_aov("LIST")
        assert _sent(mock_conn) == ("manage_aov", {"action": "LIST"})

    def test_add(self, mock_conn):
        manage_aov("ADD", name="mask", type="VALUE")
        assert _sent(mock_conn)[1] == {"action": "ADD", "name": "mask", "type": "VALUE"}

    def test_remove(self, mock_conn):
        manage_aov("REMOVE", name="mask")
        assert _sent(mock_conn)[1] == {"action": "REMOVE", "name": "mask"}

    @pytest.mark.parametrize("kwargs", [
        {"action": "RENAME", "name": "a"},
        {"action": "ADD"},
        {"action": "ADD", "name": "a", "type": "VECTOR"},
        {"action": "REMOVE", "name": "../x"},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            manage_aov(**kwargs)
