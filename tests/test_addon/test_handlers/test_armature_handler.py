"""Armature handlers must reject a missing name, not pass None to Blender.

The TCP socket accepts raw JSON from any local process, so a handler can be
reached without the MCP tool's validation. bpy_prop_collection.get(None)
raises an opaque SystemError in Blender 5.2.
"""

import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load_handler():
    """Load addon.handlers.armature without addon/handlers/__init__.py."""
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "armature.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.armature", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.armature"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def handler():
    return _load_handler()


CASES = [
    ("handle_add_bone", {"armature_name": "Rig", "bone_name": "Bone"}),
    ("handle_set_bone_property", {"armature_name": "Rig", "bone_name": "Bone",
                                  "property": "roll", "value": 0.0}),
    ("handle_add_constraint", {"object_name": "Rig", "constraint_type": "COPY_LOCATION"}),
    ("handle_parent_mesh_to_armature", {"mesh_name": "Body", "armature_name": "Rig"}),
    ("handle_set_pose", {"armature_name": "Rig", "bone_name": "Bone"}),
]

MISSING = [
    (name, key, {k: v for k, v in params.items() if k != key})
    for name, params in CASES
    for key in params
    if key.endswith("_name")
]


@pytest.mark.parametrize("handler_name, key, params", MISSING,
                         ids=[f"{n}-{k}" for n, k, _ in MISSING])
def test_missing_name_is_rejected_before_blender(handler, handler_name, key, params):
    import bpy

    bpy.data.objects.get = MagicMock()
    with pytest.raises(KeyError, match=key):
        getattr(handler, handler_name)(params)
    for call in bpy.data.objects.get.call_args_list:
        assert call.args and call.args[0] is not None


def test_dead_helpers_are_gone(handler):
    assert not hasattr(handler, "_ensure_mode")


def _rna_constraint():
    """A constraint whose RNA declares a few settings, like Blender's."""
    props = {
        "influence": SimpleNamespace(type="FLOAT", is_readonly=False),
        "use_x": SimpleNamespace(type="BOOLEAN", is_readonly=False),
        "owner_space": SimpleNamespace(type="ENUM", is_readonly=False),
        "subtarget": SimpleNamespace(type="STRING", is_readonly=False),
        "target": SimpleNamespace(type="POINTER", is_readonly=False),
        "is_valid": SimpleNamespace(type="BOOLEAN", is_readonly=True),
        "type": SimpleNamespace(type="ENUM", is_readonly=True),
    }
    c = SimpleNamespace(name="Copy Rotation", influence=1.0, use_x=True, owner_space="WORLD",
                        subtarget="", target=None)
    c.bl_rna = SimpleNamespace(properties=props)
    return c


@pytest.fixture
def rig(monkeypatch):
    import bpy

    constraint = _rna_constraint()
    removed = []
    bone = SimpleNamespace(name="Hand",
                           constraints=SimpleNamespace(new=lambda type: constraint,
                                                       remove=removed.append))
    rig_obj = SimpleNamespace(name="Rig", type="ARMATURE",
                              pose=SimpleNamespace(bones={"Hand": bone}))
    ctrl = SimpleNamespace(name="Ctrl")
    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(
        get={"Rig": rig_obj, "Ctrl": ctrl}.get))
    return SimpleNamespace(constraint=constraint, ctrl=ctrl, rig=rig_obj, removed=removed)


class TestConstraintSettingsAreRnaOnly:
    def test_declared_settings_are_set(self, handler, rig):
        handler.handle_add_constraint({
            "object_name": "Rig", "bone_name": "Hand", "constraint_type": "COPY_ROTATION",
            "properties": {"target": "Ctrl", "subtarget": "Bone", "influence": 0.5,
                           "use_x": False, "owner_space": "LOCAL"}})
        c = rig.constraint
        assert (c.target, c.subtarget, c.influence, c.use_x, c.owner_space) == (
            rig.ctrl, "Bone", 0.5, False, "LOCAL")

    @pytest.mark.parametrize("key", ["__class__", "bl_rna", "is_valid", "type", "frobnicate"])
    def test_anything_else_is_refused(self, handler, rig, key):
        with pytest.raises(ValueError, match=key):
            handler.handle_add_constraint({
                "object_name": "Rig", "bone_name": "Hand", "constraint_type": "COPY_ROTATION",
                "properties": {key: 1}})
        assert rig.removed == [rig.constraint]  # no half-configured constraint left


