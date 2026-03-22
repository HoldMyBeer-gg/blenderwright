"""Unit tests for armature tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"success": True}}
    with patch("blend_ai.tools.armature.get_connection", return_value=mock):
        yield mock


class TestCreateArmature:
    def test_create_armature_defaults(self, mock_conn):
        from blend_ai.tools.armature import create_armature

        create_armature()
        mock_conn.send_command.assert_called_once_with("create_armature", {
            "name": "Armature",
            "location": [0, 0, 0],
        })

    def test_create_armature_custom(self, mock_conn):
        from blend_ai.tools.armature import create_armature

        create_armature(name="MyRig", location=(1, 2, 3))
        mock_conn.send_command.assert_called_once_with("create_armature", {
            "name": "MyRig",
            "location": [1, 2, 3],
        })

    def test_create_armature_invalid_name(self, mock_conn):
        from blend_ai.tools.armature import create_armature

        with pytest.raises(ValidationError):
            create_armature(name="")

    def test_create_armature_invalid_location(self, mock_conn):
        from blend_ai.tools.armature import create_armature

        with pytest.raises(ValidationError):
            create_armature(location=(1, 2))

    def test_create_armature_non_numeric_location(self, mock_conn):
        from blend_ai.tools.armature import create_armature

        with pytest.raises(ValidationError):
            create_armature(location=("a", "b", "c"))


class TestAddBone:
    def test_add_bone_defaults(self, mock_conn):
        from blend_ai.tools.armature import add_bone

        add_bone("Armature", "Bone")
        mock_conn.send_command.assert_called_once_with("add_bone", {
            "armature_name": "Armature",
            "bone_name": "Bone",
            "head": [0, 0, 0],
            "tail": [0, 0, 1],
            "parent_bone": "",
        })

    def test_add_bone_custom(self, mock_conn):
        from blend_ai.tools.armature import add_bone

        add_bone("Armature", "UpperArm", head=(0, 0, 1), tail=(0, 0, 2), parent_bone="Spine")
        mock_conn.send_command.assert_called_once_with("add_bone", {
            "armature_name": "Armature",
            "bone_name": "UpperArm",
            "head": [0, 0, 1],
            "tail": [0, 0, 2],
            "parent_bone": "Spine",
        })

    def test_add_bone_invalid_head(self, mock_conn):
        from blend_ai.tools.armature import add_bone

        with pytest.raises(ValidationError):
            add_bone("Armature", "Bone", head=(1, 2))

    def test_add_bone_invalid_tail(self, mock_conn):
        from blend_ai.tools.armature import add_bone

        with pytest.raises(ValidationError):
            add_bone("Armature", "Bone", tail=(1,))

    def test_add_bone_invalid_armature_name(self, mock_conn):
        from blend_ai.tools.armature import add_bone

        with pytest.raises(ValidationError):
            add_bone("", "Bone")

    def test_add_bone_invalid_bone_name(self, mock_conn):
        from blend_ai.tools.armature import add_bone

        with pytest.raises(ValidationError):
            add_bone("Armature", "")

    def test_add_bone_non_numeric_vector(self, mock_conn):
        from blend_ai.tools.armature import add_bone

        with pytest.raises(ValidationError):
            add_bone("Armature", "Bone", head=("x", "y", "z"))


class TestSetBoneProperty:
    def test_set_roll(self, mock_conn):
        from blend_ai.tools.armature import set_bone_property

        set_bone_property("Armature", "Bone", "roll", 0.5)
        mock_conn.send_command.assert_called_once_with("set_bone_property", {
            "armature_name": "Armature",
            "bone_name": "Bone",
            "property": "roll",
            "value": 0.5,
        })

    def test_set_use_deform(self, mock_conn):
        from blend_ai.tools.armature import set_bone_property

        set_bone_property("Armature", "Bone", "use_deform", False)
        mock_conn.send_command.assert_called_once()

    def test_invalid_property(self, mock_conn):
        from blend_ai.tools.armature import set_bone_property

        with pytest.raises(ValidationError):
            set_bone_property("Armature", "Bone", "color", "red")

    def test_all_valid_properties(self, mock_conn):
        from blend_ai.tools.armature import set_bone_property, ALLOWED_BONE_PROPERTIES

        for prop in ALLOWED_BONE_PROPERTIES:
            mock_conn.send_command.reset_mock()
            set_bone_property("Armature", "Bone", prop, 1.0)
            mock_conn.send_command.assert_called_once()


class TestAddConstraint:
    def test_add_ik_constraint(self, mock_conn):
        from blend_ai.tools.armature import add_constraint

        add_constraint("Armature", bone_name="Hand", constraint_type="IK",
                       properties={"chain_count": 3})
        mock_conn.send_command.assert_called_once_with("add_constraint", {
            "object_name": "Armature",
            "bone_name": "Hand",
            "constraint_type": "IK",
            "properties": {"chain_count": 3},
        })

    def test_add_object_level_constraint(self, mock_conn):
        from blend_ai.tools.armature import add_constraint

        add_constraint("Cube", constraint_type="COPY_LOCATION")
        mock_conn.send_command.assert_called_once_with("add_constraint", {
            "object_name": "Cube",
            "bone_name": "",
            "constraint_type": "COPY_LOCATION",
            "properties": {},
        })

    def test_missing_constraint_type(self, mock_conn):
        from blend_ai.tools.armature import add_constraint

        with pytest.raises(ValidationError, match="constraint_type must be specified"):
            add_constraint("Armature", bone_name="Bone")

    def test_invalid_constraint_type(self, mock_conn):
        from blend_ai.tools.armature import add_constraint

        with pytest.raises(ValidationError):
            add_constraint("Armature", constraint_type="CUSTOM")

    def test_all_valid_constraint_types(self, mock_conn):
        from blend_ai.tools.armature import add_constraint, ALLOWED_CONSTRAINT_TYPES

        for ct in ALLOWED_CONSTRAINT_TYPES:
            mock_conn.send_command.reset_mock()
            add_constraint("Armature", constraint_type=ct)
            mock_conn.send_command.assert_called_once()


class TestParentMeshToArmature:
    def test_parent_auto(self, mock_conn):
        from blend_ai.tools.armature import parent_mesh_to_armature

        parent_mesh_to_armature("Body", "Armature")
        mock_conn.send_command.assert_called_once_with("parent_mesh_to_armature", {
            "mesh_name": "Body",
            "armature_name": "Armature",
            "type": "ARMATURE_AUTO",
        })

    def test_parent_by_name(self, mock_conn):
        from blend_ai.tools.armature import parent_mesh_to_armature

        parent_mesh_to_armature("Body", "Armature", type="ARMATURE_NAME")
        mock_conn.send_command.assert_called_once()

    def test_parent_by_envelope(self, mock_conn):
        from blend_ai.tools.armature import parent_mesh_to_armature

        parent_mesh_to_armature("Body", "Armature", type="ARMATURE_ENVELOPE")
        mock_conn.send_command.assert_called_once()

    def test_invalid_parent_type(self, mock_conn):
        from blend_ai.tools.armature import parent_mesh_to_armature

        with pytest.raises(ValidationError):
            parent_mesh_to_armature("Body", "Armature", type="OBJECT")

    def test_invalid_mesh_name(self, mock_conn):
        from blend_ai.tools.armature import parent_mesh_to_armature

        with pytest.raises(ValidationError):
            parent_mesh_to_armature("", "Armature")

    def test_invalid_armature_name(self, mock_conn):
        from blend_ai.tools.armature import parent_mesh_to_armature

        with pytest.raises(ValidationError):
            parent_mesh_to_armature("Body", "")


class TestSetPose:
    def test_set_pose_location(self, mock_conn):
        from blend_ai.tools.armature import set_pose

        set_pose("Armature", "Bone", location=(1, 0, 0))
        mock_conn.send_command.assert_called_once_with("set_pose", {
            "armature_name": "Armature",
            "bone_name": "Bone",
            "location": [1, 0, 0],
        })

    def test_set_pose_rotation(self, mock_conn):
        from blend_ai.tools.armature import set_pose

        set_pose("Armature", "Bone", rotation=(0.5, 0, 0))
        call_args = mock_conn.send_command.call_args
        assert call_args[0][1]["rotation"] == [0.5, 0, 0]

    def test_set_pose_scale(self, mock_conn):
        from blend_ai.tools.armature import set_pose

        set_pose("Armature", "Bone", scale=(2, 2, 2))
        call_args = mock_conn.send_command.call_args
        assert call_args[0][1]["scale"] == [2, 2, 2]

    def test_set_pose_all_transforms(self, mock_conn):
        from blend_ai.tools.armature import set_pose

        set_pose("Armature", "Bone",
                 location=(1, 0, 0), rotation=(0, 0.5, 0), scale=(1, 1, 1))
        call_args = mock_conn.send_command.call_args
        assert "location" in call_args[0][1]
        assert "rotation" in call_args[0][1]
        assert "scale" in call_args[0][1]

    def test_set_pose_no_transforms(self, mock_conn):
        from blend_ai.tools.armature import set_pose

        set_pose("Armature", "Bone")
        call_args = mock_conn.send_command.call_args
        assert "location" not in call_args[0][1]
        assert "rotation" not in call_args[0][1]
        assert "scale" not in call_args[0][1]

    def test_set_pose_invalid_location(self, mock_conn):
        from blend_ai.tools.armature import set_pose

        with pytest.raises(ValidationError):
            set_pose("Armature", "Bone", location=(1, 2))

    def test_set_pose_invalid_bone_name(self, mock_conn):
        from blend_ai.tools.armature import set_pose

        with pytest.raises(ValidationError):
            set_pose("Armature", "")


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.armature import create_armature

        mock_conn.send_command.return_value = {"status": "error", "result": "Failed"}
        with pytest.raises(RuntimeError, match="Blender error"):
            create_armature()
