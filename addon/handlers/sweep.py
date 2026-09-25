"""Handlers for sweeping a profile along a 3D path.

Sweeping is the one piece of procedural modelling that fails silently. Both
of its failure modes produce a closed mesh with no non-manifold edges, no
loose vertices and no degenerate faces, so analyze_mesh_quality passes them
and the broken solid reaches the slicer:

Frame flip. The obvious way to orient each ring is to cross the tangent with
a fixed world up-vector, swapping the up-vector to another axis when the
tangent gets close to it. That swap is a discontinuity: the ring rotates
instantly, and the band of faces between those two stations shears into a
fold that reads as a crack with a sliver of surface through it. Any path
that turns near-vertical hits it. The fix is parallel transport: carry one
frame along the curve, rotating it by the minimal rotation that takes each
tangent to the next, so the ring orientation can never jump.

Bend tighter than the profile. Where the centreline's radius of curvature
drops below the profile radius, consecutive rings pass through each other on
the inside of the bend. Nothing in the mesh records this, so analyze_path
reports it as a ratio and the sweep returns it to the caller.

The geometry below is plain tuples and the math module so it stays testable,
and so the addon keeps its zero-dependency rule. bmesh is only used to turn
finished rings into a mesh.
"""

import math

import bmesh
import bpy

from .. import dispatcher

# A sweep is O(path x sides). Both are capped so a mistaken call cannot run
# past the socket's retry budget, which surfaces as a connection timeout
# rather than an error the caller can act on.
MAX_PATH_POINTS = 2000
MAX_SIDES = 1024
MAX_RESOLUTION = 1000
MAX_SWEEP_FACES = 2_000_000

ALLOWED_PROFILES = ("CIRCLE", "SQUARE", "HEXAGON", "TRIANGLE")

# Below this the tangent is undefined, so the point is a duplicate.
_MIN_SEGMENT = 1e-9


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a):
    return math.sqrt(_dot(a, a))


def _normalize(a):
    n = _length(a)
    if n < _MIN_SEGMENT:
        raise ValueError("cannot normalize a zero-length vector")
    return (a[0] / n, a[1] / n, a[2] / n)


def _rotate_about(vec, axis, angle):
    """Rodrigues rotation of vec about a unit axis."""
    c, s = math.cos(angle), math.sin(angle)
    return _add(
        _add(_scale(vec, c), _scale(_cross(axis, vec), s)),
        _scale(axis, _dot(axis, vec) * (1.0 - c)),
    )


def _tangents(points):
    """Central-difference tangent at every station."""
    n = len(points)
    out = []
    for i in range(n):
        nxt = points[min(i + 1, n - 1)]
        prv = points[max(i - 1, 0)]
        d = _sub(nxt, prv)
        if _length(d) < _MIN_SEGMENT:
            d = _sub(points[min(i + 1, n - 1)], points[i])
        out.append(_normalize(d))
    return out


def parallel_transport_frames(points, twist=0.0):
    """Rotation-minimizing frames along a path.

    Returns one (tangent, normal, binormal) triple per point. Each normal is
    the previous one carried forward by the minimal rotation between the two
    tangents, so the normal never turns further than the tangent does. That
    property is what a fixed up-vector frame violates, by up to 90 degrees,
    wherever the path passes near the chosen axis.

    Args:
        points: Path stations as (x, y, z) tuples. At least two.
        twist: Total rotation of the profile about the path, in radians,
            accumulated evenly from the start to the end.

    Returns:
        List of (tangent, normal, binormal) unit-vector triples.
    """
    if len(points) < 2:
        raise ValueError("a path needs at least two points")

    tangents = _tangents(points)

    # Seed: any unit vector perpendicular to the first tangent. Cross with
    # whichever world axis is least aligned with it, so the cross is never
    # near-degenerate. This choice is arbitrary and only fixes where the
    # profile's first vertex lands; it is made once, not per station, which
    # is precisely why it cannot cause a flip.
    t0 = tangents[0]
    axis = min(
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        key=lambda a: abs(_dot(a, t0)),
    )
    normal = _normalize(_cross(t0, axis))

    normals = [normal]
    for i in range(1, len(points)):
        prev_t, cur_t = tangents[i - 1], tangents[i]
        axis_vec = _cross(prev_t, cur_t)
        sin_a = _length(axis_vec)
        if sin_a < _MIN_SEGMENT:
            carried = normals[-1]          # tangent unchanged: carry as-is
        else:
            angle = math.atan2(sin_a, _dot(prev_t, cur_t))
            carried = _rotate_about(normals[-1], _scale(axis_vec, 1.0 / sin_a), angle)
        # Re-orthogonalize against drift from repeated rotations.
        carried = _sub(carried, _scale(cur_t, _dot(carried, cur_t)))
        normals.append(_normalize(carried))

    frames = []
    last = len(points) - 1
    for i, (t, n) in enumerate(zip(tangents, normals)):
        if twist:
            n = _normalize(_rotate_about(n, t, twist * (i / last if last else 0.0)))
        frames.append((t, n, _normalize(_cross(t, n))))
    return frames


