"""MCP tools for Blender's 3D Print Toolbox."""

import math
from typing import Any

from blend_ai.server import mcp, get_connection
from blend_ai.validators import (
    ValidationError,
    validate_numeric_range,
    validate_object_name,
)

ALLOWED_PRINT_CHECKS = {
    "SOLID",
    "INTERSECT",
    "DEGENERATE",
    "THICKNESS",
    "SHARP",
    "OVERHANG",
    "NONPLANAR",
}


@mcp.tool()
def check_3d_printability(
    object_name: str,
    checks: list[str] | None = None,
    overhang_angle: float | None = None,
    min_thickness: float | None = None,
    sharp_angle: float | None = None,
    nonplanar_angle: float | None = None,
    zero_threshold: float | None = None,
) -> dict[str, Any]:
    """Check whether a mesh will 3D print, using Blender's 3D Print Toolbox.

    Catches three defects a mesh can carry while still passing
    analyze_mesh_quality, because each one leaves the mesh manifold,
    watertight and free of degenerate faces:

    - Bad contiguous edges: a shell whose normals agree with each other but
      collectively face inward. Recalculating normals reports nothing to fix,
      and the slicer rejects the file as having reversed faces.
    - Intersect faces: the surface passing through itself.
    - Thin faces: walls thinner than the nozzle, which slice away to nothing.

    It also reports shell count, zero-area faces and edges, non-flat faces,
    sharp edges and overhanging faces. Index lists are capped at 50 samples
    and can be fed straight to select_by_index to see the problem in Blender.

    Requires the 3D Print Toolbox extension, which ships with Blender but is
    off by default. If it is disabled this returns an error saying how to
    enable it; suggest_extensions also reports whether it is on.

    Args:
        object_name: Name of the mesh object to check.
        checks: Which checks to run - any of SOLID (non-manifold and bad
            contiguous edges), INTERSECT, DEGENERATE (zero faces and edges),
            THICKNESS, SHARP, OVERHANG, NONPLANAR. Omit or pass an empty list
            to run everything, which also reports shell count. Counts are only
            returned for checks that actually ran.
        overhang_angle: Overhang threshold in RADIANS. Faces steeper than this
            need support. 0.785 (45 degrees) is the usual FDM limit. Leave
            unset to keep the toolbox's current setting.
        min_thickness: Minimum wall thickness in Blender units. Set it to your
            nozzle width. Leave unset to keep the current setting.
        sharp_angle: Sharp-edge threshold in RADIANS.
        nonplanar_angle: Non-flat face threshold in RADIANS.
        zero_threshold: Area below which a face counts as zero-area.

    Returns:
        Dict with a count (and sample indices) per check that ran, plus
        checks_run, issues_found, and print_blocking: the defects that stop a
        print, as opposed to overhangs and sharp edges which are advisory.
    """
    object_name = validate_object_name(object_name)

    params: dict[str, Any] = {"object_name": object_name}

    if checks is None:
        params["checks"] = []
    else:
        if not isinstance(checks, (list, tuple)):
            raise ValidationError(
                f"checks must be a list of check names, got {type(checks).__name__}")
        cleaned = []
        for check in checks:
            if not isinstance(check, str):
                raise ValidationError("each check must be a string")
            check = check.upper()
            if check not in ALLOWED_PRINT_CHECKS:
                raise ValidationError(
                    f"check must be one of {sorted(ALLOWED_PRINT_CHECKS)}, "
                    f"got '{check}'")
            if check not in cleaned:
                cleaned.append(check)
        params["checks"] = cleaned

    # Angles are radians throughout this API. A caller reaching for 45 means
    # degrees, and silently accepting it would make every face an overhang,
    # so validate_numeric_range says so in the error.
    for name, value in (
        ("overhang_angle", overhang_angle),
        ("sharp_angle", sharp_angle),
        ("nonplanar_angle", nonplanar_angle),
    ):
        if value is not None:
            params[name] = validate_numeric_range(
                value, min_val=0.0, max_val=math.pi, name=name)

    if min_thickness is not None:
        params["min_thickness"] = validate_numeric_range(
            min_thickness, min_val=0.0, max_val=1000.0, name="min_thickness")
    if zero_threshold is not None:
        params["zero_threshold"] = validate_numeric_range(
            zero_threshold, min_val=0.0, max_val=1000.0, name="zero_threshold")

    conn = get_connection()
    response = conn.send_command("check_3d_printability", params)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
