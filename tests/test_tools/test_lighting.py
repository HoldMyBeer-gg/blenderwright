"""Unit tests for lighting tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.lighting import (
    create_light,
    set_light_property,
    set_world_background,
    create_light_rig,
    list_lights,
    delete_light,
    set_shadow_settings,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.lighting.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# create_light
# ---------------------------------------------------------------------------


class TestCreateLight:
    def test_valid_point(self, mock_conn):
        create_light("POINT", name="MyLight")
        mock_conn.send_command.assert_called_once_with(
            "create_light",
            {
                "type": "POINT",
                "name": "MyLight",
                "location": [0, 0, 0],
                "energy": 1000.0,
                "color": [1.0, 1.0, 1.0],
            },
        )

    def test_valid_sun(self, mock_conn):
        create_light("SUN")
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "SUN"

    def test_valid_spot(self, mock_conn):
        create_light("SPOT", location=[5, 5, 5], energy=500.0)
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "SPOT"
        assert args["location"] == [5, 5, 5]
        assert args["energy"] == 500.0

    def test_valid_area(self, mock_conn):
        create_light("AREA", color=[1.0, 0.5, 0.0])
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "AREA"
        assert args["color"] == [1.0, 0.5, 0.0]

    def test_invalid_type_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_light("NEON")

    def test_invalid_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_light("POINT", name="bad;name")

    def test_energy_negative_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_light("POINT", energy=-10)

    def test_energy_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_light("POINT", energy=20000000)

    def test_invalid_color_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_light("POINT", color="red")

    def test_invalid_location_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_light("POINT", location=[1, 2])

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            create_light("POINT")


# ---------------------------------------------------------------------------
# set_light_property
# ---------------------------------------------------------------------------


class TestSetLightProperty:
    def test_valid_energy(self, mock_conn):
        set_light_property("Light", "energy", 500.0)
        mock_conn.send_command.assert_called_once_with(
            "set_light_property",
            {"name": "Light", "property": "energy", "value": 500.0},
        )

    def test_valid_color(self, mock_conn):
        set_light_property("Light", "color", [1.0, 0.5, 0.0])
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == [1.0, 0.5, 0.0]

    def test_valid_use_shadow(self, mock_conn):
        set_light_property("Light", "use_shadow", True)
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] is True

    def test_valid_spot_size(self, mock_conn):
        set_light_property("Light", "spot_size", 1.0)
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == 1.0

    def test_valid_spot_blend(self, mock_conn):
        set_light_property("Light", "spot_blend", 0.5)
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == 0.5

    def test_valid_specular_factor(self, mock_conn):
        set_light_property("Light", "specular_factor", 0.8)
        args = mock_conn.send_command.call_args[0][1]
        assert args["value"] == 0.8

    def test_invalid_property_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_light_property("Light", "fake_prop", 1.0)

    def test_energy_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_light_property("Light", "energy", 20000000)

    def test_spot_blend_out_of_range_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_light_property("Light", "spot_blend", 1.5)

    def test_use_shadow_non_bool_raises(self, mock_conn):
        with pytest.raises(ValidationError, match="use_shadow must be a boolean"):
            set_light_property("Light", "use_shadow", 1)

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_light_property("", "energy", 100)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_light_property("Light", "energy", 100)


# ---------------------------------------------------------------------------
# set_world_background
# ---------------------------------------------------------------------------


class TestSetWorldBackground:
    def test_valid_color(self, mock_conn):
        set_world_background(color=[0.5, 0.5, 0.8])
        args = mock_conn.send_command.call_args[0][1]
        assert args["color"] == [0.5, 0.5, 0.8]
        assert args["strength"] == 1.0
        assert "hdri_path" not in args

    def test_valid_hdri(self, mock_conn, tmp_path):
        hdri = tmp_path / "env.hdr"
        hdri.write_bytes(b"fake hdr")
        set_world_background(hdri_path=str(hdri))
        args = mock_conn.send_command.call_args[0][1]
        assert args["hdri_path"] == str(hdri.resolve())
        assert "color" not in args

    def test_custom_strength(self, mock_conn):
        set_world_background(color=[1, 1, 1], strength=2.0)
        args = mock_conn.send_command.call_args[0][1]
        assert args["strength"] == 2.0

    def test_neither_color_nor_hdri_raises(self, mock_conn):
        with pytest.raises(ValidationError, match="Must provide either"):
            set_world_background()

    def test_both_color_and_hdri_raises(self, mock_conn, tmp_path):
        hdri = tmp_path / "env.hdr"
        hdri.write_bytes(b"fake")
        with pytest.raises(ValidationError, match="Cannot set both"):
            set_world_background(color=[1, 1, 1], hdri_path=str(hdri))

    def test_invalid_color_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_world_background(color="blue")

    def test_nonexistent_hdri_raises(self, mock_conn):
        with pytest.raises(ValidationError, match="does not exist"):
            set_world_background(hdri_path="/nonexistent/env.hdr")

    def test_invalid_hdri_extension_raises(self, mock_conn, tmp_path):
        bad = tmp_path / "env.mp4"
        bad.write_bytes(b"fake")
        with pytest.raises(ValidationError, match="not allowed"):
            set_world_background(hdri_path=str(bad))

    def test_strength_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_world_background(color=[1, 1, 1], strength=5000)


# ---------------------------------------------------------------------------
# create_light_rig
# ---------------------------------------------------------------------------


class TestCreateLightRig:
    def test_valid_three_point(self, mock_conn):
        create_light_rig("THREE_POINT")
        mock_conn.send_command.assert_called_once_with(
            "create_light_rig",
            {"type": "THREE_POINT", "target": "", "intensity": 1000.0},
        )

    def test_valid_studio(self, mock_conn):
        create_light_rig("STUDIO", target="Cube", intensity=500.0)
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "STUDIO"
        assert args["target"] == "Cube"
        assert args["intensity"] == 500.0

    def test_valid_rim(self, mock_conn):
        create_light_rig("RIM")
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "RIM"

    def test_valid_outdoor(self, mock_conn):
        create_light_rig("OUTDOOR")
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "OUTDOOR"

    def test_invalid_type_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_light_rig("CINEMATIC")

    def test_invalid_target_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_light_rig("THREE_POINT", target="bad;name")

    def test_intensity_negative_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_light_rig("THREE_POINT", intensity=-1)

    def test_intensity_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_light_rig("THREE_POINT", intensity=20000000)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            create_light_rig("THREE_POINT")


# ---------------------------------------------------------------------------
# list_lights
# ---------------------------------------------------------------------------


class TestListLights:
    def test_sends_correct_command(self, mock_conn):
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": [{"name": "Light", "type": "POINT"}],
        }
        result = list_lights()
        mock_conn.send_command.assert_called_once_with("list_lights", None)
        assert result == [{"name": "Light", "type": "POINT"}]

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            list_lights()


# ---------------------------------------------------------------------------
# delete_light
# ---------------------------------------------------------------------------


class TestDeleteLight:
    def test_valid(self, mock_conn):
        delete_light("PointLight")
        mock_conn.send_command.assert_called_once_with(
            "delete_light", {"name": "PointLight"}
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            delete_light("")

    def test_invalid_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            delete_light("bad;name")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "not found"}
        with pytest.raises(RuntimeError):
            delete_light("Light")


# ---------------------------------------------------------------------------
# set_shadow_settings
# ---------------------------------------------------------------------------


class TestSetShadowSettings:
    def test_valid_defaults(self, mock_conn):
        set_shadow_settings("Light")
        mock_conn.send_command.assert_called_once_with(
            "set_shadow_settings",
            {"name": "Light", "use_shadow": True, "shadow_soft_size": 0.25},
        )

    def test_custom_values(self, mock_conn):
        set_shadow_settings("Light", use_shadow=False, shadow_soft_size=1.0)
        args = mock_conn.send_command.call_args[0][1]
        assert args["use_shadow"] is False
        assert args["shadow_soft_size"] == 1.0

    def test_use_shadow_non_bool_raises(self, mock_conn):
        with pytest.raises(ValidationError, match="use_shadow must be a boolean"):
            set_shadow_settings("Light", use_shadow=1)

    def test_shadow_soft_size_negative_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shadow_settings("Light", shadow_soft_size=-0.1)

    def test_shadow_soft_size_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shadow_settings("Light", shadow_soft_size=200.0)

    def test_shadow_soft_size_non_numeric_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shadow_settings("Light", shadow_soft_size="big")

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_shadow_settings("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_shadow_settings("Light")
