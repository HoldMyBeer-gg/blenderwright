"""Blender handlers for procedural material generation.

Each pattern is a recipe that builds a texture node graph in a single
main-thread call. Doing it here rather than by composing primitives from the
MCP side keeps the build atomic: a failure raises before anything is wired
up, instead of leaving a half-connected graph in the user's scene.

Every recipe returns the socket that carries its greyscale result, which the
caller feeds into a colour ramp. That uniformity is what lets one function
handle the ramp, the BSDF wiring, and the palette for all thirteen patterns.
"""

import bpy
from .. import dispatcher

# Node layout columns, so generated graphs are readable when a user opens the
# shader editor rather than piled on top of each other at the origin.
_COL_COORD = -1000
_COL_MAPPING = -800
_COL_TEXTURE = -600
_COL_ADJUST = -400
_COL_RAMP = -200
_COL_BSDF = 100

# Default palettes, in ramp order from position 0.0 to 1.0. Chosen to look
# like the thing they are named after rather than to be mathematically even.
DEFAULT_PALETTES = {
    "gradient": [
        (0.0, 0.0, 0.0, 1.0),
        (1.0, 1.0, 1.0, 1.0),
    ],
    "noise": [
        (0.05, 0.05, 0.05, 1.0),
        (0.8, 0.8, 0.8, 1.0),
    ],
    "cloud": [
        (0.15, 0.25, 0.45, 1.0),
        (1.0, 1.0, 1.0, 1.0),
    ],
    "voronoi": [
        (0.08, 0.08, 0.09, 1.0),
        (0.55, 0.54, 0.5, 1.0),
    ],
    "veins": [
        (0.02, 0.02, 0.02, 1.0),
        (0.35, 0.5, 0.2, 1.0),
    ],
    "scales": [
        (0.05, 0.18, 0.06, 1.0),
        (0.22, 0.55, 0.24, 1.0),
    ],
    "stripes": [
        (0.05, 0.05, 0.06, 1.0),
        (0.85, 0.82, 0.75, 1.0),
    ],
    "wood": [
        (0.18, 0.09, 0.04, 1.0),
        (0.45, 0.26, 0.12, 1.0),
        (0.62, 0.42, 0.22, 1.0),
    ],
    "marble": [
        (0.78, 0.76, 0.72, 1.0),
        (0.35, 0.34, 0.33, 1.0),
        (0.06, 0.06, 0.07, 1.0),
    ],
    "weave": [
        (0.10, 0.09, 0.08, 1.0),
        (0.55, 0.45, 0.32, 1.0),
    ],
    "plasma": [
        (0.15, 0.0, 0.35, 1.0),
        (0.9, 0.1, 0.6, 1.0),
        (0.1, 0.7, 1.0, 1.0),
        (1.0, 1.0, 1.0, 1.0),
    ],
    "fire": [
        (0.02, 0.0, 0.0, 1.0),
        (0.6, 0.05, 0.0, 1.0),
        (1.0, 0.35, 0.0, 1.0),
        (1.0, 0.85, 0.25, 1.0),
        (1.0, 1.0, 0.9, 1.0),
    ],
    "sparks": [
        (0.0, 0.0, 0.0, 1.0),
        (0.05, 0.02, 0.0, 1.0),
        (1.0, 0.55, 0.1, 1.0),
        (1.0, 0.95, 0.7, 1.0),
    ],
}


def _out(node, *names):
    """Get the first output socket matching any of the given names.

    Blender renames sockets between versions — 'Fac' became 'Factor' on the
    Noise, Gradient, Wave and ColorRamp nodes in 5.x. Indexing by name alone
    breaks on one version or the other, so try each known spelling and fall
    back to the first output rather than failing the whole build.
    """
    for name in names:
        socket = node.outputs.get(name)
        if socket is not None:
            return socket
    return node.outputs[0]


def _in(node, *names):
    """Get the first input socket matching any of the given names."""
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            return socket
    return node.inputs[0]


def _set(node, socket_name, value):
    """Set a socket default if the socket exists on this Blender version.

    Socket names drift between Blender releases. A recipe that hard-fails on a
    renamed socket would break the whole material, so a missing optional
    socket is skipped rather than fatal.
    """
    socket = node.inputs.get(socket_name)
    if socket is None:
        return False
    socket.default_value = value
    return True


def _new(tree, bl_idname, label, x, y=0):
    node = tree.nodes.new(type=bl_idname)
    node.label = label
    node.location = (x, y)
    return node


