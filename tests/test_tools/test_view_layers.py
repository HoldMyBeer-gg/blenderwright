"""Tests for manage_view_layer and set_layer_collection."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.collections import (
    ALLOWED_VIEW_LAYER_ACTIONS,
    manage_view_layer,
    set_layer_collection,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.collections.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_actions():
    assert ALLOWED_VIEW_LAYER_ACTIONS == {"LIST", "ADD", "REMOVE", "RENAME", "SET_ACTIVE",
                                          "SET"}


class TestManageViewLayer:
    def test_list(self, mock_conn):
        manage_view_layer("LIST")
        assert _sent(mock_conn) == ("manage_view_layer", {"action": "LIST"})

    def test_add(self, mock_conn):
        manage_view_layer("ADD", view_layer="Foreground")
        assert _sent(mock_conn)[1] == {"action": "ADD", "view_layer": "Foreground"}

    def test_rename(self, mock_conn):
        manage_view_layer("RENAME", view_layer="ViewLayer", new_name="Beauty")
        assert _sent(mock_conn)[1]["new_name"] == "Beauty"

    def test_set_overrides(self, mock_conn):
        manage_view_layer("SET", view_layer="Clay", material_override="Clay",
                          world_override="", use_for_render=False)
        assert _sent(mock_conn)[1] == {"action": "SET", "view_layer": "Clay",
                                       "material_override": "Clay", "world_override": "",
                                       "use_for_render": False}

    @pytest.mark.parametrize("kwargs", [
        {"action": "COPY", "view_layer": "A"},
        {"action": "ADD"},
        {"action": "RENAME", "view_layer": "A"},
        {"action": "SET", "view_layer": "A"},
        {"action": "SET", "view_layer": "A", "material_override": "../x"},
        {"action": "SET", "view_layer": "A", "use_for_render": "no"},
        {"action": "REMOVE", "view_layer": "../x"},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            manage_view_layer(**kwargs)
        mock_conn.send_command.assert_not_called()


class TestSetLayerCollection:
    def test_only_given_flags(self, mock_conn):
        set_layer_collection("Background", holdout=True)
        assert _sent(mock_conn) == ("set_layer_collection",
                                    {"collection_name": "Background", "holdout": True})

    def test_on_another_layer(self, mock_conn):
        set_layer_collection("Props", view_layer="Foreground", exclude=True,
                             indirect_only=False)
        assert _sent(mock_conn)[1] == {"collection_name": "Props", "view_layer": "Foreground",
                                       "exclude": True, "indirect_only": False}

    def test_nothing_refused(self, mock_conn):
        with pytest.raises(ValidationError, match="at least one"):
            set_layer_collection("Props")

    def test_flags_must_be_bool(self, mock_conn):
        with pytest.raises(ValidationError):
            set_layer_collection("Props", exclude="yes")
