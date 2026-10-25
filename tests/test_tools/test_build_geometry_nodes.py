"""Tests for build_geometry_nodes and get_geometry_node_tree (tool side)."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.geometry_nodes import (
    ALLOWED_INTERFACE_TYPES,
    MAX_SPEC_LINKS,
    MAX_SPEC_NODES,
    build_geometry_nodes,
    get_geometry_node_tree,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.geometry_nodes.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


GRID_SPEC = {
    "inputs": [{"name": "Size", "type": "FLOAT", "default": 4.0, "min": 0.1, "max": 50}],
    "nodes": [
        {"name": "grid", "type": "GeometryNodeMeshGrid", "location": [-200, 0],
         "inputs": {"Vertices X": 20, "Vertices Y": 20}},
        {"name": "wave", "type": "ShaderNodeMath", "settings": {"operation": "SINE"}},
        {"name": "offset", "type": "GeometryNodeSetPosition"},
    ],
    "links": [
        ["Group Input", "Size", "grid", "Size X"],
        ["grid", "Mesh", "offset", "Geometry"],
        ["offset", "Geometry", "Group Output", "Geometry"],
        ["wave", 0, "offset", 3],
    ],
}


class TestBuildGeometryNodes:
    def test_sends_the_spec(self, mock_conn):
        build_geometry_nodes("Ground", GRID_SPEC)
        command, params = _sent(mock_conn)
        assert command == "build_geometry_nodes"
        assert params["object_name"] == "Ground" and params["modifier_name"] == "GeometryNodes"
        assert params["spec"]["links"][3] == ["wave", 0, "offset", 3]
        assert params["spec"]["nodes"][0]["inputs"] == {"Vertices X": 20, "Vertices Y": 20}

    def test_empty_spec_is_a_pass_through(self, mock_conn):
        build_geometry_nodes("Ground", {})
        assert _sent(mock_conn)[1]["spec"] == {"inputs": [], "outputs": [], "nodes": [],
                                               "links": []}

    def test_interface_types(self):
        assert {"GEOMETRY", "FLOAT", "INT", "BOOLEAN", "VECTOR", "COLOR", "OBJECT",
                "MATERIAL"} <= ALLOWED_INTERFACE_TYPES

    @pytest.mark.parametrize("spec", [
        "nodes",
        {"nodes": "grid"},
        {"extra": []},
        {"nodes": [{"name": "a", "type": "os.system"}]},
        {"nodes": [{"name": "a", "type": "GeometryNodeMeshGrid", "evil": 1}]},
        {"nodes": [{"name": "a/b", "type": "GeometryNodeMeshGrid"}]},
        {"nodes": [{"name": "Group Input", "type": "GeometryNodeMeshGrid"}]},
        {"nodes": [{"name": "a", "type": "GeometryNodeMeshGrid"},
                   {"name": "a", "type": "GeometryNodeMeshGrid"}]},
        {"nodes": [{"name": "a", "type": "ShaderNodeMath", "settings": {"__class__": 1}}]},
        {"nodes": [{"name": "a", "type": "ShaderNodeMath", "settings": {"operation": [1]}}]},
        {"nodes": [{"name": "a", "type": "ShaderNodeMath", "inputs": {"Value": {"x": 1}}}]},
        {"nodes": [{"name": "a", "type": "ShaderNodeMath", "inputs": {"Value": float("nan")}}]},
        {"nodes": [{"name": "a", "type": "ShaderNodeMath", "location": [0]}]},
        {"links": [["a", 0, "b"]]},
        {"links": [["a", -1, "b", 0]]},
        {"links": [["ghost", 0, "Group Output", 0]]},
        {"inputs": [{"name": "Size", "type": "PYTHON"}]},
        {"inputs": [{"name": "", "type": "FLOAT"}]},
        {"inputs": [{"name": "Size", "type": "FLOAT", "default": "big"}]},
        {"nodes": [{"name": f"n{i}", "type": "ShaderNodeMath"} for i in range(MAX_SPEC_NODES + 1)]},
        {"links": [["Group Input", 0, "Group Output", 0]] * (MAX_SPEC_LINKS + 1)},
    ])
    def test_bad_specs_never_reach_blender(self, mock_conn, spec):
        with pytest.raises(ValidationError):
            build_geometry_nodes("Ground", spec)
        mock_conn.send_command.assert_not_called()


def test_get_tree(mock_conn):
    get_geometry_node_tree("Ground", "GeometryNodes")
    assert _sent(mock_conn) == ("get_geometry_node_tree",
                                {"object_name": "Ground", "modifier_name": "GeometryNodes"})


class TestZones:
    def test_pair_with_is_sent(self, mock_conn):
        build_geometry_nodes("Ground", {"nodes": [
            {"name": "rep_in", "type": "GeometryNodeRepeatInput", "pair_with": "rep_out"},
            {"name": "rep_out", "type": "GeometryNodeRepeatOutput"}]})
        nodes = _sent(mock_conn)[1]["spec"]["nodes"]
        assert nodes[0]["pair_with"] == "rep_out" and "pair_with" not in nodes[1]

    @pytest.mark.parametrize("pair", ["ghost", "rep_in", "Group Output", 5])
    def test_pair_must_name_another_node(self, mock_conn, pair):
        with pytest.raises(ValidationError):
            build_geometry_nodes("Ground", {"nodes": [
                {"name": "rep_in", "type": "GeometryNodeRepeatInput", "pair_with": pair},
                {"name": "rep_out", "type": "GeometryNodeRepeatOutput"}]})
