"""Tests for UV unwrap methods, checked against Blender 5.2's uv.unwrap enum."""

import pytest

from blenderwright.tools.uv import ALLOWED_UNWRAP_METHODS
from blenderwright.validators import ValidationError, validate_enum

# bpy.ops.uv.unwrap method enum in Blender 5.2.3
BLENDER_UNWRAP_METHODS = {"ANGLE_BASED", "CONFORMAL", "MINIMUM_STRETCH"}


class TestUnwrapMethods:
    def test_allowlist_matches_blender(self):
        assert ALLOWED_UNWRAP_METHODS == BLENDER_UNWRAP_METHODS

    def test_minimum_stretch_passes_validation(self):
        """Minimum Stretch is the SLIM unwrapper; Blender's identifier is MINIMUM_STRETCH."""
        assert validate_enum("MINIMUM_STRETCH", ALLOWED_UNWRAP_METHODS, name="method") == (
            "MINIMUM_STRETCH"
        )

    def test_slim_is_rejected(self):
        """SLIM is not a value Blender accepts."""
        with pytest.raises(ValidationError):
            validate_enum("SLIM", ALLOWED_UNWRAP_METHODS, name="method")
