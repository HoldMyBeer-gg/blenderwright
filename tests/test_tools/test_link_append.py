"""Tests for reusing .blend content: list, link/append, collection instances."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.collections import create_collection_instance, make_instances_real
from blenderwright.tools.file_ops import (
    ALLOWED_LINK_TYPES,
    link_or_append,
    list_blend_contents,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def blend(tmp_path):
    path = tmp_path / "kit.blend"
    path.write_bytes(b"BLENDER")
    return str(path)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.file_ops.get_connection", return_value=mock), \
            patch("blenderwright.tools.collections.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_link_types():
    assert ALLOWED_LINK_TYPES == {"OBJECT", "COLLECTION", "MATERIAL", "NODE_GROUP",
                                  "WORLD", "MESH"}


class TestListBlendContents:
    def test_sends_path(self, mock_conn, blend):
        list_blend_contents(blend)
        assert _sent(mock_conn) == ("list_blend_contents", {"filepath": blend})

    @pytest.mark.parametrize("name", ["kit.py", "kit.fbx"])
    def test_only_blend_files(self, mock_conn, tmp_path, name):
        path = tmp_path / name
        path.write_text("x")
        with pytest.raises(ValidationError):
            list_blend_contents(str(path))

    def test_must_exist(self, mock_conn, tmp_path):
        with pytest.raises(ValidationError):
            list_blend_contents(str(tmp_path / "missing.blend"))


class TestLinkOrAppend:
    def test_append_objects(self, mock_conn, blend):
        link_or_append(blend, "OBJECT", ["Cone", "Cone", "Lamp"])
        assert _sent(mock_conn) == ("link_or_append", {
            "filepath": blend, "data_type": "OBJECT", "names": ["Cone", "Lamp"],
            "link": False})

    def test_link_collection(self, mock_conn, blend):
        link_or_append(blend, "COLLECTION", ["Props"], link=True)
        assert _sent(mock_conn)[1]["link"] is True

    @pytest.mark.parametrize("args", [
        ("SCRIPT", ["x"]), ("TEXT", ["x"]), ("OBJECT", []), ("OBJECT", "Cone"),
        ("OBJECT", ["a/b"]), ("OBJECT", ["x"] * 101),
    ])
    def test_rejects(self, mock_conn, blend, args):
        with pytest.raises(ValidationError):
            link_or_append(blend, *args)
        mock_conn.send_command.assert_not_called()


class TestCollectionInstances:
    def test_instance(self, mock_conn):
        create_collection_instance("Props", name="Props_A", location=[1, 2, 0],
                                   rotation=[0, 0, 1.57], scale=[2, 2, 2])
        assert _sent(mock_conn) == ("create_collection_instance", {
            "collection_name": "Props", "name": "Props_A", "location": [1.0, 2.0, 0.0],
            "rotation": [0.0, 0.0, 1.57], "scale": [2.0, 2.0, 2.0]})

    def test_instance_defaults(self, mock_conn):
        create_collection_instance("Props")
        assert _sent(mock_conn)[1] == {"collection_name": "Props", "name": "",
                                       "location": [0.0, 0.0, 0.0],
                                       "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}

    @pytest.mark.parametrize("kwargs", [{"location": [0, 0]}, {"scale": [0, 1, 1]},
                                        {"location": [0, float("nan"), 0]},
                                        {"name": "a/b"}])
    def test_instance_rejects(self, mock_conn, kwargs):
        with pytest.raises(ValidationError):
            create_collection_instance("Props", **kwargs)

    def test_make_real(self, mock_conn):
        make_instances_real("Props_A", keep_hierarchy=True)
        assert _sent(mock_conn) == ("make_instances_real",
                                    {"object_name": "Props_A", "keep_hierarchy": True})
