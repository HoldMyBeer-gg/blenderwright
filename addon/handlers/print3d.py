"""Handlers wrapping Blender's 3D Print Toolbox.

The toolbox is a bundled extension, not part of bpy, so it may be absent or
switched off. Every entry point here checks for it first and says how to turn
it on, rather than failing with an AttributeError from inside an operator.

It is wrapped rather than reimplemented because it catches three defects a
mesh can carry while still reporting as manifold, watertight and
non-degenerate, which is to say while passing analyze_mesh_quality:

  Bad Contiguous Edges - a shell whose normals agree with each other but
      collectively face inward. recalc_face_normals reports nothing to fix,
      and the slicer rejects the result as reversed faces.
  Intersect Faces      - the surface passing through itself.
  Thin Faces           - walls thinner than the nozzle, which slice to nothing.

Each check operator replaces the stored report with only its own rows, and
Shells is produced only by check_all, so running a subset means merging the
report after every call.
"""

import bpy

from .. import dispatcher

MAX_SAMPLE_INDICES = 50

# Report row label -> the key pair used in the response.
_ROW_KEYS = {
    "Non-manifold Edges": ("non_manifold_edge_count", "non_manifold_edge_indices"),
    "Bad Contiguous Edges": ("bad_contiguous_edge_count", "bad_contiguous_edge_indices"),
    "Intersect Faces": ("intersect_face_count", "intersect_face_indices"),
    "Shells": ("shell_count", None),
    "Zero Faces": ("zero_face_count", "zero_face_indices"),
    "Zero Edges": ("zero_edge_count", "zero_edge_indices"),
    "Non-flat Faces": ("non_flat_face_count", "non_flat_face_indices"),
    "Thin Faces": ("thin_face_count", "thin_face_indices"),
    "Sharp Edges": ("sharp_edge_count", "sharp_edge_indices"),
    "Overhang Faces": ("overhang_face_count", "overhang_face_indices"),
}

_CHECK_OPERATORS = {
    "SOLID": "print3d_check_solid",
    "INTERSECT": "print3d_check_intersect",
    "DEGENERATE": "print3d_check_degenerate",
    "THICKNESS": "print3d_check_thick",
    "SHARP": "print3d_check_sharp",
    "OVERHANG": "print3d_check_overhang",
    "NONPLANAR": "print3d_check_nonplanar",
}

# Threshold parameter -> the toolbox property it sets. Only the ones the
# caller passes are written, so an unset threshold leaves the user's own
# toolbox settings untouched.
_THRESHOLDS = {
    "overhang_angle": "angle_overhang",
    "sharp_angle": "angle_sharp",
    "nonplanar_angle": "angle_nonplanar",
    "min_thickness": "thickness_min",
    "zero_threshold": "threshold_zero",
}

# These stop a print outright. Overhangs, sharp edges and non-flat faces are
# advisory: they describe geometry a slicer will still process.
_BLOCKING = (
    "Non-manifold Edges",
    "Bad Contiguous Edges",
    "Intersect Faces",
    "Zero Faces",
    "Zero Edges",
)

_NOT_ENABLED = (
    "The 3D Print Toolbox extension is not enabled in this Blender. "
    "Enable it in Edit > Preferences > Add-ons by searching for "
    "'3D Print Toolbox', then retry. It ships with Blender, so there is "
    "nothing to download."
)


def toolbox_available():
    """True when the toolbox's scene properties are registered."""
    return hasattr(bpy.context.scene, "print3d_toolbox")


def _props():
    props = getattr(bpy.context.scene, "print3d_toolbox", None)
    if props is None:
        raise RuntimeError(_NOT_ENABLED)
    return props


def _get_mesh_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object '{name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{name}' is a {obj.type}, not a mesh")
    return obj


def _collect(props, into):
    """Fold the current report into the accumulating result."""
    for row in props.get_report():
        label, count = row[0], row[1]
        keys = _ROW_KEYS.get(label)
        if keys is None:
            continue
        count_key, index_key = keys
        into[count_key] = int(count)
        if index_key is not None and len(row) > 2 and row[2] is not None:
            into[index_key] = [int(i) for i in list(row[2])[:MAX_SAMPLE_INDICES]]
        into.setdefault("_labels", set()).add(label)


def handle_check_3d_printability(params):
    """Run the 3D Print Toolbox checks on one mesh and return its report."""
    props = _props()
    obj = _get_mesh_object(params["object_name"])

    checks = params.get("checks") or []
    if not isinstance(checks, (list, tuple)):
        raise ValueError("checks must be a list")
    checks = [str(c).upper() for c in checks]
    unknown = [c for c in checks if c not in _CHECK_OPERATORS]
    if unknown:
        raise ValueError(
            f"unknown check(s) {unknown}, expected any of "
            f"{sorted(_CHECK_OPERATORS)}"
        )

    for key, prop_name in _THRESHOLDS.items():
        if params.get(key) is not None:
            setattr(props, prop_name, float(params[key]))

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    result = {}
    if checks:
        # Deduplicate while keeping the caller's order.
        ordered = list(dict.fromkeys(checks))
        for check in ordered:
            getattr(bpy.ops.mesh, _CHECK_OPERATORS[check])()
            _collect(props, result)
        result["checks_run"] = ordered
    else:
        bpy.ops.mesh.print3d_check_all()
        _collect(props, result)
        result["checks_run"] = sorted(_CHECK_OPERATORS) + ["SHELLS"]

    seen = result.pop("_labels", set())
    blocking = []
    for label in _BLOCKING:
        if label not in seen:
            continue
        count = result.get(_ROW_KEYS[label][0], 0)
        if count:
            blocking.append(f"{count} {label.lower()}")
    # A solid is one shell. Zero or several is worth saying; one is not.
    shells = result.get("shell_count")
    if shells is not None and shells != 1:
        blocking.append(f"{shells} separate shells")

    result["object"] = obj.name
    result["print_blocking"] = blocking
    result["issues_found"] = bool(blocking) or any(
        result.get(_ROW_KEYS[label][0], 0)
        for label in seen
        if label != "Shells"
    )
    return result


def register():
    dispatcher.register_handler("check_3d_printability", handle_check_3d_printability)
