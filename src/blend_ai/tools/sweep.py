"""MCP tools for sweeping a profile along a 3D path."""

from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    ValidationError,
    validate_enum,
    validate_numeric_range,
    validate_object_name,
)

ALLOWED_SWEEP_PROFILES = {"CIRCLE", "SQUARE", "HEXAGON", "TRIANGLE"}

# Mirrors the caps in addon/handlers/sweep.py. Duplicated deliberately: the
# addon socket is reachable by any local process, so the handler cannot trust
# this layer. Kept in step by tests/test_addon/test_layer_consistency.py.
MAX_PATH_POINTS = 2000
MAX_SIDES = 1024
MAX_RESOLUTION = 1000
MAX_TWIST = 100.0


def _validate_path_points(path_points: Any) -> list[list[float]]:
    """Check a path is usable before it reaches Blender.

    A zero-length segment leaves the tangent undefined, and a non-finite
    coordinate propagates through every vector operation without raising,
    landing in the exported mesh as NaN. Both are caught here.
    """
    if not isinstance(path_points, (list, tuple)):
        raise ValidationError("path_points must be a list of [x, y, z] points")
    if len(path_points) < 2:
        raise ValidationError(
            "path_points needs at least two points to define a direction")
    if len(path_points) > MAX_PATH_POINTS:
        raise ValidationError(
            f"path_points must have {MAX_PATH_POINTS} points or fewer, "
            f"got {len(path_points)}")

    cleaned: list[list[float]] = []
    for i, point in enumerate(path_points):
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            raise ValidationError(
                f"path point {i} must have exactly 3 components (x, y, z)")
        coords = []
        for axis, value in zip("xyz", point):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValidationError(
                    f"path point {i} component {axis} must be a number")
            value = float(value)
            if value != value or value in (float("inf"), float("-inf")):
                raise ValidationError(
                    f"path point {i} component {axis} must be finite")
            coords.append(value)
        if cleaned:
            prev = cleaned[-1]
            if all(abs(a - b) < 1e-9 for a, b in zip(coords, prev)):
                raise ValidationError(
                    f"path point {i} repeats point {i - 1}; a zero-length "
                    f"segment has no direction to orient the profile against")
        cleaned.append(coords)
    return cleaned


@mcp.tool()
def sweep_profile_along_path(
    path_points: list[list[float]],
    profile: str = "CIRCLE",
    radius: float = 1.0,
    sides: int = 16,
    resolution: int = 0,
    twist: float = 0.0,
    caps: bool = True,
    name: str = "Sweep",
) -> dict[str, Any]:
    """Sweep a closed profile along a 3D path to make a solid tube, pipe, cable or rope.

    Use this for anything that follows a route: hoses, handrails, wires, vines,
    tentacles, roads. It orients the profile with parallel transport, so the
    tube never creases or folds where the path turns vertical, and it reports
    whether any bend is too tight for the profile to fit around.

    Args:
        path_points: Centreline as a list of [x, y, z] points, in order. At
            least 2, at most 2000. Consecutive points must differ.
        profile: Cross-section shape - CIRCLE, SQUARE, HEXAGON, or TRIANGLE.
        radius: Distance from the centreline to the furthest point of the
            profile, in Blender units. Must be positive.
        sides: Number of sides for a CIRCLE profile (3-1024). Ignored by the
            fixed-sided profiles.
        resolution: Samples generated between each pair of path points, which
            smooths the path with a centripetal Catmull-Rom spline. 0 uses the
            points exactly as given. 8-16 gives a smooth curve.
        twist: Total rotation of the profile about the path from start to end,
            in radians. Spreads evenly along the path.
        caps: Close both ends. Leave True for a printable solid.
        name: Name for the created object.

    Returns:
        Dict with the object name, vertex and face counts, and a validity
        report: min_clearance_ratio (path curvature radius over profile radius
        at the tightest point), tightest_point, and self_intersects. A ratio
        below 1.0 means rings overlap inside the bend, so the result is
        watertight but is not a solid.
    """
    path_points = _validate_path_points(path_points)
    validate_enum(profile, ALLOWED_SWEEP_PROFILES, name="profile")
    radius = validate_numeric_range(radius, min_val=1e-6, max_val=10000.0, name="radius")
    sides = validate_numeric_range(sides, min_val=3, max_val=MAX_SIDES, name="sides")
    resolution = validate_numeric_range(
        resolution, min_val=0, max_val=MAX_RESOLUTION, name="resolution")
    twist = validate_numeric_range(
        twist, min_val=-MAX_TWIST, max_val=MAX_TWIST, name="twist")
    if not isinstance(caps, bool):
        raise ValidationError("caps must be true or false")
    name = validate_object_name(name)

    conn = get_connection()
    response = conn.send_command("sweep_profile_along_path", {
        "path_points": path_points,
        "profile": profile,
        "radius": radius,
        "sides": int(sides),
        "resolution": int(resolution),
        "twist": twist,
        "caps": caps,
        "name": name,
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def analyze_sweep_path(
    path_points: list[list[float]],
    radius: float = 1.0,
    resolution: int = 0,
) -> dict[str, Any]:
    """Check whether a path can carry a profile of a given radius, without building it.

    Where a path's radius of curvature falls below the profile radius, the
    swept rings pass through each other on the inside of the bend. The result
    still reports as watertight and manifold with no degenerate faces, so no
    ordinary mesh check catches it. Call this before sweeping, or to find
    where an existing path needs widening.

    Args:
        path_points: Centreline as a list of [x, y, z] points, in order.
        radius: Outer radius of the profile you intend to sweep.
        resolution: Samples between path points, matching what you will pass
            to sweep_profile_along_path so the check covers the same curve.

    Returns:
        Dict with min_clearance_ratio (curvature radius over profile radius at
        the tightest station; below 1.0 self-intersects), tightest_index,
        tightest_point, self_intersects, and counts of stations below 1.0 and
        below 1.5. Aim for 1.5 or more for a clean surface.
    """
    path_points = _validate_path_points(path_points)
    radius = validate_numeric_range(radius, min_val=1e-6, max_val=10000.0, name="radius")
    resolution = validate_numeric_range(
        resolution, min_val=0, max_val=MAX_RESOLUTION, name="resolution")

    conn = get_connection()
    response = conn.send_command("analyze_sweep_path", {
        "path_points": path_points,
        "radius": radius,
        "resolution": int(resolution),
    })
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
