"""Physics, modifiers, armatures, mesh edits, baking, selection and the
sweep fixes in a real Blender. Replaces those fake-bpy handler tests."""

import pytest

from blenderwright import server
from blenderwright.server import mcp
from blenderwright.tools.mesh_quality import analyze_mesh_quality
from blenderwright.tools.objects import create_object, get_object_info

T = {x.name: x.fn for x in mcp._tool_manager.list_tools()}


def _raw(command, params):
    return server.get_connection().send_command(command, params)


class TestPhysics:
    @pytest.mark.parametrize("add", ["add_rigid_body", "add_cloth_sim", "add_particle_system",
                                     "add_soft_body"])
    def test_each_simulation_bakes(self, scene, add):
        T["set_frame_range"](1, 5)
        create_object("UV_SPHERE", name="Thing", location=[0, 0, 3])
        T[add]("Thing")
        assert T["bake_physics"]("Thing")

    def test_force_field_and_collision(self, scene):
        T["add_force_field"]("WIND", name="Breeze", strength=5.0)
        assert get_object_info("Breeze")["type"] == "EMPTY"
        T["add_collision"]("Cube", friction=2.0)
        with pytest.raises(RuntimeError):
            T["bake_physics"]("Light")

    def test_unknown_field_type_refused_by_the_addon(self, scene):
        assert _raw("add_force_field", {"type": "__class__"})["status"] == "error"

    def test_glued_body_hangs_and_unglued_falls(self, scene):
        T["set_frame_range"](1, 40)
        create_object("CUBE", name="Anchor", location=[0, 0, 6])
        create_object("CUBE", name="Weight", location=[0, 0, 3])
        create_object("CUBE", name="Loose", location=[5, 0, 3])
        T["add_rigid_body"]("Anchor", type="PASSIVE")
        for name in ("Weight", "Loose"):
            T["add_rigid_body"](name)
        T["add_rigid_body_constraint"]("Anchor", "Weight", type="FIXED")
        assert T["set_rigid_body_world"](substeps_per_frame=20)["substeps_per_frame"] == 20
        for frame in range(1, 41):
            T["set_frame"](frame)
        assert get_object_info("Weight")["world_location"][2] == pytest.approx(3.0, abs=0.1)
        assert get_object_info("Loose")["world_location"][2] < -5.0

    def test_constraint_needs_rigid_bodies(self, scene):
        with pytest.raises(RuntimeError, match="add_rigid_body"):
            T["add_rigid_body_constraint"]("Cube", "Light")


class TestModifiers:
    def test_text_values_become_the_property_type(self, scene):
        T["add_modifier"]("Cube", "BEVEL", name="Bevel")
        T["set_modifier_property"]("Cube", "Bevel", "segments", "3")
        T["set_modifier_property"]("Cube", "Bevel", "width", "0.25")
        assert analyze_mesh_quality("Cube")["vertex_count"] == 8  # not applied yet

    def test_object_target_by_name_changes_the_shape(self, scene):
        create_object("UV_SPHERE", name="Ball", location=[0, 0, 5])
        create_object("PLANE", name="Floor", scale=[5, 5, 1])
        T["add_modifier"]("Ball", "SHRINKWRAP", name="Wrap")
        T["set_modifier_property"]("Ball", "Wrap", "target", "Floor")
        assert get_object_info("Ball")["dimensions"][2] == pytest.approx(0.0, abs=0.01)

    def test_errors_list_the_real_settings(self, scene):
        T["add_modifier"]("Cube", "BEVEL", name="Bevel")
        with pytest.raises(RuntimeError, match="width"):
            T["set_modifier_property"]("Cube", "Bevel", "widht", 1)
        T["add_modifier"]("Cube", "SHRINKWRAP", name="Wrap")
        with pytest.raises(RuntimeError, match="Ghost"):
            T["set_modifier_property"]("Cube", "Wrap", "target", "Ghost")

    def test_extrude_positive_goes_outward(self, scene):
        create_object("PLANE", name="Sheet")
        T["extrude_faces"]("Sheet", offset=1.0)
        assert get_object_info("Sheet")["dimensions"][2] == pytest.approx(1.0, abs=0.01)