# ---------------------------------------------------------------------------
# Pattern recipes
#
# Each takes (tree, vector_socket, params) and returns the output socket
# carrying its result, ready for the colour ramp.
# ---------------------------------------------------------------------------


def _noise_node(tree, vector, params, y=0, detail_boost=0.0):
    noise = _new(tree, "ShaderNodeTexNoise", "Noise", _COL_TEXTURE, y)
    tree.links.new(vector, noise.inputs["Vector"])
    _set(noise, "Scale", params["scale"])
    _set(noise, "Detail", min(params["detail"] + detail_boost, 15.0))
    _set(noise, "Distortion", params["distortion"])
    return noise


def _build_gradient(tree, vector, params):
    grad = _new(tree, "ShaderNodeTexGradient", "Gradient", _COL_TEXTURE)
    grad.gradient_type = "LINEAR"
    tree.links.new(vector, grad.inputs["Vector"])
    return _out(grad, "Fac", "Factor")


def _build_noise(tree, vector, params):
    return _out(_noise_node(tree, vector, params), "Fac", "Factor")


def _build_cloud(tree, vector, params):
    # Softer and puffier than plain noise: more octaves, no distortion.
    noise = _noise_node(tree, vector, params, detail_boost=4.0)
    _set(noise, "Roughness", 0.6)
    return _out(noise, "Fac", "Factor")


def _build_voronoi(tree, vector, params):
    voronoi = _new(tree, "ShaderNodeTexVoronoi", "Voronoi", _COL_TEXTURE)
    voronoi.feature = "F1"
    tree.links.new(vector, voronoi.inputs["Vector"])
    _set(voronoi, "Scale", params["scale"])
    return voronoi.outputs["Distance"]


def _build_veins(tree, vector, params):
    # Distance to edge is what turns cells into the cracks between them.
    voronoi = _new(tree, "ShaderNodeTexVoronoi", "Veins", _COL_TEXTURE)
    voronoi.feature = "DISTANCE_TO_EDGE"
    tree.links.new(vector, voronoi.inputs["Vector"])
    _set(voronoi, "Scale", params["scale"])
    return voronoi.outputs["Distance"]


def _build_scales(tree, vector, params):
    voronoi = _new(tree, "ShaderNodeTexVoronoi", "Scales", _COL_TEXTURE)
    voronoi.feature = "F1"
    tree.links.new(vector, voronoi.inputs["Vector"])
    _set(voronoi, "Scale", params["scale"])
    # Randomness low so cells stay a regular plated grid rather than blotches.
    _set(voronoi, "Randomness", 0.25)
    return voronoi.outputs["Distance"]


def _build_stripes(tree, vector, params):
    wave = _new(tree, "ShaderNodeTexWave", "Stripes", _COL_TEXTURE)
    wave.wave_type = "BANDS"
    wave.wave_profile = "SIN"
    tree.links.new(vector, wave.inputs["Vector"])
    _set(wave, "Scale", params["scale"])
    _set(wave, "Distortion", params["distortion"])
    return _out(wave, "Fac", "Factor")


def _build_wood(tree, vector, params):
    wave = _new(tree, "ShaderNodeTexWave", "Wood", _COL_TEXTURE)
    wave.wave_type = "RINGS"
    wave.wave_profile = "SIN"
    tree.links.new(vector, wave.inputs["Vector"])
    _set(wave, "Scale", params["scale"])
    # Rings alone look machined; distortion is what reads as grain.
    _set(wave, "Distortion", max(params["distortion"], 2.0))
    _set(wave, "Detail", params["detail"])
    return _out(wave, "Fac", "Factor")


def _build_marble(tree, vector, params):
    wave = _new(tree, "ShaderNodeTexWave", "Marble", _COL_TEXTURE)
    wave.wave_type = "BANDS"
    wave.wave_profile = "SIN"
    tree.links.new(vector, wave.inputs["Vector"])
    _set(wave, "Scale", params["scale"])
    _set(wave, "Distortion", max(params["distortion"], 6.0))
    _set(wave, "Detail", max(params["detail"], 3.0))
    return _out(wave, "Fac", "Factor")


def _build_weave(tree, vector, params):
    # Two band sets at right angles, multiplied where threads cross.
    warp = _new(tree, "ShaderNodeTexWave", "Warp", _COL_TEXTURE, 200)
    warp.wave_type = "BANDS"
    warp.bands_direction = "X"
    tree.links.new(vector, warp.inputs["Vector"])
    _set(warp, "Scale", params["scale"])

    weft = _new(tree, "ShaderNodeTexWave", "Weft", _COL_TEXTURE, -200)
    weft.wave_type = "BANDS"
    weft.bands_direction = "Y"
    tree.links.new(vector, weft.inputs["Vector"])
    _set(weft, "Scale", params["scale"])

    combine = _new(tree, "ShaderNodeMath", "Weave Mix", _COL_ADJUST)
    combine.operation = "MULTIPLY"
    tree.links.new(_out(warp, "Fac", "Factor"), combine.inputs[0])
    tree.links.new(_out(weft, "Fac", "Factor"), combine.inputs[1])
    return combine.outputs["Value"]