class BoneCollection:
    def __init__(self, name, parent=None):
        self.name, self.parent, self.is_visible = name, parent, True
        self.bones = []

    def assign(self, bone):
        if bone not in self.bones:
            self.bones.append(bone)
        return True

    def unassign(self, bone):
        if bone in self.bones:
            self.bones.remove(bone)


@pytest.fixture
def arm(monkeypatch):
    import bpy

    cols = {}

    class Collections:
        def new(self, name, parent=None):
            cols[name] = BoneCollection(name, parent)
            return cols[name]

        def get(self, name):
            return cols.get(name)

        def remove(self, col):
            cols.pop(col.name)

    bones = {n: SimpleNamespace(name=n) for n in ("Arm", "Forearm", "Hand")}
    data = SimpleNamespace(collections=Collections(), collections_all=cols, bones=bones)
    pose_bones = {n: SimpleNamespace(name=n, constraints=[], ik_stretch=0.0) for n in bones}
    for pb in pose_bones.values():
        pb.constraints = SimpleNamespace(new=lambda type, pb=pb: _ik(pb))
    rig_obj = SimpleNamespace(name="Rig", type="ARMATURE", data=data,
                              pose=SimpleNamespace(bones=pose_bones))
    objects = {"Rig": rig_obj, "Ctrl": SimpleNamespace(name="Ctrl"),
               "Pole": SimpleNamespace(name="Pole")}
    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(get=objects.get))
    return SimpleNamespace(cols=cols, bones=bones, pose=pose_bones, objects=objects)


def _ik(pb):
    pb.ik = SimpleNamespace(name="IK", target=None, subtarget="", pole_target=None,
                            pole_subtarget="", pole_angle=0.0, chain_count=0,
                            use_stretch=True, iterations=500)
    return pb.ik


class TestBoneCollections:
    def test_create_assign_hide_delete(self, handler, arm):
        handler.handle_manage_bone_collection({"armature_name": "Rig", "action": "CREATE",
                                               "collection_name": "Deform",
                                               "bones": ["Arm", "Forearm"], "parent": ""})
        assert [b.name for b in arm.cols["Deform"].bones] == ["Arm", "Forearm"]
        handler.handle_manage_bone_collection({"armature_name": "Rig", "action": "UNASSIGN",
                                               "collection_name": "Deform", "bones": ["Arm"]})
        result = handler.handle_manage_bone_collection({"armature_name": "Rig",
                                                        "action": "HIDE",
                                                        "collection_name": "Deform"})
        assert arm.cols["Deform"].is_visible is False
        assert result["collections"] == [{"name": "Deform", "visible": False,
                                          "bones": ["Forearm"], "parent": None}]
        handler.handle_manage_bone_collection({"armature_name": "Rig", "action": "DELETE",
                                               "collection_name": "Deform"})
        assert arm.cols == {}

    def test_unknown_bone_and_collection(self, handler, arm):
        with pytest.raises(ValueError, match="Tail"):
            handler.handle_manage_bone_collection({"armature_name": "Rig", "action": "CREATE",
                                                   "collection_name": "X", "bones": ["Tail"]})
        assert arm.cols == {}
        with pytest.raises(ValueError, match="Nope"):
            handler.handle_manage_bone_collection({"armature_name": "Rig", "action": "SHOW",
                                                   "collection_name": "Nope"})


class TestIkChain:
    def test_sets_target_pole_and_chain(self, handler, arm):
        result = handler.handle_setup_ik_chain({
            "armature_name": "Rig", "bone_name": "Forearm", "target_object": "Ctrl",
            "target_bone": "", "chain_count": 2, "pole_object": "Pole", "pole_bone": "",
            "pole_angle": -1.5708, "use_stretch": False, "iterations": 300})
        ik = arm.pose["Forearm"].ik
        assert (ik.target, ik.pole_target, ik.chain_count, ik.pole_angle, ik.use_stretch,
                ik.iterations) == (arm.objects["Ctrl"], arm.objects["Pole"], 2, -1.5708,
                                   False, 300)
        assert result["constraint"] == "IK"

    def test_missing_target(self, handler, arm):
        with pytest.raises(ValueError, match="Ghost"):
            handler.handle_setup_ik_chain({"armature_name": "Rig", "bone_name": "Forearm",
                                           "target_object": "Ghost"})
