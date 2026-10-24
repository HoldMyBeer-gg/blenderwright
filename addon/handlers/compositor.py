"""Blender handlers for the compositor (Blender 5.x node-group compositor).

The scene's compositor is a CompositorNodeTree assigned to
scene.compositing_node_group. Render Layers feeds a Group Output; effects
are chained between them. Node options are input sockets, so settings only
ever touch a node's own inputs.
"""

import os

import bpy
from .. import dispatcher

# Effect name -> built-in node type, or ("asset", Essentials node group name)
EFFECTS = {
    "glare": "CompositorNodeGlare",
    "lens_distortion": "CompositorNodeLensdist",
    "color_balance": "CompositorNodeColorBalance",
    "denoise": "CompositorNodeDenoise",
    "blur": "CompositorNodeBlur",
    "exposure": "CompositorNodeExposure",
    "brightness_contrast": "CompositorNodeBrightContrast",
    "hue_saturation": "CompositorNodeHueSat",
    "kuwahara": "CompositorNodeKuwahara",
    "pixelate": "CompositorNodePixelate",
    "posterize": "CompositorNodePosterize",
    "anti_aliasing": "CompositorNodeAntiAliasing",
    "vignette": ("asset", "Vignette"),
    "film_grain": ("asset", "Film Grain"),
    "chromatic_aberration": ("asset", "Chromatic Aberration"),
    "sepia": ("asset", "Sepia"),
    "split_toning": ("asset", "Split Toning"),
    "sensor_noise": ("asset", "Sensor Noise"),
    "unsharp_mask": ("asset", "Unsharp Mask"),
    "tune_image": ("asset", "Tune Image"),
}

CORE_NODE_TYPES = {"CompositorNodeRLayers", "NodeGroupOutput", "CompositorNodeViewer"}
ESSENTIALS_FILE = os.path.join("nodes", "compositing_nodes_essentials.blend")


def _essentials_group(name):
    """The named compositor node group from Blender's bundled Essentials library."""
    existing = bpy.data.node_groups.get(name)
    if existing is not None and existing.bl_idname == "CompositorNodeTree":
        return existing
    path = os.path.join(bpy.utils.system_resource("DATAFILES", path="assets"), ESSENTIALS_FILE)
    with bpy.data.libraries.load(path, link=False) as (_src, dst):
        dst.node_groups = [name]
    return dst.node_groups[0]


def _find(tree, bl_idname):
    return next((n for n in tree.nodes if n.bl_idname == bl_idname), None)


def _build_default(tree):
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    layers = tree.nodes.new("CompositorNodeRLayers")
    layers.location = (0, 0)
    output = tree.nodes.new("NodeGroupOutput")
    output.location = (400, 0)
    viewer = tree.nodes.new("CompositorNodeViewer")
    viewer.location = (400, -200)
    tree.links.new(layers.outputs[0], output.inputs[0])
    tree.links.new(layers.outputs[0], viewer.inputs[0])


def _ensure_tree(reset=False):
    scene = bpy.context.scene
    tree = scene.compositing_node_group
    if tree is None or reset:
        tree = bpy.data.node_groups.new("Compositing", "CompositorNodeTree")
        _build_default(tree)
        scene.compositing_node_group = tree
    scene.render.use_compositing = True
    return tree


def _image_input(node):
    return next((s for s in node.inputs if s.type == "RGBA"), None)


def _chain_nodes(tree):
    """Nodes from the source to the Group Output, following the image links."""
    output = _find(tree, "NodeGroupOutput")
    if output is None:
        return []
    nodes, node = [output], output
    while True:
        socket = _image_input(node)
        if socket is None or not socket.links:
            break
        node = socket.links[0].from_node
        nodes.append(node)
    return list(reversed(nodes))


def _is_sequence(value):
    return hasattr(value, "__len__") and not isinstance(value, str)


def _plain(value):
    return list(value) if _is_sequence(value) else value


def _set_inputs(node, settings):
    """Set unlinked input sockets by name; pick same-named sockets by value shape."""
    for name, value in settings.items():
        candidates = [s for s in node.inputs if s.name == name and not s.is_linked]
        if not candidates:
            valid = sorted({s.name for s in node.inputs if not s.is_linked})
            raise ValueError(f"'{node.name}' has no input '{name}'. Inputs: {', '.join(valid)}")
        want_sequence = isinstance(value, list)
        socket = next((s for s in candidates
                       if _is_sequence(s.default_value) == want_sequence), candidates[0])
        try:
            socket.default_value = value
        except (TypeError, ValueError) as e:
            raise ValueError(f"Cannot set '{name}' on '{node.name}' to {value!r}: {e}") from None


