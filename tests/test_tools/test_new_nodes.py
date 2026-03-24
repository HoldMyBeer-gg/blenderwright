"""Tests for new Blender 5.1 shader node types."""

import pytest
from blend_ai.tools.materials import ALLOWED_SHADER_NODE_TYPES


class TestNew51ShaderNodes:
    def test_raycast_node_in_allowlist(self):
        """ShaderNodeRaycast is in ALLOWED_SHADER_NODE_TYPES."""
        assert "ShaderNodeRaycast" in ALLOWED_SHADER_NODE_TYPES

    def test_existing_nodes_still_present(self):
        """Existing nodes are still in the allowlist."""
        assert "ShaderNodeBsdfPrincipled" in ALLOWED_SHADER_NODE_TYPES
        assert "ShaderNodeMix" in ALLOWED_SHADER_NODE_TYPES
        assert "ShaderNodeTexImage" in ALLOWED_SHADER_NODE_TYPES

    def test_raycast_passes_validation(self):
        """ShaderNodeRaycast passes validate_enum."""
        from blend_ai.validators import validate_enum
        result = validate_enum(
            "ShaderNodeRaycast", ALLOWED_SHADER_NODE_TYPES, name="node_type"
        )
        assert result == "ShaderNodeRaycast"
