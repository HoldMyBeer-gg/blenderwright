"""Unit tests for expert prompt functions in workflows.py."""

import sys

# Ensure mcp.prompt() works as identity decorator (same as mcp.tool())
_server = sys.modules["blend_ai.server"]
_server.mcp.prompt.return_value = lambda fn: fn

from blend_ai.prompts.workflows import (  # noqa: E402
    topology_best_practices,
    scale_reference_guide,
    lighting_principles,
    studio_lighting_setup,
    character_basemesh_workflow,
    material_workflow_guide,
)


# ---------------------------------------------------------------------------
# TestTopologyPrompt
# ---------------------------------------------------------------------------


class TestTopologyPrompt:
    def test_returns_non_empty_string(self):
        result = topology_best_practices()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_quad(self):
        result = topology_best_practices()
        assert "quad" in result.lower()

    def test_contains_edge_loop_or_edge_flow(self):
        result = topology_best_practices()
        assert "edge loop" in result.lower() or "edge flow" in result.lower()

    def test_contains_modifier(self):
        result = topology_best_practices()
        assert "modifier" in result.lower()

    def test_contains_ngon(self):
        result = topology_best_practices()
        assert "n-gon" in result.lower() or "ngon" in result.lower()


# ---------------------------------------------------------------------------
# TestScalePrompt
# ---------------------------------------------------------------------------


class TestScalePrompt:
    def test_returns_non_empty_string(self):
        result = scale_reference_guide()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_meter_or_cm(self):
        result = scale_reference_guide()
        assert "meter" in result.lower() or "cm" in result.lower()

    def test_contains_at_least_three_real_world_objects(self):
        result = scale_reference_guide().lower()
        objects = ["door", "table", "person", "chair", "car", "cup", "smartphone", "ceiling"]
        found = sum(1 for obj in objects if obj in result)
        assert found >= 3, f"Expected at least 3 real-world object references, found {found}"


# ---------------------------------------------------------------------------
# TestLightingPrompt
# ---------------------------------------------------------------------------


class TestLightingPrompt:
    def test_returns_non_empty_string(self):
        result = lighting_principles()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_three_point_lighting(self):
        result = lighting_principles()
        assert "three-point" in result.lower() or "3-point" in result.lower()

    def test_contains_hdri(self):
        result = lighting_principles()
        assert "hdri" in result.upper()

    def test_contains_eevee_and_cycles(self):
        result = lighting_principles()
        assert "eevee" in result.lower()
        assert "cycles" in result.lower()


# ---------------------------------------------------------------------------
# TestStudioLightingWorkflow
# ---------------------------------------------------------------------------


class TestStudioLightingWorkflow:
    def test_returns_non_empty_string(self):
        result = studio_lighting_setup()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_numbered_steps(self):
        result = studio_lighting_setup()
        assert "1." in result
        assert "2." in result

    def test_contains_key_light(self):
        result = studio_lighting_setup()
        assert "key light" in result.lower()


# ---------------------------------------------------------------------------
# TestCharacterBasemeshWorkflow
# ---------------------------------------------------------------------------


class TestCharacterBasemeshWorkflow:
    def test_returns_non_empty_string(self):
        result = character_basemesh_workflow()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_numbered_steps(self):
        result = character_basemesh_workflow()
        assert "1." in result
        assert "2." in result

    def test_contains_mirror(self):
        result = character_basemesh_workflow()
        assert "mirror" in result.lower()


# ---------------------------------------------------------------------------
# TestMaterialWorkflowGuide
# ---------------------------------------------------------------------------


class TestMaterialWorkflowGuide:
    def test_returns_non_empty_string(self):
        result = material_workflow_guide()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_principled_bsdf(self):
        result = material_workflow_guide()
        assert "principled bsdf" in result.lower()

    def test_contains_roughness_and_metallic(self):
        result = material_workflow_guide()
        assert "roughness" in result.lower()
        assert "metallic" in result.lower()
