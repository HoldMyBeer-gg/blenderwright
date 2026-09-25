"""Tests for the sweep handler's path geometry.

These cover the two ways a swept tube silently produces a broken solid while
every ordinary mesh check still passes:

1. A frame flip. Orienting each ring from a fixed world up-vector makes the
   ring rotation jump the moment the path turns near-vertical, shearing the
   band between two adjacent rings into a fold. Parallel transport cannot do
   this, and the property below pins that.
2. A bend tighter than the profile. If the centreline's radius of curvature
   drops below the profile radius, consecutive rings pass through each other.

Neither shows up as a non-manifold edge, a loose vertex or a degenerate face,
so neither is caught by analyze_mesh_quality. They have to be tested here.
"""

import math
import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_sweep_handler():
    """Load addon.handlers.sweep without triggering addon/handlers/__init__.py."""
    mock_dispatcher = MagicMock()
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher
    sys.modules["bmesh"] = MagicMock()

    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "addon", "handlers", "sweep.py"
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.sweep", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.sweep"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sweep():
    return _load_sweep_handler()


def _angle(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return math.acos(max(-1.0, min(1.0, dot)))


# The path that broke the wishing-well hose: vertical up, arc over, vertical
# down. Both ends cross the threshold where a fixed up-vector flips.
VERTICAL_ENDED_PATH = (
    [(0.0, 0.0, z) for z in (0.0, 2.0, 4.0, 6.0)]
    + [(2.0, 0.0, 8.0), (5.0, 0.0, 10.0), (9.0, 0.0, 10.0), (12.0, 0.0, 8.0)]
    + [(14.0, 0.0, 6.0)]
    + [(14.0, 0.0, z) for z in (4.0, 2.0, 0.0)]
)


class TestParallelTransportFrames:
    def test_frames_are_orthonormal(self, sweep):
        frames = sweep.parallel_transport_frames(VERTICAL_ENDED_PATH)
        assert len(frames) == len(VERTICAL_ENDED_PATH)
        for tangent, normal, binormal in frames:
            for vec in (tangent, normal, binormal):
                assert math.isclose(
                    math.sqrt(sum(c * c for c in vec)), 1.0, abs_tol=1e-9
                )
            assert abs(sum(a * b for a, b in zip(tangent, normal))) < 1e-9
            assert abs(sum(a * b for a, b in zip(tangent, binormal))) < 1e-9
            assert abs(sum(a * b for a, b in zip(normal, binormal))) < 1e-9

    def test_normal_never_rotates_more_than_the_tangent(self, sweep):
        """The defining property of parallel transport, and the regression test.

        Transporting by the minimal rotation between consecutive tangents means
        the normal can never turn further than the tangent does. A fixed
        up-vector frame violates this by ~90 degrees where the path goes
        vertical, which is exactly the fold.
        """
        frames = sweep.parallel_transport_frames(VERTICAL_ENDED_PATH)
        for i in range(1, len(frames)):
            tangent_turn = _angle(frames[i - 1][0], frames[i][0])
            normal_turn = _angle(frames[i - 1][1], frames[i][1])
            assert normal_turn <= tangent_turn + 1e-6, (
                f"frame flipped at station {i}: normal turned "
                f"{math.degrees(normal_turn):.1f} deg while the tangent turned "
                f"{math.degrees(tangent_turn):.1f} deg"
            )

    def test_no_flip_on_a_purely_vertical_path(self, sweep):
        """A straight vertical path is the degenerate case for a Z up-vector."""
        straight_up = [(0.0, 0.0, float(z)) for z in range(10)]
        frames = sweep.parallel_transport_frames(straight_up)
        for i in range(1, len(frames)):
            assert _angle(frames[i - 1][1], frames[i][1]) < 1e-6

    def test_handles_path_reversing_direction_in_z(self, sweep):
        """Up then down: the tangent's z crosses zero and changes sign."""
        frames = sweep.parallel_transport_frames(VERTICAL_ENDED_PATH)
        z_signs = {1 if f[0][2] > 0 else -1 for f in frames if abs(f[0][2]) > 0.5}
        assert z_signs == {1, -1}, "test path should genuinely reverse in z"

    def test_twist_is_applied_evenly(self, sweep):
        """A requested twist should accumulate along the path, not jump."""
        frames = sweep.parallel_transport_frames(
            VERTICAL_ENDED_PATH, twist=math.pi / 2
        )
        plain = sweep.parallel_transport_frames(VERTICAL_ENDED_PATH)
        first = _angle(plain[0][1], frames[0][1])
        last = _angle(plain[-1][1], frames[-1][1])
        assert first < 1e-6
        assert math.isclose(last, math.pi / 2, abs_tol=1e-6)

    def test_rejects_too_few_points(self, sweep):
        with pytest.raises(ValueError):
            sweep.parallel_transport_frames([(0.0, 0.0, 0.0)])


class TestCurvature:
    def test_straight_line_has_infinite_radius(self, sweep):
        line = [(float(i), 0.0, 0.0) for i in range(5)]
        for r in sweep.curvature_radii(line)[1:-1]:
            assert r == float("inf")

    def test_circular_arc_recovers_its_radius(self, sweep):
        radius = 5.0
        arc = [
            (radius * math.cos(a * 0.1), radius * math.sin(a * 0.1), 0.0)
            for a in range(12)
        ]
        for r in sweep.curvature_radii(arc)[1:-1]:
            assert math.isclose(r, radius, rel_tol=1e-6)

    def test_endpoints_are_not_constrained(self, sweep):
        arc = [(math.cos(a * 0.2), math.sin(a * 0.2), 0.0) for a in range(6)]
        radii = sweep.curvature_radii(arc)
        assert radii[0] == float("inf")
        assert radii[-1] == float("inf")


class TestAnalyzePath:
    def test_flags_a_bend_tighter_than_the_profile(self, sweep):
        """A 2mm-radius bend cannot carry a 4mm-radius tube."""
        arc = [
            (2.0 * math.cos(a * 0.25), 2.0 * math.sin(a * 0.25), 0.0)
            for a in range(14)
        ]
        report = sweep.analyze_path(arc, radius=4.0)
        assert report["self_intersects"] is True
        assert report["min_clearance_ratio"] < 1.0
        assert 0 <= report["tightest_index"] < len(arc)

    def test_passes_a_bend_wider_than_the_profile(self, sweep):
        arc = [
            (20.0 * math.cos(a * 0.1), 20.0 * math.sin(a * 0.1), 0.0)
            for a in range(14)
        ]
        report = sweep.analyze_path(arc, radius=2.0)
        assert report["self_intersects"] is False
        assert report["min_clearance_ratio"] >= 1.0

    def test_straight_path_is_always_clear(self, sweep):
        line = [(float(i), 0.0, 0.0) for i in range(6)]
        report = sweep.analyze_path(line, radius=100.0)
        assert report["self_intersects"] is False

    def test_reports_the_tightest_location(self, sweep):
        """A path that is straight, then kinks, should point at the kink."""
        path = [(float(i), 0.0, 0.0) for i in range(6)]
        path += [(5.0 + 0.4 * i, 0.9 * i, 0.0) for i in range(1, 6)]
        report = sweep.analyze_path(path, radius=1.0)
        assert 4 <= report["tightest_index"] <= 7


class TestResamplePath:
    def test_passes_through_every_control_point(self, sweep):
        ctrl = [(0.0, 0.0, 0.0), (10.0, 0.0, 5.0), (20.0, 8.0, 5.0), (30.0, 8.0, 0.0)]
        out = sweep.resample_path(ctrl, samples_per_segment=8)
        for c in ctrl:
            assert any(
                all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(c, p))
                for p in out
            ), f"control point {c} is not on the resampled path"

    def test_uneven_spacing_does_not_cusp(self, sweep):
        """Uniform Catmull-Rom cusps here; centripetal must not.

        The control points are deliberately spaced 2mm then 40mm, the ratio
        that made the uniform form double back on itself.
        """
        ctrl = [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (42.0, 6.0, 0.0),
            (44.0, 6.0, 0.0),
        ]
        out = sweep.resample_path(ctrl, samples_per_segment=24)
        radii = sweep.curvature_radii(out)
        assert min(radii) > 0.2, "centreline doubles back on itself"

    def test_samples_scale_with_segment_count(self, sweep):
        ctrl = [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
        assert len(sweep.resample_path(ctrl, samples_per_segment=4)) == 9

    def test_zero_samples_returns_the_points_unchanged(self, sweep):
        ctrl = [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (10.0, 1.0, 0.0)]
        assert sweep.resample_path(ctrl, samples_per_segment=0) == ctrl

    def test_rejects_too_few_points(self, sweep):
        with pytest.raises(ValueError):
            sweep.resample_path([(0.0, 0.0, 0.0)], samples_per_segment=4)


class TestProfiles:
    def test_circle_has_the_requested_side_count(self, sweep):
        assert len(sweep.make_profile("CIRCLE", 2.0, 16)) == 16

    def test_circle_points_lie_on_the_radius(self, sweep):
        for u, v in sweep.make_profile("CIRCLE", 3.0, 12):
            assert math.isclose(math.hypot(u, v), 3.0, rel_tol=1e-9)

    def test_square_has_four_corners(self, sweep):
        assert len(sweep.make_profile("SQUARE", 1.0, 16)) == 4

    def test_profiles_wind_consistently(self, sweep):
        """Signed area must be positive for every profile, or caps flip."""
        for shape in ("CIRCLE", "SQUARE", "HEXAGON"):
            pts = sweep.make_profile(shape, 1.0, 12)
            area = sum(
                pts[i][0] * pts[(i + 1) % len(pts)][1]
                - pts[(i + 1) % len(pts)][0] * pts[i][1]
                for i in range(len(pts))
            )
            assert area > 0, f"{shape} winds the wrong way"

    def test_rejects_unknown_profile(self, sweep):
        with pytest.raises(ValueError):
            sweep.make_profile("TRAPEZOID", 1.0, 8)


class TestRegistration:
    def test_registers_both_commands(self, sweep):
        dispatcher = MagicMock()
        sweep.dispatcher = dispatcher
        sweep.register()
        registered = {c.args[0] for c in dispatcher.register_handler.call_args_list}
        assert "sweep_profile_along_path" in registered
        assert "analyze_sweep_path" in registered