def curvature_radii(points):
    """Radius of curvature at each station, from the circle through its neighbours.

    Endpoints have no neighbour on one side and report infinity; they are
    never the tightest point on a path that bends anywhere.
    """
    if len(points) < 2:
        raise ValueError("a path needs at least two points")
    inf = float("inf")
    out = [inf]
    for i in range(1, len(points) - 1):
        a, b, c = points[i - 1], points[i], points[i + 1]
        ab, bc, ca = _sub(b, a), _sub(c, b), _sub(a, c)
        area = _length(_cross(ab, _sub(c, a))) * 0.5
        if area < 1e-12:
            out.append(inf)               # collinear: straight
        else:
            out.append(_length(ab) * _length(bc) * _length(ca) / (4.0 * area))
    out.append(inf)
    return out


def analyze_path(points, radius):
    """Report whether a profile of the given radius fits along the path.

    Where the radius of curvature falls below the profile radius, consecutive
    rings intersect each other on the inside of the bend and the result is not
    a solid, though it is still watertight and manifold.

    Args:
        points: Path stations as (x, y, z) tuples.
        radius: Outer radius of the profile being swept.

    Returns:
        Dict with min_clearance_ratio (curvature radius over profile radius at
        the tightest station), tightest_index, tightest_point,
        self_intersects, and a count of offending stations.
    """
    if radius <= 0:
        raise ValueError("radius must be positive")
    radii = curvature_radii(points)
    ratios = [r / radius for r in radii]
    tightest = min(range(len(ratios)), key=lambda i: ratios[i])
    worst = ratios[tightest]
    return {
        "points": len(points),
        "min_clearance_ratio": None if worst == float("inf") else round(worst, 4),
        "tightest_index": tightest,
        "tightest_point": [round(c, 6) for c in points[tightest]],
        "self_intersects": worst < 1.0,
        "stations_below_1": sum(1 for r in ratios if r < 1.0),
        "stations_below_1_5": sum(1 for r in ratios if r < 1.5),
    }


def resample_path(points, samples_per_segment=8):
    """Interpolate a path with a centripetal Catmull-Rom spline.

    Centripetal parameterization (alpha = 0.5) is used rather than the uniform
    form because the uniform form overshoots and forms cusps when control
    points are unevenly spaced, and a cusp in the centreline makes the sweep
    double back through itself. Centripetal is provably cusp-free and never
    leaves the control polygon's neighbourhood.

    Args:
        points: Control points as (x, y, z) tuples. At least two.
        samples_per_segment: Samples generated between consecutive control
            points. 0 returns the input unchanged.

    Returns:
        List of (x, y, z) tuples passing through every control point.
    """
    if len(points) < 2:
        raise ValueError("a path needs at least two points")
    if samples_per_segment <= 0:
        return list(points)

    pts = list(points)
    # Phantom ends so the first and last segments are interpolated, not clamped.
    padded = (
        [_sub(_scale(pts[0], 2.0), pts[1])]
        + pts
        + [_sub(_scale(pts[-1], 2.0), pts[-2])]
    )

    knots = [0.0]
    for i in range(len(padded) - 1):
        knots.append(knots[-1] + max(_length(_sub(padded[i + 1], padded[i])), 1e-6) ** 0.5)

    def point_at(j, t):
        t0, t1, t2, t3 = knots[j - 1], knots[j], knots[j + 1], knots[j + 2]
        p0, p1, p2, p3 = padded[j - 1], padded[j], padded[j + 1], padded[j + 2]
        a1 = _add(_scale(p0, (t1 - t) / (t1 - t0)), _scale(p1, (t - t0) / (t1 - t0)))
        a2 = _add(_scale(p1, (t2 - t) / (t2 - t1)), _scale(p2, (t - t1) / (t2 - t1)))
        a3 = _add(_scale(p2, (t3 - t) / (t3 - t2)), _scale(p3, (t - t2) / (t3 - t2)))
        b1 = _add(_scale(a1, (t2 - t) / (t2 - t0)), _scale(a2, (t - t0) / (t2 - t0)))
        b2 = _add(_scale(a2, (t3 - t) / (t3 - t1)), _scale(a3, (t - t1) / (t3 - t1)))
        return _add(_scale(b1, (t2 - t) / (t2 - t1)), _scale(b2, (t - t1) / (t2 - t1)))

    out = []
    for seg in range(1, len(padded) - 2):
        lo, hi = knots[seg], knots[seg + 1]
        for s in range(samples_per_segment):
            out.append(point_at(seg, lo + (hi - lo) * s / samples_per_segment))
    out.append(tuple(pts[-1]))
    return out


