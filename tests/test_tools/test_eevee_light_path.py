"""Tests for EEVEE light intensity controls.

This file previously had nine passing tests for a tool that had never worked
once. They asserted the payload the tool sends and never that Blender would
accept it, so they pinned three property names, light_path_diffuse_intensity
and two siblings, that exist in no Blender version. Every real call raised
AttributeError. Verified against a live Blender 5.1.

The tool now exposes what EEVEE Next actually has: direct_light_intensity and
indirect_light_intensity, with no per-lobe split.
"""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.tools.rendering import set_eevee_light_path
from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {
        "status": "ok",
        "result": {"direct_intensity": 1.0, "indirect_intensity": 1.0},
    }
    with patch("blend_ai.tools.rendering.get_connection", return_value=mock):
        yield mock


class TestSetEeveeLightIntensity:
    def test_sends_direct_intensity(self, mock_conn):
        set_eevee_light_path(direct_intensity=2.0)
        assert mock_conn.send_command.call_args[0][1] == {"direct_intensity": 2.0}

    def test_sends_indirect_intensity(self, mock_conn):
        set_eevee_light_path(indirect_intensity=0.5)
        assert mock_conn.send_command.call_args[0][1] == {"indirect_intensity": 0.5}

    def test_sends_both(self, mock_conn):
        set_eevee_light_path(direct_intensity=1.5, indirect_intensity=0.25)
        assert mock_conn.send_command.call_args[0][1] == {
            "direct_intensity": 1.5, "indirect_intensity": 0.25}

    def test_omitted_parameters_are_not_sent(self, mock_conn):
        """An unset parameter must leave the scene value alone."""
        set_eevee_light_path()
        assert mock_conn.send_command.call_args[0][1] == {}

    def test_returns_the_result(self, mock_conn):
        assert set_eevee_light_path(direct_intensity=1.0)["direct_intensity"] == 1.0

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "nope"}
        with pytest.raises(RuntimeError):
            set_eevee_light_path(direct_intensity=1.0)

    @pytest.mark.parametrize("value", [-0.1, 10.1])
    def test_out_of_range_direct_is_rejected(self, mock_conn, value):
        with pytest.raises(ValidationError):
            set_eevee_light_path(direct_intensity=value)

    @pytest.mark.parametrize("value", [-0.1, 10.1])
    def test_out_of_range_indirect_is_rejected(self, mock_conn, value):
        with pytest.raises(ValidationError):
            set_eevee_light_path(indirect_intensity=value)

    def test_numeric_strings_are_accepted(self, mock_conn):
        """Models send "1.5"; the validator coerces and the caller keeps it."""
        set_eevee_light_path(direct_intensity="1.5")
        assert mock_conn.send_command.call_args[0][1] == {"direct_intensity": 1.5}


class TestTheOldPropertiesAreGone:
    def test_tool_no_longer_mentions_light_path_properties(self):
        """Guard against the dead property names creeping back."""
        import inspect
        from blend_ai.tools import rendering
        source = inspect.getsource(rendering)
        for dead in ("light_path_diffuse_intensity", "light_path_glossy_intensity",
                     "light_path_transmission_intensity"):
            assert dead not in source, f"{dead} exists in no Blender version"
