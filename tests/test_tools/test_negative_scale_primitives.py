"""A negative scale on a fresh primitive means "point it the other way".

A local model building a shuttle sent scale=[7, 4, -1] for a cone five times
in one session, re-reading an error that told it to rotate instead and then
sending a negative scale again. Fighting the habit cost a fifth of its budget.

A primitive is symmetric about its own axis, so on create_object a negative
component is exactly a positive one plus a half turn, or nothing at all. Do
that, and say so in the result. set_scale on an existing object keeps the
error: an arbitrary mesh is not symmetric and a mirror there is a mistake.
"""

import math
from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.objects import create_object, normalise_primitive_scale
from blenderwright.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"name": "Cone"}}
    with patch("blenderwright.tools.objects.get_connection", return_value=mock):
        yield mock


class TestNormalise:
    def test_positive_scale_is_untouched(self):
        scale, rotation, note = normalise_primitive_scale("CONE", (1, 2, 3), (0.1, 0.2, 0.3))
        assert scale == (1, 2, 3)
        assert rotation == (0.1, 0.2, 0.3)
        assert note is None

    def test_cone_negative_z_becomes_a_half_turn_about_x(self):
        scale, rotation, note = normalise_primitive_scale("CONE", (7, 4, -1), (0, 0, 0))
        assert scale == (7, 4, 1)
        assert rotation == pytest.approx((math.pi, 0, 0))
        assert "rotat" in note.lower()

    def test_half_turn_composes_with_a_given_rotation(self):
        _, rotation, _ = normalise_primitive_scale("CYLINDER", (1, 1, -2), (0.5, 0.25, 0.1))
        assert rotation == pytest.approx((0.5 + math.pi, 0.25, 0.1))

    @pytest.mark.parametrize("axis", [0, 1])
    def test_cone_negative_x_or_y_is_a_no_op_mirror(self, axis):
        # A cone mirrored across its own axis looks identical.
        scale = [3, 3, 5]
        scale[axis] = -3
        out, rotation, note = normalise_primitive_scale("CONE", tuple(scale), (0, 0, 0))
        assert out == (3, 3, 5)
        assert rotation == (0, 0, 0)
        assert note and "no visible" in note.lower()

    @pytest.mark.parametrize("kind", ["CUBE", "SPHERE", "UV_SPHERE", "ICO_SPHERE", "TORUS"])
    def test_fully_symmetric_primitives_just_take_abs(self, kind):
        scale, rotation, note = normalise_primitive_scale(kind, (-1, -2, -3), (0, 0, 0))
        assert scale == (1, 2, 3)
        assert rotation == (0, 0, 0)
        assert note

    @pytest.mark.parametrize("kind", ["PLANE", "CIRCLE"])
    def test_flat_primitives_flip_their_normal_with_a_half_turn(self, kind):
        scale, rotation, _ = normalise_primitive_scale(kind, (2, 2, -1), (0, 0, 0))
        assert scale == (2, 2, 1)
        assert rotation == pytest.approx((math.pi, 0, 0))

    @pytest.mark.parametrize("kind", ["MONKEY", "EMPTY"])
    def test_asymmetric_or_empty_is_left_for_the_validator(self, kind):
        scale, rotation, note = normalise_primitive_scale(kind, (1, 1, -1), (0, 0, 0))
        assert scale == (1, 1, -1)
        assert note is None

    def test_zero_is_not_touched(self):
        # Zero is a different mistake with a different message.
        scale, _, note = normalise_primitive_scale("CONE", (1, 1, 0), (0, 0, 0))
        assert scale == (1, 1, 0)
        assert note is None


class TestCreateObject:
    def test_negative_cone_is_created_rotated(self, mock_conn):
        result = create_object("CONE", name="nose", scale=[7, 4, -1])
        params = mock_conn.send_command.call_args.args[1]
        assert params["scale"] == [7, 4, 1]
        assert params["rotation"] == pytest.approx([math.pi, 0, 0])
        assert "note" in result
        assert "rotat" in result["note"].lower()

    def test_positive_scale_adds_no_note(self, mock_conn):
        result = create_object("CONE", name="nose", scale=[7, 4, 1])
        assert "note" not in result

    def test_monkey_with_negative_scale_still_errors(self, mock_conn):
        with pytest.raises(ValidationError, match="negative"):
            create_object("MONKEY", scale=[1, 1, -1])
        mock_conn.send_command.assert_not_called()

    def test_zero_scale_still_errors(self, mock_conn):
        with pytest.raises(ValidationError, match="zero"):
            create_object("CONE", scale=[1, 1, 0])
