"""Shader nodes and modifiers that Blender 5.2 offers (each verified live)."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.materials import ALLOWED_SHADER_NODE_TYPES
from blenderwright.tools.modeling import ALLOWED_MODIFIER_TYPES, set_modifier_property
from blenderwright.validators import ValidationError

NEW_SHADER_NODES = {
    "ShaderNodeBackground", "ShaderNodeBsdfMetallic", "ShaderNodeBsdfSheen",
    "ShaderNodeBsdfRefraction", "ShaderNodeBsdfHairPrincipled", "ShaderNodeBsdfRayPortal",
    "ShaderNodeHoldout", "ShaderNodeAmbientOcclusion", "ShaderNodeBevel",
    "ShaderNodeWireframe", "ShaderNodeVertexColor", "ShaderNodeVolumeInfo",
    "ShaderNodeParticleInfo", "ShaderNodeHairInfo", "ShaderNodePointInfo",
    "ShaderNodeLightFalloff", "ShaderNodeTexWhiteNoise", "ShaderNodeTexGabor",
    "ShaderNodeTexIES", "ShaderNodeSeparateColor", "ShaderNodeCombineColor",
    "ShaderNodeFloatCurve", "ShaderNodeShaderToRGB", "ShaderNodeVectorDisplacement",
    "ShaderNodeVectorTransform", "ShaderNodeOutputAOV", "ShaderNodeOutputLight",
    "ShaderNodeRadialTiling", "ShaderNodeSqueeze", "ShaderNodeVolumeCoefficients",
}
NEW_MODIFIERS = {
    "NORMAL_EDIT", "DATA_TRANSFER", "UV_PROJECT", "UV_WARP", "VERTEX_WEIGHT_PROXIMITY",
    "VERTEX_WEIGHT_EDIT", "VERTEX_WEIGHT_MIX", "WARP", "LAPLACIANDEFORM", "BUILD",
    "MULTIRES", "OCEAN", "EXPLODE",
}


def test_new_shader_nodes_allowed():
    assert NEW_SHADER_NODES <= ALLOWED_SHADER_NODE_TYPES


def test_anisotropic_retired():
    """Merged into Glossy since 4.0; Glossy covers it."""
    assert "ShaderNodeBsdfAnisotropic" not in ALLOWED_SHADER_NODE_TYPES


def test_new_modifiers_allowed():
    assert NEW_MODIFIERS <= ALLOWED_MODIFIER_TYPES


class TestSetModifierPropertyInput:
    @pytest.fixture
    def mock_conn(self):
        mock = MagicMock()
        mock.send_command.return_value = {"status": "ok", "result": {}}
        with patch("blenderwright.tools.modeling.get_connection", return_value=mock):
            yield mock

    @pytest.mark.parametrize("value", [3, 2.5, True, "PROJECT", "Ground", [0, 0, 1]])
    def test_plain_values_pass(self, mock_conn, value):
        set_modifier_property("Cube", "Mod", "target", value)

    @pytest.mark.parametrize("prop, value", [
        ("__class__", 1), ("Levels", 1), ("a b", 1), ("levels", float("nan")),
        ("levels", {"x": 1}), ("levels", None), ("offset", [1, 2, 3, 4, 5]),
        ("name", "x" * 65),
    ])
    def test_rejected(self, mock_conn, prop, value):
        with pytest.raises(ValidationError):
            set_modifier_property("Cube", "Mod", prop, value)
        mock_conn.send_command.assert_not_called()
