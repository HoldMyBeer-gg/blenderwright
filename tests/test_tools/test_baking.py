"""Tests for bake_texture: maps baked into images with Cycles."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.baking import ALLOWED_BAKE_TYPES, bake_texture
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.baking.get_connection", return_value=mock):
        yield mock


def test_bake_types_match_blender_52():
    assert ALLOWED_BAKE_TYPES == {"COMBINED", "AO", "SHADOW", "POSITION", "NORMAL", "UV",
                                  "ROUGHNESS", "EMIT", "ENVIRONMENT", "DIFFUSE", "GLOSSY",
                                  "TRANSMISSION"}


def test_simple_bake(mock_conn, tmp_path):
    out = str(tmp_path / "albedo.png")
    bake_texture("Crate", "DIFFUSE", out)
    command, params = mock_conn.send_command.call_args[0]
    assert command == "bake_texture"
    assert params == {"object_name": "Crate", "bake_type": "DIFFUSE", "filepath": out,
                      "resolution": 1024, "margin": 16, "samples": 64,
                      "diffuse_color_only": True, "normal_space": "TANGENT"}
    assert mock_conn.send_command.call_args.kwargs["timeout"] >= 600


def test_high_to_low(mock_conn, tmp_path):
    out = str(tmp_path / "normal.png")
    bake_texture("Crate_low", "NORMAL", out, source_object="Crate_high", cage_extrusion=0.05,
                 max_ray_distance=0.2, resolution=2048)
    params = mock_conn.send_command.call_args[0][1]
    assert params["source_object"] == "Crate_high"
    assert (params["cage_extrusion"], params["max_ray_distance"]) == (0.05, 0.2)
    assert params["resolution"] == 2048


@pytest.mark.parametrize("kwargs", [
    {"bake_type": "ALBEDO"}, {"resolution": 32}, {"resolution": 9000}, {"resolution": 1000.5},
    {"margin": -1}, {"margin": 65}, {"samples": 0}, {"cage_extrusion": -0.1},
    {"normal_space": "WORLD"}, {"source_object": "a/b"},
])
def test_rejects_bad_input(mock_conn, tmp_path, kwargs):
    args = {"object_name": "Crate", "bake_type": "DIFFUSE",
            "filepath": str(tmp_path / "x.png"), **kwargs}
    with pytest.raises(ValidationError):
        bake_texture(**args)
    mock_conn.send_command.assert_not_called()


@pytest.mark.parametrize("name", ["x.blend", "x.py", "x"])
def test_only_image_files(mock_conn, tmp_path, name):
    with pytest.raises(ValidationError):
        bake_texture("Crate", "DIFFUSE", str(tmp_path / name))


def test_missing_directory_is_explained(mock_conn, tmp_path):
    with pytest.raises(ValidationError, match="does not exist"):
        bake_texture("Crate", "DIFFUSE", str(tmp_path / "nope" / "x.png"))


def test_same_source_and_target(mock_conn, tmp_path):
    with pytest.raises(ValidationError):
        bake_texture("Crate", "NORMAL", str(tmp_path / "n.png"), source_object="Crate")