def _build_plasma(tree, vector, params):
    # Two noise fields at different scales, summed for a churning look.
    base = _noise_node(tree, vector, params, y=200)
    fine = _noise_node(tree, vector, dict(params, scale=params["scale"] * 2.7), y=-200)

    combine = _new(tree, "ShaderNodeMath", "Plasma Mix", _COL_ADJUST)
    combine.operation = "ADD"
    combine.use_clamp = True
    tree.links.new(_out(base, "Fac", "Factor"), combine.inputs[0])
    tree.links.new(_out(fine, "Fac", "Factor"), combine.inputs[1])
    return combine.outputs["Value"]


def _build_fire(tree, vector, params):
    # Noise masked by a vertical gradient, so flame fades out with height.
    noise = _noise_node(tree, vector, params, y=200, detail_boost=2.0)

    gradient = _new(tree, "ShaderNodeTexGradient", "Height Mask", _COL_TEXTURE, -200)
    gradient.gradient_type = "LINEAR"
    tree.links.new(vector, gradient.inputs["Vector"])

    combine = _new(tree, "ShaderNodeMath", "Flame Mask", _COL_ADJUST)
    combine.operation = "MULTIPLY"
    tree.links.new(_out(noise, "Fac", "Factor"), combine.inputs[0])
    tree.links.new(_out(gradient, "Fac", "Factor"), combine.inputs[1])
    return combine.outputs["Value"]


def _build_sparks(tree, vector, params):
    # Dense voronoi pushed through a steep power curve, leaving only the
    # brightest cell centres as isolated points.
    voronoi = _new(tree, "ShaderNodeTexVoronoi", "Sparks", _COL_TEXTURE)
    voronoi.feature = "F1"
    tree.links.new(vector, voronoi.inputs["Vector"])
    _set(voronoi, "Scale", params["scale"] * 4.0)

    # Math nodes have two inputs both named 'Value', so these must be
    # addressed by index. Name lookup returns inputs[0] every time, which
    # would put the constant on the linked socket where it is ignored.
    invert = _new(tree, "ShaderNodeMath", "Invert", _COL_ADJUST, 150)
    invert.operation = "SUBTRACT"
    invert.inputs[0].default_value = 1.0
    tree.links.new(voronoi.outputs["Distance"], invert.inputs[1])

    sharpen = _new(tree, "ShaderNodeMath", "Sharpen", _COL_ADJUST, -150)
    sharpen.operation = "POWER"
    tree.links.new(invert.outputs["Value"], sharpen.inputs[0])
    sharpen.inputs[1].default_value = 8.0
    return sharpen.outputs["Value"]


# Patterns that span the space once rather than tiling. Scaling their
# coordinates just pushes both ends past the ramp and flattens the result.
SCALE_INDEPENDENT_PATTERNS = {"gradient"}

# Which patterns actually consume which parameters. Cellular and gradient
# patterns have no Detail or Distortion socket to write to, so passing those
# values is a silent no-op. Recorded here so the handler can report what it
# ignored rather than leaving the caller to wonder why nothing changed.
PATTERNS_USING_DETAIL = {"noise", "cloud", "wood", "marble", "plasma", "fire"}
PATTERNS_USING_DISTORTION = {
    "noise", "cloud", "stripes", "wood", "marble", "plasma", "fire",
}

PATTERN_BUILDERS = {
    "gradient": _build_gradient,
    "noise": _build_noise,
    "cloud": _build_cloud,
    "voronoi": _build_voronoi,
    "veins": _build_veins,
    "scales": _build_scales,
    "stripes": _build_stripes,
    "wood": _build_wood,
    "marble": _build_marble,
    "weave": _build_weave,
    "plasma": _build_plasma,
    "fire": _build_fire,
    "sparks": _build_sparks,
}