def _settings(node):
    """Current values of the node's unlinked inputs, for reporting."""
    out = {}
    for s in node.inputs:
        if s.is_linked or not getattr(s, "enabled", True) or not hasattr(s, "default_value"):
            continue
        key = s.name if s.name not in out else f"{s.name} ({s.type.lower()})"
        out[key] = _plain(s.default_value)
    return out


def _describe(tree):
    return {
        "tree": tree.name,
        "chain": [{"node_name": n.name, "effect": n.label or n.bl_idname,
                   **({"settings": _settings(n)} if n.bl_idname not in CORE_NODE_TYPES else {})}
                  for n in _chain_nodes(tree)],
    }


def _get_effect_node(tree, name):
    node = tree.nodes.get(name)
    if node is None:
        raise ValueError(f"No compositor node named '{name}'")
    if node.bl_idname in CORE_NODE_TYPES:
        raise ValueError(f"'{name}' is part of the compositor itself, not an effect")
    return node


def handle_setup_compositor(params):
    tree = _ensure_tree(reset=bool(params.get("reset", False)))
    return {"tree": tree.name, "chain": [n.name for n in _chain_nodes(tree)]}


def handle_add_compositor_effect(params):
    effect = params.get("effect")
    kind = EFFECTS.get(effect)
    if kind is None:
        raise ValueError(f"Unknown compositor effect: {effect!r}")
    tree = _ensure_tree()

    if isinstance(kind, tuple):
        group = _essentials_group(kind[1])
        node = tree.nodes.new("CompositorNodeGroup")
        node.node_tree = group
        node.name = group.name  # "Vignette", not "Group"; Blender adds .001 if taken
    else:
        node = tree.nodes.new(kind)
    node.label = effect
    try:
        _set_inputs(node, params.get("settings", {}))
    except Exception:
        tree.nodes.remove(node)
        raise

    output = _find(tree, "NodeGroupOutput")
    out_socket = output.inputs[0]
    if out_socket.links:
        source = out_socket.links[0].from_socket
    else:
        source = _find(tree, "CompositorNodeRLayers").outputs[0]
    # == not "is": Blender returns a new wrapper for the same socket on every access
    viewers = [n for n in tree.nodes if n.bl_idname == "CompositorNodeViewer"
               and n.inputs[0].links and n.inputs[0].links[0].from_socket == source]

    tree.links.new(source, _image_input(node))
    tree.links.new(node.outputs[0], out_socket)
    for viewer in viewers:
        tree.links.new(node.outputs[0], viewer.inputs[0])

    x, y = source.node.location[0], source.node.location[1]
    node.location = (x + 250, y)
    output.location = (x + 500, output.location[1])

    return {"node_name": node.name, "effect": effect, "settings": _settings(node)}


def handle_set_compositor_effect(params):
    tree = _ensure_tree()
    node = _get_effect_node(tree, params.get("node_name"))
    _set_inputs(node, params.get("settings", {}))
    return {"node_name": node.name, "settings": _settings(node)}


def handle_remove_compositor_effect(params):
    tree = _ensure_tree()
    node = _get_effect_node(tree, params.get("node_name"))
    image_in = _image_input(node)
    source = image_in.links[0].from_socket if image_in is not None and image_in.links else None
    targets = [link.to_socket for link in node.outputs[0].links] if node.outputs else []
    name = node.name
    tree.nodes.remove(node)
    if source is not None:
        for socket in targets:
            tree.links.new(source, socket)
    return {"removed": name, **_describe(tree)}


def handle_list_compositor(params):
    tree = bpy.context.scene.compositing_node_group
    if tree is None:
        return {"tree": None, "chain": []}
    return _describe(tree)


def register():
    dispatcher.register_handler("setup_compositor", handle_setup_compositor)
    dispatcher.register_handler("add_compositor_effect", handle_add_compositor_effect)
    dispatcher.register_handler("set_compositor_effect", handle_set_compositor_effect)
    dispatcher.register_handler("remove_compositor_effect", handle_remove_compositor_effect)
    dispatcher.register_handler("list_compositor", handle_list_compositor)