class TestArmature:
    @pytest.fixture
    def rig(self, scene):
        T["create_armature"](name="Rig")
        T["add_bone"]("Rig", "Upper", head=[0, 0, 0], tail=[0, 0, 1])
        T["add_bone"]("Rig", "Lower", head=[0, 0, 1], tail=[0, 0, 2], parent_bone="Upper")
        return "Rig"

    def test_bone_collections(self, rig):
        T["manage_bone_collection"](rig, "CREATE", "Arm")
        T["manage_bone_collection"](rig, "ASSIGN", "Arm", bones=["Upper", "Lower"])
        T["manage_bone_collection"](rig, "HIDE", "Arm")
        T["manage_bone_collection"](rig, "DELETE", "Arm")
        with pytest.raises(RuntimeError, match="Ghost"):
            T["manage_bone_collection"](rig, "ASSIGN", "Ghost", bones=["Upper"])

    def test_ik_chain(self, rig):
        create_object("EMPTY", name="Target", location=[1, 0, 2])
        result = T["setup_ik_chain"](rig, "Lower", "Target", chain_count=2)
        assert result
        with pytest.raises(RuntimeError, match="Nowhere"):
            T["setup_ik_chain"](rig, "Lower", "Nowhere")

    def test_constraint_settings_are_rna_only(self, scene):
        create_object("EMPTY", name="Leader", location=[3, 0, 0])
        T["add_constraint"]("Cube", constraint_type="COPY_LOCATION",
                            properties={"target": "Leader", "use_y": False})
        info = get_object_info("Cube")
        assert info["location"][0] == pytest.approx(0)  # what was set
        assert info["world_location"][0] == pytest.approx(3.0)  # where it really is
        reply = _raw("add_constraint", {"object_name": "Cube", "constraint_type": "COPY_LOCATION",
                                        "properties": {"__class__": 1}})
        assert reply["status"] == "error"


class TestMeshEdits:
    def test_symmetrize_and_bisect(self, scene):
        create_object("MONKEY", name="Face")
        T["symmetrize_mesh"]("Face")
        T["bisect_mesh"]("Face", plane_normal=[1, 0, 0], clear_outer=True)
        assert get_object_info("Face")["dimensions"][0] < 1.6

    def test_unknown_options_refused_by_the_addon(self, scene):
        assert _raw("symmetrize_mesh", {"object_name": "Cube",
                                        "direction": "SIDEWAYS"})["status"] == "error"
        assert _raw("loop_tools", {"object_name": "Cube",
                                   "operation": "__class__"})["status"] == "error"


class TestBaking:
    def test_diffuse_bake_writes_a_file_and_restores_the_engine(self, scene):
        T["smart_uv_project"]("Cube")
        T["set_render_engine"]("BLENDER_EEVEE")
        out = scene / "bake.png"
        T["bake_texture"]("Cube", "DIFFUSE", str(out), resolution=64, samples=1)
        assert out.exists()
        assert T["set_render_samples"](16)["engine"] == "BLENDER_EEVEE"

    def test_high_to_low(self, scene):
        create_object("UV_SPHERE", name="High")
        T["smart_uv_project"]("Cube")
        out = scene / "normal.png"
        T["bake_texture"]("Cube", "NORMAL", str(out), resolution=64, samples=1,
                          source_object="High", cage_extrusion=0.1)
        assert out.exists()

    def test_unbakeable_object(self, scene):
        with pytest.raises(RuntimeError):
            T["bake_texture"]("Light", "DIFFUSE", str(scene / "x.png"), resolution=64)


class TestSelection:
    def test_index_selection_and_bounds(self, scene):
        result = T["select_by_index"]("Cube", "FACE", [0])
        assert result["faces"]["selected"] == 1
        with pytest.raises(RuntimeError, match="out of range"):
            T["select_by_index"]("Cube", "VERTEX", [99])

    def test_extend_keeps_the_existing_selection(self, scene):
        T["select_by_axis"]("Cube", axis="Z", sign="POS")
        result = T["select_by_axis"]("Cube", axis="Z", sign="NEG", extend=True)
        assert result["faces"]["selected"] == 6


class TestSweepFixes:
    def test_duplicate_material_has_its_own_tree(self, scene):
        T["duplicate_material"]("Material", "Copy")
        T["set_shader_node_input"]("Copy", "Principled BSDF", "Roughness", 0.9)
        original = next(n for n in T["get_node_tree"]("Material")["nodes"]
                        if n["name"] == "Principled BSDF")
        assert original["values"]["Roughness"] != pytest.approx(0.9)

    def test_slice_makes_two_pieces(self, scene):
        create_object("UV_SPHERE", name="Knife", location=[1, 0, 0])
        T["booltool_auto_slice"]("Cube", "Knife")
        names = {o["name"] for o in T["list_objects"]()}
        assert {"Cube", "Cube.001"} <= names and "Knife" not in names

    def test_recent_files_is_a_list(self, scene):
        assert isinstance(T["list_recent_files"](), list)


class TestFocus:
    def test_focusing_while_sculpting_keeps_sculpt_mode(self, scene):
        T["enter_sculpt_mode"]("Cube")
        T["focus_on_object"]("Cube")
        T["set_sculpt_mask"]("Cube")  # sculpt-only state still reachable
        T["exit_sculpt_mode"]()

    def test_focusing_another_object(self, scene):
        create_object("UV_SPHERE", name="Ball", location=[3, 0, 0])
        T["enter_sculpt_mode"]("Cube")
        assert T["focus_on_object"]("Ball")["success"] is True
