"""Unit tests for material tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.materials import (
    create_material,
    assign_material,
    set_material_color,
    set_material_property,
    create_principled_material,
    add_texture_node,
    set_material_blend_mode,
    list_materials,
    delete_material,
    duplicate_material,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.materials.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# create_material
# ---------------------------------------------------------------------------


class TestCreateMaterial:
    def test_valid(self, mock_conn):
        create_material("RedMetal")
        mock_conn.send_command.assert_called_once_with(
            "create_material", {"name": "RedMetal"}
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_material("")

    def test_invalid_chars_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_material("bad<>name")

    def test_name_too_long_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_material("a" * 64)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "exists"}
        with pytest.raises(RuntimeError):
            create_material("Mat")


# ---------------------------------------------------------------------------
# assign_material
# ---------------------------------------------------------------------------


class TestAssignMaterial:
    def test_valid(self, mock_conn):
        assign_material("Cube", "RedMetal")
        mock_conn.send_command.assert_called_once_with(
            "assign_material",
            {"object_name": "Cube", "material_name": "RedMetal"},
        )

    def test_empty_object_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            assign_material("", "RedMetal")

    def test_empty_material_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            assign_material("Cube", "")


# ---------------------------------------------------------------------------
# set_material_color
# ---------------------------------------------------------------------------


class TestSetMaterialColor:
    def test_valid_rgba(self, mock_conn):
        set_material_color("Mat", [1.0, 0.0, 0.0, 1.0])
        mock_conn.send_command.assert_called_once_with(
            "set_material_color",
            {"material_name": "Mat", "color": [1.0, 0.0, 0.0, 1.0]},
        )

    def test_valid_rgb_auto_alpha(self, mock_conn):
        set_material_color("Mat", [0.5, 0.5, 0.5])
        args = mock_conn.send_command.call_args[0][1]
        assert args["color"] == [0.5, 0.5, 0.5, 1.0]

    def test_invalid_color_too_many_components(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_color("Mat", [1, 0, 0, 1, 1])

    def test_invalid_color_out_of_range(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_color("Mat", [2.0, 0, 0, 1])

    def test_invalid_color_negative(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_color("Mat", [-0.1, 0, 0])

    def test_invalid_color_not_list(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_color("Mat", "red")

    def test_empty_material_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_color("", [1, 0, 0, 1])


# ---------------------------------------------------------------------------
# set_material_property
# ---------------------------------------------------------------------------


class TestSetMaterialProperty:
    def test_valid_metallic(self, mock_conn):
        set_material_property("Mat", "metallic", 1.0)
        mock_conn.send_command.assert_called_once_with(
            "set_material_property",
            {"material_name": "Mat", "property": "metallic", "value": 1.0},
        )

    def test_valid_roughness(self, mock_conn):
        set_material_property("Mat", "roughness", 0.5)
        args = mock_conn.send_command.call_args[0][1]
        assert args["property"] == "roughness"
        assert args["value"] == 0.5

    def test_valid_ior(self, mock_conn):
        set_material_property("Mat", "ior", 1.45)
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == 1.45

    def test_valid_emission_strength(self, mock_conn):
        set_material_property("Mat", "emission_strength", 10.0)
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == 10.0

    def test_invalid_property_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_property("Mat", "fake_property", 1.0)

    def test_metallic_out_of_range_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_property("Mat", "metallic", 1.5)

    def test_roughness_negative_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_property("Mat", "roughness", -0.1)

    def test_ior_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_property("Mat", "ior", 200.0)

    def test_emission_color_valid(self, mock_conn):
        set_material_property("Mat", "emission_color", [1.0, 0.5, 0.0, 1.0])
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == [1.0, 0.5, 0.0, 1.0]

    def test_emission_color_invalid_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_property("Mat", "emission_color", "red")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_material_property("Mat", "metallic", 0.5)


# ---------------------------------------------------------------------------
# create_principled_material
# ---------------------------------------------------------------------------


class TestCreatePrincipledMaterial:
    def test_defaults(self, mock_conn):
        create_principled_material("Mat")
        args = mock_conn.send_command.call_args[0][1]
        assert args["name"] == "Mat"
        assert args["color"] == [0.8, 0.8, 0.8, 1.0]
        assert args["metallic"] == 0.0
        assert args["roughness"] == 0.5
        assert args["specular"] == 0.5
        assert args["emission_strength"] == 0.0
        assert args["alpha"] == 1.0
        assert args["transmission"] == 0.0
        assert args["ior"] == 1.45

    def test_custom_params(self, mock_conn):
        create_principled_material(
            "Gold",
            color=[1.0, 0.8, 0.0, 1.0],
            metallic=1.0,
            roughness=0.3,
        )
        args = mock_conn.send_command.call_args[0][1]
        assert args["name"] == "Gold"
        assert args["metallic"] == 1.0
        assert args["roughness"] == 0.3

    def test_rgb_color_gets_alpha(self, mock_conn):
        create_principled_material("Mat", color=[0.5, 0.5, 0.5])
        args = mock_conn.send_command.call_args[0][1]
        assert args["color"] == [0.5, 0.5, 0.5, 1.0]

    def test_metallic_out_of_range_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_principled_material("Mat", metallic=2.0)

    def test_roughness_negative_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_principled_material("Mat", roughness=-0.1)

    def test_alpha_out_of_range_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_principled_material("Mat", alpha=1.5)

    def test_transmission_out_of_range_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_principled_material("Mat", transmission=2.0)

    def test_ior_out_of_range_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_principled_material("Mat", ior=200.0)

    def test_invalid_color_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_principled_material("Mat", color="red")

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_principled_material("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            create_principled_material("Mat")


# ---------------------------------------------------------------------------
# add_texture_node
# ---------------------------------------------------------------------------


class TestAddTextureNode:
    def test_valid(self, mock_conn, tmp_path):
        img = tmp_path / "texture.png"
        img.write_bytes(b"fake png")
        add_texture_node("Mat", str(img))
        args = mock_conn.send_command.call_args[0][1]
        assert args["material_name"] == "Mat"
        assert args["image_path"] == str(img.resolve())
        assert args["label"] == "Image Texture"

    def test_nonexistent_file_raises(self, mock_conn):
        with pytest.raises(ValidationError, match="does not exist"):
            add_texture_node("Mat", "/nonexistent/texture.png")

    def test_invalid_extension_raises(self, mock_conn, tmp_path):
        bad = tmp_path / "texture.mp4"
        bad.write_bytes(b"fake")
        with pytest.raises(ValidationError, match="not allowed"):
            add_texture_node("Mat", str(bad))

    def test_empty_material_name_raises(self, mock_conn, tmp_path):
        img = tmp_path / "texture.png"
        img.write_bytes(b"fake")
        with pytest.raises(ValidationError):
            add_texture_node("", str(img))


# ---------------------------------------------------------------------------
# set_material_blend_mode
# ---------------------------------------------------------------------------


class TestSetMaterialBlendMode:
    def test_valid_opaque(self, mock_conn):
        set_material_blend_mode("Mat", "OPAQUE")
        mock_conn.send_command.assert_called_once_with(
            "set_material_blend_mode",
            {"material_name": "Mat", "mode": "OPAQUE"},
        )

    def test_valid_blend(self, mock_conn):
        set_material_blend_mode("Mat", "BLEND")
        args = mock_conn.send_command.call_args[0][1]
        assert args["mode"] == "BLEND"

    def test_valid_clip(self, mock_conn):
        set_material_blend_mode("Mat", "CLIP")
        args = mock_conn.send_command.call_args[0][1]
        assert args["mode"] == "CLIP"

    def test_valid_hashed(self, mock_conn):
        set_material_blend_mode("Mat", "HASHED")
        args = mock_conn.send_command.call_args[0][1]
        assert args["mode"] == "HASHED"

    def test_invalid_mode_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_blend_mode("Mat", "ADDITIVE")

    def test_empty_material_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_material_blend_mode("", "OPAQUE")


# ---------------------------------------------------------------------------
# list_materials
# ---------------------------------------------------------------------------


class TestListMaterials:
    def test_sends_correct_command(self, mock_conn):
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": [{"name": "Mat", "users": 1}],
        }
        result = list_materials()
        mock_conn.send_command.assert_called_once_with("list_materials", None)
        assert result == [{"name": "Mat", "users": 1}]

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            list_materials()


# ---------------------------------------------------------------------------
# delete_material
# ---------------------------------------------------------------------------


class TestDeleteMaterial:
    def test_valid(self, mock_conn):
        delete_material("OldMat")
        mock_conn.send_command.assert_called_once_with(
            "delete_material", {"material_name": "OldMat"}
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            delete_material("")

    def test_invalid_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            delete_material("bad;name")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "not found"}
        with pytest.raises(RuntimeError):
            delete_material("Mat")


# ---------------------------------------------------------------------------
# duplicate_material
# ---------------------------------------------------------------------------


class TestDuplicateMaterial:
    def test_valid(self, mock_conn):
        duplicate_material("Mat", "Mat.001")
        mock_conn.send_command.assert_called_once_with(
            "duplicate_material",
            {"material_name": "Mat", "new_name": "Mat.001"},
        )

    def test_empty_source_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            duplicate_material("", "NewMat")

    def test_empty_new_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            duplicate_material("Mat", "")

    def test_invalid_new_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            duplicate_material("Mat", "bad<>name")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            duplicate_material("Mat", "Mat.001")
