"""Sequencer strips, mesh quality and Grease Pencil in a real Blender.
Replaces those fake-bpy handler tests (the file-numbering logic stays a
unit test)."""

import os
import shutil

import pytest

from blenderwright.server import mcp
from blenderwright.tools.objects import create_object

T = {x.name: x.fn for x in mcp._tool_manager.list_tools()}
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


class TestSequencer:
    def test_image_sequence_becomes_one_strip(self, scene):
        for i in (1, 2, 3, 10):
            shutil.copy(os.path.join(ASSETS, "tex.png"), scene / f"frame_{i:04d}.png")
        result = T["add_image_sequence_strip"](str(scene / "frame_0001.png"))
        strip = next(s for s in T["list_strips"]() if s["name"] == result["name"])
        assert strip["frame_end"] - strip["frame_start"] + 1 == 4

    def test_sound_offset_slides_and_names_from_the_file(self, scene):
        result = T["add_sound_strip"](os.path.join(ASSETS, "tone.wav"), frame_start=10)
        assert result["name"].startswith("tone")
        assert next(s for s in T["list_strips"]() if s["name"] == result["name"])[
            "frame_start"] == 10

    def test_remove_and_list(self, scene):
        assert T["list_strips"]() == []
        T["add_sound_strip"](os.path.join(ASSETS, "tone.wav"), name="Tone")
        T["remove_strip"]("Tone")
        assert T["list_strips"]() == []
        with pytest.raises(RuntimeError, match="Tone"):
            T["remove_strip"]("Tone")

    @pytest.mark.parametrize("container, ext, audio", [("MPEG4", "mp4", "AAC"),
                                                       ("WEBM", "webm", "OPUS")])
    def test_render_video_writes_and_restores(self, scene, container, ext, audio):
        T["set_render_resolution"](32, 32)
        T["set_render_engine"]("CYCLES")
        T["set_render_samples"](1)
        T["set_frame_range"](1, 3)
        out = scene / f"clip.{ext}"
        T["render_video"](filepath=str(out), container=container, audio_codec=audio)
        assert out.exists() and out.stat().st_size > 0
        assert T["set_output_format"]("PNG")["format"] == "PNG"


class TestMeshQuality:
    def test_clean_cube(self, scene):
        report = T["analyze_mesh_quality"]("Cube")
        assert report["issues_found"] is False
        assert (report["vertex_count"], report["face_count"]) == (8, 6)

    def test_open_plane_is_non_manifold(self, scene):
        create_object("PLANE", name="Sheet")
        report = T["analyze_mesh_quality"]("Sheet")
        assert report["non_manifold_edge_count"] == 4 and report["issues_found"] is True

    def test_duplicate_vertices_found_and_repaired(self, scene):
        create_object("CUBE", name="Twin")
        T["join_objects"](["Cube", "Twin"])
        assert T["analyze_mesh_quality"]("Cube")["duplicate_vertex_count"] >= 8
        T["merge_vertices"]("Cube")
        assert T["analyze_mesh_quality"]("Cube")["duplicate_vertex_count"] == 0

    def test_repair_fills_the_hole_a_cut_leaves(self, scene):
        create_object("CUBE", name="Box")
        T["bisect_mesh"]("Box", plane_point=[0, 0, 0.5], clear_outer=True)
        assert T["analyze_mesh_quality"]("Box")["non_manifold_edge_count"] > 0
        result = T["repair_mesh"]("Box", fill_holes=True)
        assert result["repairs_applied"]
        assert T["analyze_mesh_quality"]("Box")["non_manifold_edge_count"] == 0

    def test_missing_and_non_mesh(self, scene):
        with pytest.raises(RuntimeError, match="Ghost"):
            T["analyze_mesh_quality"]("Ghost")
        with pytest.raises(RuntimeError):
            T["analyze_mesh_quality"]("Light")


class TestAnnotations:
    def test_create_layer_stroke_remove(self, scene):
        name = T["create_annotation"]("Notes")["name"]
        T["add_annotation_layer"](name, "Ideas")
        assert T["add_annotation_stroke"](name, "Ideas", [[0, 0, 0], [1, 1, 0]])[
            "point_count"] == 2
        T["remove_annotation_layer"](name, "Ideas")
        with pytest.raises(RuntimeError, match="Ideas"):
            T["remove_annotation_layer"](name, "Ideas")
        with pytest.raises(RuntimeError, match="Ghost"):
            T["add_annotation_layer"]("Ghost", "x")


class TestGreasePencil:
    def test_draw_with_material_on_a_new_layer(self, scene):
        T["create_grease_pencil"](name="Sketch")
        T["create_gp_material"]("Red", color=[1, 0, 0, 1])
        result = T["add_gp_stroke"]("Sketch", [[0, 0, 0], [1, 0, 1], [2, 0, 0]],
                                    layer="Ink", material="Red")
        assert (result["layer"], result["points"], result["strokes_on_frame"]) == ("Ink", 3, 1)

    def test_stroke_without_materials_gets_default_ink(self, scene):
        T["create_grease_pencil"](name="Sketch")
        T["add_gp_stroke"]("Sketch", [[0, 0, 0], [1, 0, 0]])

    def test_refusals(self, scene):
        T["create_grease_pencil"](name="Sketch")
        with pytest.raises(RuntimeError, match="Material"):
            T["add_gp_stroke"]("Sketch", [[0, 0, 0], [1, 0, 0]], material="Material")
        with pytest.raises(RuntimeError, match="Grease Pencil"):
            T["add_gp_stroke"]("Cube", [[0, 0, 0], [1, 0, 0]])

    def test_lineart_needs_a_camera(self, scene):
        T["add_lineart"]()
        T["delete_object"]("Camera")
        with pytest.raises(RuntimeError, match="(?i)camera"):
            T["add_lineart"](name="Second")
