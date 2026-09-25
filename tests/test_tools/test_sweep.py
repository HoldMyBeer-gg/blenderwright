"""Sweeping a profile along a 3D path, and checking a path before you sweep it.

A swept tube has two failure modes that every ordinary mesh check passes:
a frame flip where the path turns near-vertical, and a bend tighter than the
profile. Both produce a closed, manifold, non-degenerate mesh that is not a
solid. The handler owns the geometry; these tests own the input contract and
the fact that the validity report reaches the caller.
"""

import math
import pytest
from unittest.mock import MagicMock, patch

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blend_ai.tools.sweep.get_connection", return_value=mock):
        yield mock


SIMPLE_PATH = [[0.0, 0.0, 0.0], [0.0, 0.0, 5.0], [4.0, 0.0, 9.0]]


class TestSweepProfileAlongPath:
    def test_path_and_profile_are_sent(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        sweep_profile_along_path(path_points=SIMPLE_PATH, radius=2.0, sides=12)
        sent = mock_conn.send_command.call_args[0][1]
        assert sent["path_points"] == SIMPLE_PATH
        assert sent["radius"] == 2.0
        assert sent["sides"] == 12

    def test_command_name(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        sweep_profile_along_path(path_points=SIMPLE_PATH)
        assert mock_conn.send_command.call_args[0][0] == "sweep_profile_along_path"

    @pytest.mark.parametrize("shape", ["CIRCLE", "SQUARE", "HEXAGON"])
    def test_profile_shapes_accepted(self, mock_conn, shape):
        from blend_ai.tools.sweep import sweep_profile_along_path
        sweep_profile_along_path(path_points=SIMPLE_PATH, profile=shape)
        assert mock_conn.send_command.call_args[0][1]["profile"] == shape

    def test_unknown_profile_rejected(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=SIMPLE_PATH, profile="TRAPEZOID")

    def test_needs_at_least_two_points(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=[[0.0, 0.0, 0.0]])

    def test_points_must_be_three_dimensional(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=[[0.0, 0.0], [1.0, 1.0]])

    def test_point_components_must_be_numbers(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=[[0.0, 0.0, 0.0], [1.0, "x", 1.0]])

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_coordinates_rejected(self, mock_conn, bad):
        """NaN propagates silently through every vector op and out into the STL."""
        from blend_ai.tools.sweep import sweep_profile_along_path
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=[[0.0, 0.0, 0.0], [1.0, bad, 1.0]])

    def test_consecutive_duplicate_points_rejected(self, mock_conn):
        """A zero-length segment has no tangent, so the frame is undefined."""
        from blend_ai.tools.sweep import sweep_profile_along_path
        with pytest.raises(ValidationError):
            sweep_profile_along_path(
                path_points=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
            )

    def test_radius_must_be_positive(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=SIMPLE_PATH, radius=0.0)

    def test_sides_are_bounded(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=SIMPLE_PATH, sides=2)
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=SIMPLE_PATH, sides=1025)

    def test_path_length_is_bounded(self, mock_conn):
        """An unbounded path times out the socket rather than erroring."""
        from blend_ai.tools.sweep import sweep_profile_along_path
        from blend_ai.tools.sweep import MAX_PATH_POINTS
        too_many = [[float(i), 0.0, 0.0] for i in range(MAX_PATH_POINTS + 1)]
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=too_many)

    def test_resolution_is_bounded(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=SIMPLE_PATH, resolution=1001)

    def test_name_is_validated(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=SIMPLE_PATH, name="../etc/passwd")

    def test_twist_is_bounded(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        with pytest.raises(ValidationError):
            sweep_profile_along_path(path_points=SIMPLE_PATH, twist=1000.0)

    def test_twist_accepts_radians(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        sweep_profile_along_path(path_points=SIMPLE_PATH, twist=math.pi)
        assert mock_conn.send_command.call_args[0][1]["twist"] == math.pi

    def test_blender_error_is_raised(self, mock_conn):
        from blend_ai.tools.sweep import sweep_profile_along_path
        mock_conn.send_command.return_value = {"status": "error", "result": "boom"}
        with pytest.raises(RuntimeError, match="boom"):
            sweep_profile_along_path(path_points=SIMPLE_PATH)

    def test_validity_report_is_returned(self, mock_conn):
        """The caller must be told when the sweep is not a solid."""
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": {"name": "Sweep", "self_intersects": True,
                       "min_clearance_ratio": 0.4},
        }
        from blend_ai.tools.sweep import sweep_profile_along_path
        result = sweep_profile_along_path(path_points=SIMPLE_PATH)
        assert result["self_intersects"] is True
        assert result["min_clearance_ratio"] == 0.4


class TestAnalyzeSweepPath:
    def test_command_name_and_payload(self, mock_conn):
        from blend_ai.tools.sweep import analyze_sweep_path
        analyze_sweep_path(path_points=SIMPLE_PATH, radius=1.5)
        assert mock_conn.send_command.call_args[0][0] == "analyze_sweep_path"
        assert mock_conn.send_command.call_args[0][1]["radius"] == 1.5

    def test_same_path_validation_as_the_sweep(self, mock_conn):
        from blend_ai.tools.sweep import analyze_sweep_path
        with pytest.raises(ValidationError):
            analyze_sweep_path(path_points=[[0.0, 0.0, 0.0]], radius=1.0)

    def test_radius_must_be_positive(self, mock_conn):
        from blend_ai.tools.sweep import analyze_sweep_path
        with pytest.raises(ValidationError):
            analyze_sweep_path(path_points=SIMPLE_PATH, radius=-1.0)

    def test_blender_error_is_raised(self, mock_conn):
        from blend_ai.tools.sweep import analyze_sweep_path
        mock_conn.send_command.return_value = {"status": "error", "result": "nope"}
        with pytest.raises(RuntimeError, match="nope"):
            analyze_sweep_path(path_points=SIMPLE_PATH, radius=1.0)
