"""Unit tests for the imported mesh cleanup workflow prompt."""

from blenderwright.prompts.workflows import imported_mesh_cleanup


class TestImportedMeshCleanupPrompt:
    def test_returns_non_empty_string(self):
        result = imported_mesh_cleanup()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_is_vendor_neutral(self):
        result = imported_mesh_cleanup().lower()
        for vendor in ("tripo", "meshy", "sketchfab", "luma", "rodin"):
            assert vendor not in result

    def test_chains_import_analyze_repair(self):
        result = imported_mesh_cleanup()
        assert "import_file" in result
        assert "analyze_mesh_quality" in result
        assert "repair_mesh" in result
        assert result.index("import_file") < result.index("analyze_mesh_quality")
        assert result.index("analyze_mesh_quality") < result.index("repair_mesh")

    def test_merges_duplicates_before_repair(self):
        result = imported_mesh_cleanup()
        assert "merge_vertices" in result
        assert "duplicate_vertex_count" in result
        assert result.index("merge_vertices") < result.index("repair_mesh")

    def test_fill_holes_is_called_out_as_opt_in(self):
        result = imported_mesh_cleanup()
        assert "fill_holes" in result
        assert "non_manifold_edge_count" in result

    def test_covers_density_and_normals(self):
        result = imported_mesh_cleanup()
        assert "decimate_mesh" in result
        assert "recalculate_normals" in result

    def test_covers_transforms_and_scale(self):
        result = imported_mesh_cleanup()
        assert "apply_transforms" in result
        assert "scale_reference_guide" in result

    def test_covers_shading_and_uvs(self):
        result = imported_mesh_cleanup()
        assert "shade_auto_smooth" in result
        assert "smart_uv_project" in result

    def test_names_common_sources(self):
        result = imported_mesh_cleanup().lower()
        assert "scan" in result
        assert "generated" in result

    def test_reanalyzes_after_repair(self):
        result = imported_mesh_cleanup()
        assert result.count("analyze_mesh_quality") >= 2

    def test_ends_with_visual_check(self):
        result = imported_mesh_cleanup()
        assert "get_viewport_screenshot" in result

    def test_frames_object_before_screenshot(self):
        result = imported_mesh_cleanup()
        assert "focus_on_object" in result
        assert result.index("focus_on_object") < result.index("get_viewport_screenshot")

    def test_uses_import_result_names(self):
        result = imported_mesh_cleanup()
        assert "imported_objects" in result
