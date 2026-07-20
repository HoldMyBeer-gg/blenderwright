"""Unit tests for procedural material presets.

These build a complete texture node graph in one command rather than by
composing primitives over ~40 round-trips, so the tool layer's job is
validation and forwarding; the graph construction is tested addon-side.
"""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.materials import (
    PROCEDURAL_PATTERNS,
    create_procedural_material,
    list_procedural_patterns,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.materials.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# Pattern table
# ---------------------------------------------------------------------------


class TestPatternTable:
    def test_covers_every_forge_pattern_except_runes(self):
        """The 13 patterns reproducible with native shader nodes.

        'runes' is deliberately absent: it stamps discrete glyphs, which no
        combination of shader nodes produces. It needs a raster path.
        """
        assert PROCEDURAL_PATTERNS == {
            "gradient", "noise", "cloud", "voronoi", "veins", "scales",
            "stripes", "wood", "marble", "weave", "plasma", "fire", "sparks",
        }

    def test_runes_is_not_claimed(self):
        assert "runes" not in PROCEDURAL_PATTERNS


# ---------------------------------------------------------------------------
# create_procedural_material
# ---------------------------------------------------------------------------


class TestCreateProceduralMaterial:
    def test_minimal_call(self, mock_conn):
        create_procedural_material("Lava", "fire")
        mock_conn.send_command.assert_called_once()
        command, params = mock_conn.send_command.call_args[0]
        assert command == "create_procedural_material"
        assert params["name"] == "Lava"
        assert params["pattern"] == "fire"

    def test_defaults(self, mock_conn):
        create_procedural_material("M", "noise")
        params = mock_conn.send_command.call_args[0][1]
        assert params["scale"] == 5.0
        assert params["detail"] == 2.0
        assert params["distortion"] == 0.0
        assert params["roughness"] == 0.5
        assert params["metallic"] == 0.0
        assert params["connect_to_bsdf"] is True

    def test_custom_scale_and_detail(self, mock_conn):
        create_procedural_material("M", "wood", scale=12.0, detail=6.0)
        params = mock_conn.send_command.call_args[0][1]
        assert params["scale"] == 12.0
        assert params["detail"] == 6.0

    def test_custom_colors_forwarded(self, mock_conn):
        create_procedural_material(
            "M", "fire", colors=[[0.0, 0.0, 0.0, 1.0], [1.0, 0.3, 0.0, 1.0]]
        )
        params = mock_conn.send_command.call_args[0][1]
        assert params["colors"] == [[0.0, 0.0, 0.0, 1.0], [1.0, 0.3, 0.0, 1.0]]

    def test_rgb_colors_padded_to_rgba(self, mock_conn):
        create_procedural_material("M", "fire", colors=[[1.0, 0.0, 0.0]])
        params = mock_conn.send_command.call_args[0][1]
        assert params["colors"] == [[1.0, 0.0, 0.0, 1.0]]

    def test_colors_omitted_when_not_given(self, mock_conn):
        """Omitted colors let the addon apply the pattern's own palette."""
        create_procedural_material("M", "fire")
        params = mock_conn.send_command.call_args[0][1]
        assert "colors" not in params

    def test_banded_flag(self, mock_conn):
        create_procedural_material("M", "voronoi", banded=True)
        params = mock_conn.send_command.call_args[0][1]
        assert params["banded"] is True

    def test_connect_to_bsdf_false(self, mock_conn):
        create_procedural_material("M", "noise", connect_to_bsdf=False)
        params = mock_conn.send_command.call_args[0][1]
        assert params["connect_to_bsdf"] is False

    def test_every_pattern_is_accepted(self, mock_conn):
        for pattern in sorted(PROCEDURAL_PATTERNS):
            mock_conn.send_command.reset_mock()
            create_procedural_material("M", pattern)
            assert mock_conn.send_command.call_args[0][1]["pattern"] == pattern

    def test_returns_result(self, mock_conn):
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": {"material": "Lava", "nodes": ["Noise", "ColorRamp"]},
        }
        result = create_procedural_material("Lava", "fire")
        assert result["material"] == "Lava"


class TestCreateProceduralMaterialValidation:
    def test_unknown_pattern_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "runes")

    def test_misspelled_pattern_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "fyre")

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("", "noise")

    def test_scale_zero_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", scale=0.0)

    def test_negative_scale_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", scale=-1.0)

    def test_excessive_scale_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", scale=10001.0)

    def test_negative_detail_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", detail=-1.0)

    def test_excessive_detail_raises(self, mock_conn):
        """Blender caps Noise detail at 15."""
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", detail=16.0)

    def test_negative_distortion_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", distortion=-0.1)

    def test_roughness_above_one_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", roughness=1.5)

    def test_metallic_above_one_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", metallic=1.5)

    def test_single_color_stop_is_allowed(self, mock_conn):
        create_procedural_material("M", "noise", colors=[[1.0, 0.0, 0.0, 1.0]])
        assert mock_conn.send_command.called

    def test_empty_colors_list_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", colors=[])

    def test_too_many_colors_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material(
                "M", "noise", colors=[[0.0, 0.0, 0.0, 1.0]] * 33
            )

    def test_malformed_color_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", colors=[[1.0, 0.0]])

    def test_out_of_range_color_component_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", colors=[[1.5, 0.0, 0.0, 1.0]])

    def test_colors_not_a_list_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_procedural_material("M", "noise", colors="red")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            create_procedural_material("M", "noise")


# ---------------------------------------------------------------------------
# list_procedural_patterns
# ---------------------------------------------------------------------------


class TestListProceduralPatterns:
    def test_is_local_and_makes_no_call(self, mock_conn):
        """The table is static, so listing must not hit Blender."""
        list_procedural_patterns()
        mock_conn.send_command.assert_not_called()

    def test_lists_every_pattern(self, mock_conn):
        result = list_procedural_patterns()
        assert set(result["patterns"]) == PROCEDURAL_PATTERNS

    def test_each_pattern_has_a_description(self, mock_conn):
        result = list_procedural_patterns()
        for pattern in PROCEDURAL_PATTERNS:
            assert result["descriptions"][pattern].strip()

    def test_sorted_for_stable_output(self, mock_conn):
        result = list_procedural_patterns()
        assert result["patterns"] == sorted(result["patterns"])
