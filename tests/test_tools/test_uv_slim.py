"""Tests for SLIM UV unwrap method (Blender 5.1)."""

import pytest
from blend_ai.tools.uv import ALLOWED_UNWRAP_METHODS


class TestSlimUnwrapMethod:
    def test_slim_in_allowed_methods(self):
        """SLIM is in ALLOWED_UNWRAP_METHODS."""
        assert "SLIM" in ALLOWED_UNWRAP_METHODS

    def test_angle_based_still_allowed(self):
        """ANGLE_BASED is still allowed."""
        assert "ANGLE_BASED" in ALLOWED_UNWRAP_METHODS

    def test_conformal_still_allowed(self):
        """CONFORMAL is still allowed."""
        assert "CONFORMAL" in ALLOWED_UNWRAP_METHODS

    def test_slim_passes_validation(self):
        """SLIM passes validate_enum."""
        from blend_ai.validators import validate_enum
        result = validate_enum("SLIM", ALLOWED_UNWRAP_METHODS, name="method")
        assert result == "SLIM"
