"""Unit tests for geometry nodes tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"name": "GeometryNodes"}}
    with patch("blend_ai.tools.geometry_nodes.get_connection", return_value=mock):
        yield mock


class TestCreateGeometryNodes:
    def test_create_default(self, mock_conn):
        from blend_ai.tools.geometry_nodes import create_geometry_nodes

        result = create_geometry_nodes("Cube")
        mock_conn.send_command.assert_called_once_with("create_geometry_nodes", {
            "object_name": "Cube",
            "name": "GeometryNodes",
        })
        assert result == {"name": "GeometryNodes"}

    def test_create_custom_name(self, mock_conn):
        from blend_ai.tools.geometry_nodes import create_geometry_nodes

        create_geometry_nodes("Cube", name="MyGeoNodes")
        mock_conn.send_command.assert_called_once_with("create_geometry_nodes", {
            "object_name": "Cube",
            "name": "MyGeoNodes",
        })

    def test_invalid_object_name(self, mock_conn):
        from blend_ai.tools.geometry_nodes import create_geometry_nodes

        with pytest.raises(ValidationError):
            create_geometry_nodes("")

    def test_invalid_modifier_name(self, mock_conn):
        from blend_ai.tools.geometry_nodes import create_geometry_nodes

        with pytest.raises(ValidationError):
            create_geometry_nodes("Cube", name="")


class TestAddGeometryNode:
    def test_add_node(self, mock_conn):
        from blend_ai.tools.geometry_nodes import add_geometry_node

        add_geometry_node("GeometryNodes", "GeometryNodeMeshCube", location=(100, 0))
        mock_conn.send_command.assert_called_once_with("add_geometry_node", {
            "modifier_name": "GeometryNodes",
            "node_type": "GeometryNodeMeshCube",
            "location": [100, 0],
        })

    def test_add_node_default_location(self, mock_conn):
        from blend_ai.tools.geometry_nodes import add_geometry_node

        add_geometry_node("GeometryNodes", "GeometryNodeTransform")
        mock_conn.send_command.assert_called_once_with("add_geometry_node", {
            "modifier_name": "GeometryNodes",
            "node_type": "GeometryNodeTransform",
            "location": [0, 0],
        })

    def test_empty_node_type(self, mock_conn):
        from blend_ai.tools.geometry_nodes import add_geometry_node

        with pytest.raises(ValidationError, match="node_type must be a non-empty string"):
            add_geometry_node("GeometryNodes", "")

    def test_invalid_modifier_name(self, mock_conn):
        from blend_ai.tools.geometry_nodes import add_geometry_node

        with pytest.raises(ValidationError):
            add_geometry_node("", "GeometryNodeMeshCube")

    def test_invalid_location_size(self, mock_conn):
        from blend_ai.tools.geometry_nodes import add_geometry_node

        with pytest.raises(ValidationError):
            add_geometry_node("GeometryNodes", "GeometryNodeMeshCube", location=(1, 2, 3))


class TestConnectGeometryNodes:
    def test_connect_nodes(self, mock_conn):
        from blend_ai.tools.geometry_nodes import connect_geometry_nodes

        connect_geometry_nodes("GeometryNodes", "MeshCube", 0, "Group Output", 0)
        mock_conn.send_command.assert_called_once_with("connect_geometry_nodes", {
            "modifier_name": "GeometryNodes",
            "from_node": "MeshCube",
            "from_socket": 0,
            "to_node": "Group Output",
            "to_socket": 0,
        })

    def test_empty_from_node(self, mock_conn):
        from blend_ai.tools.geometry_nodes import connect_geometry_nodes

        with pytest.raises(ValidationError, match="from_node must be a non-empty string"):
            connect_geometry_nodes("GeometryNodes", "", 0, "Group Output", 0)

    def test_empty_to_node(self, mock_conn):
        from blend_ai.tools.geometry_nodes import connect_geometry_nodes

        with pytest.raises(ValidationError, match="to_node must be a non-empty string"):
            connect_geometry_nodes("GeometryNodes", "MeshCube", 0, "", 0)

    def test_negative_from_socket(self, mock_conn):
        from blend_ai.tools.geometry_nodes import connect_geometry_nodes

        with pytest.raises(ValidationError, match="from_socket must be a non-negative integer"):
            connect_geometry_nodes("GeometryNodes", "MeshCube", -1, "Group Output", 0)

    def test_negative_to_socket(self, mock_conn):
        from blend_ai.tools.geometry_nodes import connect_geometry_nodes

        with pytest.raises(ValidationError, match="to_socket must be a non-negative integer"):
            connect_geometry_nodes("GeometryNodes", "MeshCube", 0, "Group Output", -1)

    def test_non_int_socket(self, mock_conn):
        from blend_ai.tools.geometry_nodes import connect_geometry_nodes

        with pytest.raises(ValidationError):
            connect_geometry_nodes("GeometryNodes", "MeshCube", 0.5, "Group Output", 0)


class TestSetGeometryNodeInput:
    def test_set_input(self, mock_conn):
        from blend_ai.tools.geometry_nodes import set_geometry_node_input

        set_geometry_node_input("Cube", "GeometryNodes", "Size", 2.0)
        mock_conn.send_command.assert_called_once_with("set_geometry_node_input", {
            "object_name": "Cube",
            "modifier_name": "GeometryNodes",
            "input_name": "Size",
            "value": 2.0,
        })

    def test_empty_input_name(self, mock_conn):
        from blend_ai.tools.geometry_nodes import set_geometry_node_input

        with pytest.raises(ValidationError, match="input_name must be a non-empty string"):
            set_geometry_node_input("Cube", "GeometryNodes", "", 1.0)

    def test_invalid_object_name(self, mock_conn):
        from blend_ai.tools.geometry_nodes import set_geometry_node_input

        with pytest.raises(ValidationError):
            set_geometry_node_input("", "GeometryNodes", "Size", 1.0)

    def test_invalid_modifier_name(self, mock_conn):
        from blend_ai.tools.geometry_nodes import set_geometry_node_input

        with pytest.raises(ValidationError):
            set_geometry_node_input("Cube", "", "Size", 1.0)


class TestListGeometryNodeInputs:
    def test_list_inputs(self, mock_conn):
        from blend_ai.tools.geometry_nodes import list_geometry_node_inputs

        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": [{"name": "Size", "type": "FLOAT", "value": 1.0}],
        }
        result = list_geometry_node_inputs("Cube", "GeometryNodes")
        mock_conn.send_command.assert_called_once_with("list_geometry_node_inputs", {
            "object_name": "Cube",
            "modifier_name": "GeometryNodes",
        })
        assert len(result) == 1
        assert result[0]["name"] == "Size"

    def test_invalid_object_name(self, mock_conn):
        from blend_ai.tools.geometry_nodes import list_geometry_node_inputs

        with pytest.raises(ValidationError):
            list_geometry_node_inputs("", "GeometryNodes")

    def test_invalid_modifier_name(self, mock_conn):
        from blend_ai.tools.geometry_nodes import list_geometry_node_inputs

        with pytest.raises(ValidationError):
            list_geometry_node_inputs("Cube", "")


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.geometry_nodes import create_geometry_nodes

        mock_conn.send_command.return_value = {"status": "error", "result": "Modifier not found"}
        with pytest.raises(RuntimeError, match="Blender error"):
            create_geometry_nodes("Cube")