def make_profile(shape, radius, sides):
    """A closed 2D profile in the ring's local plane, wound counter-clockwise.

    Consistent winding matters: the end caps are built from these points
    directly, so a profile wound the other way would cap with inverted normals.
    """
    if radius <= 0:
        raise ValueError("radius must be positive")
    if shape == "CIRCLE":
        n = sides
    elif shape == "SQUARE":
        n = 4
    elif shape == "HEXAGON":
        n = 6
    elif shape == "TRIANGLE":
        n = 3
    else:
        raise ValueError(
            f"unknown profile '{shape}', expected one of {list(ALLOWED_PROFILES)}"
        )
    if n < 3:
        raise ValueError("a profile needs at least 3 sides")
    # Squares and other low-n profiles are drawn on their circumcircle, so
    # `radius` always means the same thing: distance to the furthest point.
    offset = math.pi / 4.0 if shape == "SQUARE" else 0.0
    return [
        (radius * math.cos(math.tau * i / n + offset),
         radius * math.sin(math.tau * i / n + offset))
        for i in range(n)
    ]


def _validate_path(raw):
    """Coerce and check a path from the wire. The socket is not trusted."""
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        raise ValueError("path_points needs at least two points")
    if len(raw) > MAX_PATH_POINTS:
        raise ValueError(f"path_points exceeds {MAX_PATH_POINTS} points")
    pts = []
    for i, p in enumerate(raw):
        if not isinstance(p, (list, tuple)) or len(p) != 3:
            raise ValueError(f"path point {i} must have exactly 3 components")
        try:
            xyz = tuple(float(c) for c in p)
        except (TypeError, ValueError):
            raise ValueError(f"path point {i} must be numeric") from None
        if not all(math.isfinite(c) for c in xyz):
            raise ValueError(f"path point {i} is not finite")
        if pts and _length(_sub(xyz, pts[-1])) < _MIN_SEGMENT:
            raise ValueError(f"path point {i} repeats the previous point")
        pts.append(xyz)
    return pts


def handle_sweep_profile_along_path(params):
    """Sweep a closed profile along a path and return a solid mesh object."""
    points = _validate_path(params.get("path_points"))
    shape = params.get("profile", "CIRCLE")
    radius = float(params.get("radius", 1.0))
    sides = int(params.get("sides", 16))
    resolution = int(params.get("resolution", 0))
    twist = float(params.get("twist", 0.0))
    caps = bool(params.get("caps", True))
    name = params.get("name") or "Sweep"

    if radius <= 0:
        raise ValueError("radius must be positive")
    if not 3 <= sides <= MAX_SIDES:
        raise ValueError(f"sides must be between 3 and {MAX_SIDES}")
    if not 0 <= resolution <= MAX_RESOLUTION:
        raise ValueError(f"resolution must be between 0 and {MAX_RESOLUTION}")

    if resolution:
        points = resample_path(points, resolution)
    profile = make_profile(shape, radius, sides)

    faces = (len(points) - 1) * len(profile)
    if faces > MAX_SWEEP_FACES:
        raise ValueError(
            f"sweep would create {faces} faces, over the {MAX_SWEEP_FACES} limit; "
            f"lower resolution or sides"
        )

    report = analyze_path(points, radius)
    frames = parallel_transport_frames(points, twist=twist)

    bm = bmesh.new()
    rings = []
    for centre, (_t, normal, binormal) in zip(points, frames):
        rings.append([
            bm.verts.new(_add(centre,
                              _add(_scale(normal, u), _scale(binormal, v))))
            for u, v in profile
        ])
    for i in range(len(rings) - 1):
        for j in range(len(profile)):
            k = (j + 1) % len(profile)
            bm.faces.new((rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]))
    if caps:
        bm.faces.new(tuple(rings[0]))
        bm.faces.new(tuple(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    result = {
        "name": obj.name,
        "stations": len(points),
        "profile": shape,
        "sides": len(profile),
        "vertices": len(mesh.vertices),
        "faces": len(mesh.polygons),
        "closed": caps,
    }
    result.update(report)
    if report["self_intersects"]:
        result["warning"] = (
            "The path bends tighter than the profile, so rings overlap on the "
            "inside of the bend. The mesh is watertight but is not a solid and "
            "will slice wrongly. Widen the bend, reduce radius, or call "
            "analyze_sweep_path to find the tightest point."
        )
    return result


def handle_analyze_sweep_path(params):
    """Check a path against a profile radius without building anything."""
    points = _validate_path(params.get("path_points"))
    radius = float(params.get("radius", 1.0))
    resolution = int(params.get("resolution", 0))
    if radius <= 0:
        raise ValueError("radius must be positive")
    if not 0 <= resolution <= MAX_RESOLUTION:
        raise ValueError(f"resolution must be between 0 and {MAX_RESOLUTION}")
    if resolution:
        points = resample_path(points, resolution)
    return analyze_path(points, radius)


def register():
    dispatcher.register_handler(
        "sweep_profile_along_path", handle_sweep_profile_along_path)
    dispatcher.register_handler("analyze_sweep_path", handle_analyze_sweep_path)
