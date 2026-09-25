"""Inputs that were accepted and then silently did the wrong thing.

Each of these reported success while producing nothing, producing something
broken, or writing somewhere the caller did not ask for. Collected from an
audit of all 175 tools; see issue #31.
"""

import contextlib
from unittest.mock import MagicMock, patch

import pytest

from blend_ai.validators import ValidationError

# Each tool module resolves get_connection through its own namespace, and this
# file spans several, so patch them all.
_MODULES = ("mesh_editing", "modeling", "armature", "curves", "rendering",
            "scene", "geometry_nodes")


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with contextlib.ExitStack() as stack:
        for name in _MODULES:
            stack.enter_context(
                patch(f"blend_ai.tools.{name}.get_connection", return_value=mock))
        yield mock


class TestZeroSizedOperations:
    """Zero duplicates geometry in place and reports success.

    Same shape as extrude_faces(offset=0): the operator runs, new geometry is
    created on top of the old, and the mesh is left non-manifold with nothing
    to show for it.
    """

    def test_inset_thickness_zero_is_rejected(self, mock_conn):
        from blend_ai.tools.mesh_editing import inset_faces
        with pytest.raises(ValidationError):
            inset_faces("Cube", thickness=0)

    def test_inset_thickness_positive_is_fine(self, mock_conn):
        from blend_ai.tools.mesh_editing import inset_faces
        inset_faces("Cube", thickness=0.05)
        assert mock_conn.send_command.call_args[0][1]["thickness"] == 0.05

    def test_bevel_width_zero_is_rejected(self, mock_conn):
        from blend_ai.tools.modeling import bevel_edges
        with pytest.raises(ValidationError):
            bevel_edges("Cube", width=0)

    def test_bevel_width_positive_is_fine(self, mock_conn):
        from blend_ai.tools.modeling import bevel_edges
        bevel_edges("Cube", width=0.02)
        assert mock_conn.send_command.call_args[0][1]["width"] == 0.02


class TestDegenerateVectors:
    def test_zero_length_bone_is_rejected(self, mock_conn):
        """Blender discards zero-length bones, so the tool reported one it
        had not created."""
        from blend_ai.tools.armature import add_bone
        with pytest.raises(ValidationError) as exc:
            add_bone("Rig", "Bone", head=[0, 0, 1], tail=[0, 0, 1])
        assert "length" in str(exc.value).lower()

    def test_a_real_bone_is_fine(self, mock_conn):
        from blend_ai.tools.armature import add_bone
        add_bone("Rig", "Bone", head=[0, 0, 0], tail=[0, 0, 1])
        assert mock_conn.send_command.called

    def test_zero_spin_axis_is_rejected(self, mock_conn):
        """A zero-magnitude rotation axis produces nothing, with no error."""
        from blend_ai.tools.mesh_editing import spin_mesh
        with pytest.raises(ValidationError) as exc:
            spin_mesh("Cube", axis=[0, 0, 0])
        assert "axis" in str(exc.value).lower()

    def test_a_real_spin_axis_is_fine(self, mock_conn):
        from blend_ai.tools.mesh_editing import spin_mesh
        spin_mesh("Cube", axis=[0, 0, 1])
        assert mock_conn.send_command.called


class TestFilePathsAreValidated:
    def test_font_path_is_validated(self, mock_conn):
        """The only file path in the codebase that skipped validation."""
        from blend_ai.tools.curves import create_text
        with pytest.raises(ValidationError):
            create_text("Hi", font="relative/font.ttf")

    def test_font_extension_is_checked(self, mock_conn, tmp_path):
        from blend_ai.tools.curves import create_text
        bad = tmp_path / "notafont.txt"
        bad.write_text("")
        with pytest.raises(ValidationError):
            create_text("Hi", font=str(bad))

    def test_no_font_is_still_allowed(self, mock_conn):
        from blend_ai.tools.curves import create_text
        create_text("Hi")
        assert mock_conn.send_command.called

    def test_render_animation_resolves_a_relative_path(self, mock_conn):
        """Blender resolves a relative path against the .blend, so frames
        landed somewhere the caller never named. validate_file_path pins it to
        an absolute path first, as render_image already did."""
        from blend_ai.tools.rendering import render_animation
        render_animation(filepath="frames/out")
        sent = mock_conn.send_command.call_args[0][1]["filepath"]
        assert sent.startswith("/"), f"sent a relative path: {sent!r}"

    def test_render_animation_rejects_null_bytes(self, mock_conn):
        from blend_ai.tools.rendering import render_animation
        with pytest.raises(ValidationError):
            render_animation(filepath="/tmp/out\x00evil")


class TestSceneProperties:
    def test_gravity_must_be_a_vector(self, mock_conn):
        """A scalar raised TypeError: 'float' object is not iterable, inside
        Blender."""
        from blend_ai.tools.scene import set_scene_property
        with pytest.raises(ValidationError):
            set_scene_property("gravity", -9.81)

    def test_gravity_vector_is_accepted(self, mock_conn):
        from blend_ai.tools.scene import set_scene_property
        set_scene_property("gravity", [0, 0, -9.81])
        assert mock_conn.send_command.called

    def test_use_gravity_must_be_a_boolean(self, mock_conn):
        from blend_ai.tools.scene import set_scene_property
        with pytest.raises(ValidationError):
            set_scene_property("use_gravity", "maybe")


class TestGeometryNodeTypeShape:
    """Shader nodes had a 64-entry allowlist; geometry nodes had none.

    The authoritative check lives in the addon, which can ask bpy.types what
    node classes this Blender actually has and so cannot drift across
    versions. The tool layer only rejects shapes that cannot be a node type,
    to catch obvious junk without a round trip.
    """

    @pytest.mark.parametrize("bad", ["cube", "Cube", "bpy.ops.mesh.cube",
                                     "GeometryNode Mesh Cube", ""])
    def test_obviously_wrong_shapes_are_rejected(self, mock_conn, bad):
        from blend_ai.tools.geometry_nodes import add_geometry_node
        with pytest.raises(ValidationError):
            add_geometry_node("Tree", bad)

    @pytest.mark.parametrize("good", ["GeometryNodeMeshCube", "FunctionNodeInputVector",
                                      "ShaderNodeMath", "GeometryNodeSetPosition"])
    def test_plausible_node_identifiers_pass_to_the_addon(self, mock_conn, good):
        """The addon has bpy and makes the real decision."""
        from blend_ai.tools.geometry_nodes import add_geometry_node
        add_geometry_node("Tree", good)
        assert mock_conn.send_command.call_args[0][1]["node_type"] == good
