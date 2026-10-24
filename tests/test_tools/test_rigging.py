"""Tests for constraint hardening, new constraint types, bone collections and IK chains."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.armature import (
    ALLOWED_CONSTRAINT_TYPES,
    add_constraint,
    manage_bone_collection,
    setup_ik_chain,
)
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.armature.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


def test_new_constraint_types():
    assert {"LIMIT_DISTANCE", "SPLINE_IK", "ACTION", "FOLLOW_PATH", "SHRINKWRAP",
            "GEOMETRY_ATTRIBUTE"} <= ALLOWED_CONSTRAINT_TYPES


class TestConstraintProperties:
    def test_plain_values_pass(self, mock_conn):
        add_constraint("Rig", "Hand", "COPY_ROTATION",
                       properties={"target": "Ctrl", "influence": 0.5, "use_x": False,
                                   "owner_space": "LOCAL", "subtarget": "Bone.001"})
        assert _sent(mock_conn)[1]["properties"]["influence"] == 0.5

    @pytest.mark.parametrize("properties", [
        {"__class__": 1}, {"_hidden": 1}, {"Influence": 1}, {"a b": 1},
        {"influence": float("nan")}, {"influence": None}, {"target": {"x": 1}},
        {"name": "x" * 65}, "influence=1",
    ])
    def test_unsafe_properties_refused(self, mock_conn, properties):
        with pytest.raises(ValidationError):
            add_constraint("Rig", "Hand", "COPY_ROTATION", properties=properties)
        mock_conn.send_command.assert_not_called()


class TestBoneCollections:
    def test_create_with_bones(self, mock_conn):
        manage_bone_collection("Rig", "CREATE", "Deform", bones=["Arm", "Arm", "Hand"])
        assert _sent(mock_conn) == ("manage_bone_collection", {
            "armature_name": "Rig", "action": "CREATE", "collection_name": "Deform",
            "bones": ["Arm", "Hand"], "parent": ""})

    def test_hide(self, mock_conn):
        manage_bone_collection("Rig", "HIDE", "Mechanism")
        assert _sent(mock_conn)[1]["action"] == "HIDE"

    @pytest.mark.parametrize("args", [("Rig", "RENAME", "X"), ("Rig", "CREATE", "a/b"),
                                      ("Rig", "ASSIGN", "X", "Arm")])
    def test_rejects(self, mock_conn, args):
        with pytest.raises(ValidationError):
            manage_bone_collection(*args)


class TestIkChain:
    def test_full_setup(self, mock_conn):
        setup_ik_chain("Rig", "Forearm", target_object="HandCtrl", chain_count=2,
                       pole_object="ElbowCtrl", pole_angle=-1.5708, use_stretch=True)
        assert _sent(mock_conn) == ("setup_ik_chain", {
            "armature_name": "Rig", "bone_name": "Forearm", "target_object": "HandCtrl",
            "target_bone": "", "chain_count": 2, "pole_object": "ElbowCtrl",
            "pole_bone": "", "pole_angle": -1.5708, "use_stretch": True, "iterations": 500})

    @pytest.mark.parametrize("kwargs", [{"chain_count": -1}, {"chain_count": 256},
                                        {"pole_angle": 7}, {"iterations": 0},
                                        {"target_object": "a/b"}])
    def test_rejects(self, mock_conn, kwargs):
        args = {"armature_name": "Rig", "bone_name": "Forearm", "target_object": "Ctrl",
                **kwargs}
        with pytest.raises(ValidationError):
            setup_ik_chain(**args)
