"""Tests for asset library tools."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.file_ops import list_asset_libraries, list_assets, place_asset
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.file_ops.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_list_libraries(mock_conn):
    list_asset_libraries()
    assert _sent(mock_conn) == ("list_asset_libraries", {})


class TestListAssets:
    def test_whole_library(self, mock_conn):
        list_assets("Essentials")
        assert _sent(mock_conn) == ("list_assets", {"library": "Essentials"})

    def test_filtered(self, mock_conn):
        list_assets("User Library", asset_type="MATERIAL")
        assert _sent(mock_conn)[1] == {"library": "User Library", "asset_type": "MATERIAL"}

    @pytest.mark.parametrize("kwargs", [
        {"library": ""}, {"library": "a/../b"}, {"asset_type": "SCRIPT"},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            list_assets(**({"library": "Essentials"} | kwargs))


class TestPlaceAsset:
    def test_sends_relative_file(self, mock_conn):
        place_asset("User Library", "props/chairs.blend", "OBJECT", "Chair", link=True)
        assert _sent(mock_conn) == ("place_asset", {
            "library": "User Library", "file": "props/chairs.blend",
            "asset_type": "OBJECT", "name": "Chair", "link": True})

    @pytest.mark.parametrize("file", [
        "/etc/passwd.blend", "../outside.blend", "props/../../x.blend", "props/x.txt",
        "", "a\x00.blend", "C:\\\\x.blend", "props\\\\..\\\\..\\\\x.blend",
    ])
    def test_file_must_stay_inside_the_library(self, mock_conn, file):
        with pytest.raises(ValidationError):
            place_asset("User Library", file, "OBJECT", "Chair")
        mock_conn.send_command.assert_not_called()

    @pytest.mark.parametrize("kwargs", [
        {"asset_type": "TEXT"}, {"asset_name": "../x"}, {"link": "yes"},
    ])
    def test_bad_input(self, mock_conn, kwargs):
        args = {"library": "User Library", "file": "a.blend", "asset_type": "OBJECT",
                "asset_name": "Chair"} | kwargs
        with pytest.raises(ValidationError):
            place_asset(**args)