def _apply_palette(ramp_node, colors, banded):
    """Replace a ramp's stops with the given colours, evenly spread.

    Banded ramps space stops differently. CONSTANT interpolation holds each
    stop's colour until the *next* stop, so a final stop sitting at 1.0 would
    only ever show at exactly 1.0 and the last band would be invisible.
    Banded spacing therefore divides by the number of colours rather than by
    the gaps between them, giving every colour a band of real width.
    """
    ramp = ramp_node.color_ramp
    ramp.interpolation = "CONSTANT" if banded else "LINEAR"

    # A new ramp starts with two stops. Blender refuses to remove the last
    # one, so reuse the first and trim the rest before adding.
    while len(ramp.elements) > 1:
        ramp.elements.remove(ramp.elements[len(ramp.elements) - 1])

    count = len(colors)
    first = ramp.elements[0]
    first.position = 0.0
    first.color = tuple(colors[0])

    for i, color in enumerate(colors[1:], start=1):
        if banded:
            position = i / count
        else:
            position = i / (count - 1) if count > 1 else 0.0
        element = ramp.elements.new(position)
        element.color = tuple(color)


def _get_principled(tree):
    for node in tree.nodes:
        if node.bl_idname == "ShaderNodeBsdfPrincipled":
            return node
    return None


def handle_create_procedural_material(params: dict) -> dict:
    """Build a complete procedural texture graph as a new material."""
    mat = None
    try:
        pattern = params["pattern"]
        builder = PATTERN_BUILDERS.get(pattern)
        if builder is None:
            raise ValueError(
                f"Unknown pattern '{pattern}'. "
                f"Available: {sorted(PATTERN_BUILDERS)}"
            )

        mat = bpy.data.materials.new(name=params["name"])
        mat.use_nodes = True
        tree = mat.node_tree

        coord = _new(tree, "ShaderNodeTexCoord", "Coordinates", _COL_COORD)
        mapping = _new(tree, "ShaderNodeMapping", "Mapping", _COL_MAPPING)
        # Generated coordinates keep the texture working without a UV unwrap.
        tree.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])

        scale = params["scale"]
        # A gradient runs once across 0-1. Tiling it by the scale factor just
        # saturates both ends and the ramp reads as flat, so it maps 1:1 and
        # ignores scale entirely.
        if pattern in SCALE_INDEPENDENT_PATTERNS:
            scale = 1.0
        _set(mapping, "Scale", (scale, scale, scale))

        # The recipe consumes the mapped vector and hands back a greyscale
        # socket; scale is applied once here so recipes need not repeat it.
        pattern_params = dict(params)
        pattern_params["scale"] = 1.0
        result_socket = builder(tree, mapping.outputs["Vector"], pattern_params)

        ramp_node = _new(tree, "ShaderNodeValToRGB", "Palette", _COL_RAMP)
        tree.links.new(result_socket, _in(ramp_node, "Fac", "Factor"))

        colors = params.get("colors") or DEFAULT_PALETTES[pattern]
        _apply_palette(ramp_node, colors, params.get("banded", False))

        bsdf = _get_principled(tree)
        if bsdf is not None:
            bsdf.location = (_COL_BSDF, 0)
            _set(bsdf, "Roughness", params["roughness"])
            _set(bsdf, "Metallic", params["metallic"])
            if params.get("connect_to_bsdf", True):
                tree.links.new(
                    ramp_node.outputs["Color"], bsdf.inputs["Base Color"]
                )

        nodes = {
            "coordinates": coord.name,
            "mapping": mapping.name,
            "color_ramp": ramp_node.name,
        }
        if bsdf is not None:
            nodes["bsdf"] = bsdf.name

        # Tell the caller which parameters this pattern could not use, so a
        # value that had no effect is visible rather than silently dropped.
        ignored = []
        if pattern in SCALE_INDEPENDENT_PATTERNS:
            ignored.append("scale")
        if pattern not in PATTERNS_USING_DETAIL:
            ignored.append("detail")
        if pattern not in PATTERNS_USING_DISTORTION:
            ignored.append("distortion")

        return {
            "material": mat.name,
            "pattern": pattern,
            "nodes": nodes,
            "ignored_params": ignored,
            "connected": bool(params.get("connect_to_bsdf", True)),
            "stops": len(ramp_node.color_ramp.elements),
        }
    except Exception as e:
        # Deliver the atomicity this module's docstring promises. Without
        # this, a failure partway through leaves a half-wired material in
        # the user's scene that they have to find and delete by hand.
        if mat is not None:
            try:
                bpy.data.materials.remove(mat)
            except Exception:
                pass
        raise RuntimeError(f"Failed to create procedural material: {e}") from e


def register():
    """Register procedural material handlers with the dispatcher."""
    dispatcher.register_handler(
        "create_procedural_material", handle_create_procedural_material
    )
