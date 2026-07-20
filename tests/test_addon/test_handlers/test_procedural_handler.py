"""Tests for addon.handlers.procedural — procedural material graph building.

The handler assembles a whole texture node graph in one main-thread call, so
these tests assert on the resulting graph: which nodes exist, how they are
linked, and what the ramp ends up looking like.
"""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_procedural_handler():
    """Load addon.handlers.procedural without triggering addon/__init__.py."""
    mock_dispatcher = MagicMock()
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "procedural.py",
    )
    spec = importlib.util.spec_from_file_location(
        "addon.handlers.procedural", handler_path
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.procedural"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ph():
    return _load_procedural_handler()


# ---------------------------------------------------------------------------
# Fakes modelling the parts of bpy the handler touches
# ---------------------------------------------------------------------------


class FakeSocket:
    def __init__(self, name, default_value=0.0):
        self.name = name
        self.default_value = default_value


class FakeSocketCollection(list):
    def get(self, name, default=None):
        for item in self:
            if item.name == name:
                return item
        return default

    def __getitem__(self, key):
        if isinstance(key, str):
            found = self.get(key)
            if found is None:
                raise KeyError(key)
            return found
        return list.__getitem__(self, key)


class FakeElement:
    def __init__(self, position, color):
        self.position = position
        self.color = list(color)


class FakeElements(list):
    """Ramp elements, kept sorted by position as Blender keeps them.

    Real Blender reorders and reindexes stops on insert and on position
    change. An append-only fake hides every index-shift bug, which is the
    same class of defect as the ramp-spacing bug that already shipped.
    """

    def new(self, position):
        element = FakeElement(position, [0.0, 0.0, 0.0, 1.0])
        self.append(element)
        self.sort(key=lambda e: e.position)
        return element

    def remove(self, element):
        list.remove(self, element)

    def resort(self):
        self.sort(key=lambda e: e.position)


class FakeRamp:
    def __init__(self):
        self.elements = FakeElements(
            [
                FakeElement(0.0, [0.0, 0.0, 0.0, 1.0]),
                FakeElement(1.0, [1.0, 1.0, 1.0, 1.0]),
            ]
        )
        self.interpolation = "LINEAR"
        self.color_mode = "RGB"


# Sockets each node type exposes, enough for the recipes to wire against.
_NODE_SOCKETS = {
    "ShaderNodeTexCoord": ([], ["Generated", "Object", "UV", "Normal"]),
    "ShaderNodeMapping": (["Vector", "Location", "Rotation", "Scale"], ["Vector"]),
    "ShaderNodeTexNoise": (
        ["Vector", "Scale", "Detail", "Roughness", "Distortion"],
        ["Fac", "Color"],
    ),
    "ShaderNodeTexVoronoi": (
        ["Vector", "Scale", "Randomness"],
        ["Distance", "Color", "Position"],
    ),
    "ShaderNodeTexWave": (
        ["Vector", "Scale", "Distortion", "Detail"],
        ["Fac", "Color"],
    ),
    "ShaderNodeTexGradient": (["Vector"], ["Fac", "Color"]),
    "ShaderNodeValToRGB": (["Fac"], ["Color", "Alpha"]),
    "ShaderNodeMath": (["Value", "Value"], ["Value"]),
    "ShaderNodeMixRGB": (["Fac", "Color1", "Color2"], ["Color"]),
    "ShaderNodeBsdfPrincipled": (
        ["Base Color", "Metallic", "Roughness", "Emission Color", "Emission Strength"],
        ["BSDF"],
    ),
    "ShaderNodeOutputMaterial": (["Surface"], []),
}


# Flipped to True by the Blender-5.x fixture so FakeNode renames 'Fac' to
# 'Factor', reproducing the socket rename that shipped in 5.x.
_USE_V5_SOCKET_NAMES = False


def _sockets_for(bl_idname):
    inputs, outputs = _NODE_SOCKETS.get(bl_idname, ([], []))
    if _USE_V5_SOCKET_NAMES:
        inputs = ["Factor" if n == "Fac" else n for n in inputs]
        outputs = ["Factor" if n == "Fac" else n for n in outputs]
    return inputs, outputs


class FakeNode:
    def __init__(self, bl_idname, name):
        self.bl_idname = bl_idname
        self.name = name
        self.label = ""
        self.location = (0, 0)
        inputs, outputs = _sockets_for(bl_idname)
        self.inputs = FakeSocketCollection(FakeSocket(n) for n in inputs)
        self.outputs = FakeSocketCollection(FakeSocket(n) for n in outputs)
        if bl_idname == "ShaderNodeValToRGB":
            self.color_ramp = FakeRamp()
        if bl_idname == "ShaderNodeTexNoise":
            self.noise_dimensions = "3D"
        if bl_idname == "ShaderNodeTexVoronoi":
            self.feature = "F1"
            self.distance = "EUCLIDEAN"
            self.voronoi_dimensions = "3D"
        if bl_idname == "ShaderNodeTexWave":
            self.wave_type = "BANDS"
            self.wave_profile = "SIN"
            self.bands_direction = "X"
        if bl_idname == "ShaderNodeTexGradient":
            self.gradient_type = "LINEAR"
        if bl_idname == "ShaderNodeMath":
            self.operation = "ADD"
            self.use_clamp = False
        if bl_idname == "ShaderNodeMixRGB":
            self.blend_type = "MIX"


class FakeNodes(list):
    def __init__(self, *args):
        list.__init__(self, *args)
        self._counter = 0

    def new(self, type):
        self._counter += 1
        node = FakeNode(type, f"{type}.{self._counter:03d}")
        self.append(node)
        return node

    def get(self, name, default=None):
        for node in self:
            if node.name == name:
                return node
        return default

    def remove(self, node):
        list.remove(self, node)


class FakeLink:
    def __init__(self, from_socket, to_socket, from_node, to_node):
        self.from_socket = from_socket
        self.to_socket = to_socket
        self.from_node = from_node
        self.to_node = to_node


class FakeLinks(list):
    def __init__(self, tree):
        list.__init__(self)
        self._tree = tree

    def new(self, from_socket, to_socket):
        from_node = self._tree._owner_of(from_socket, "outputs")
        to_node = self._tree._owner_of(to_socket, "inputs")
        link = FakeLink(from_socket, to_socket, from_node, to_node)
        self.append(link)
        return link


class FakeTree:
    def __init__(self):
        bsdf = FakeNode("ShaderNodeBsdfPrincipled", "Principled BSDF")
        output = FakeNode("ShaderNodeOutputMaterial", "Material Output")
        self.nodes = FakeNodes([bsdf, output])
        self.links = FakeLinks(self)

    def _owner_of(self, socket, kind):
        for node in self.nodes:
            if socket in getattr(node, kind):
                return node
        return None


class FakeMaterial:
    def __init__(self, name):
        self.name = name
        self.use_nodes = False
        self.node_tree = None

    def _enable_nodes(self):
        self.use_nodes = True
        self.node_tree = FakeTree()


class FakeMaterials:
    def __init__(self):
        self._store = {}

    def new(self, name):
        mat = FakeMaterial(name)
        mat._enable_nodes()
        self._store[name] = mat
        return mat

    def get(self, name, default=None):
        return self._store.get(name, default)


@pytest.fixture
def bpy_materials(ph):
    import bpy

    materials = FakeMaterials()
    bpy.data.materials = materials
    return materials


def build(ph, **overrides):
    """Run the handler with sensible defaults, returning (result, material)."""
    params = {
        "name": "M",
        "pattern": "noise",
        "scale": 5.0,
        "detail": 2.0,
        "distortion": 0.0,
        "roughness": 0.5,
        "metallic": 0.0,
        "banded": False,
        "connect_to_bsdf": True,
    }
    params.update(overrides)
    return ph.handle_create_procedural_material(params)


def node_types(material):
    return [n.bl_idname for n in material.node_tree.nodes]


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


class TestGraphConstruction:
    def test_creates_the_material(self, ph, bpy_materials):
        result = build(ph, name="Lava")
        assert bpy_materials.get("Lava") is not None
        assert result["material"] == "Lava"

    def test_every_pattern_builds(self, ph, bpy_materials):
        for pattern in sorted(ph.PATTERN_BUILDERS):
            result = build(ph, name=f"M_{pattern}", pattern=pattern)
            assert result["pattern"] == pattern
            mat = bpy_materials.get(f"M_{pattern}")
            assert len(mat.node_tree.nodes) > 2

    def test_builder_table_matches_documented_patterns(self, ph):
        assert set(ph.PATTERN_BUILDERS) == {
            "gradient", "noise", "cloud", "voronoi", "veins", "scales",
            "stripes", "wood", "marble", "weave", "plasma", "fire", "sparks",
        }

    def test_unknown_pattern_raises(self, ph, bpy_materials):
        with pytest.raises(RuntimeError):
            build(ph, pattern="runes")

    def test_adds_coordinate_and_mapping(self, ph, bpy_materials):
        build(ph, name="M")
        types = node_types(bpy_materials.get("M"))
        assert "ShaderNodeTexCoord" in types
        assert "ShaderNodeMapping" in types

    def test_adds_color_ramp(self, ph, bpy_materials):
        build(ph, name="M")
        assert "ShaderNodeValToRGB" in node_types(bpy_materials.get("M"))

    def test_returns_node_names_for_later_tweaking(self, ph, bpy_materials):
        result = build(ph, name="M")
        mat = bpy_materials.get("M")
        existing = {n.name for n in mat.node_tree.nodes}
        assert result["nodes"]
        for node_name in result["nodes"].values():
            assert node_name in existing

    def test_ramp_node_name_is_reported(self, ph, bpy_materials):
        result = build(ph, name="M")
        assert "color_ramp" in result["nodes"]


# ---------------------------------------------------------------------------
# Linking
# ---------------------------------------------------------------------------


def linked_pairs(material):
    return {
        (link.from_node.bl_idname, link.to_node.bl_idname)
        for link in material.node_tree.links
        if link.from_node and link.to_node
    }


class TestLinking:
    def test_coordinates_feed_mapping(self, ph, bpy_materials):
        build(ph, name="M")
        assert ("ShaderNodeTexCoord", "ShaderNodeMapping") in linked_pairs(
            bpy_materials.get("M")
        )

    def test_connects_to_bsdf_by_default(self, ph, bpy_materials):
        build(ph, name="M")
        assert ("ShaderNodeValToRGB", "ShaderNodeBsdfPrincipled") in linked_pairs(
            bpy_materials.get("M")
        )

    def test_connect_to_bsdf_false_leaves_ramp_dangling(self, ph, bpy_materials):
        build(ph, name="M", connect_to_bsdf=False)
        assert ("ShaderNodeValToRGB", "ShaderNodeBsdfPrincipled") not in linked_pairs(
            bpy_materials.get("M")
        )

    def test_connect_to_bsdf_false_still_builds_pattern(self, ph, bpy_materials):
        build(ph, name="M", connect_to_bsdf=False)
        assert "ShaderNodeValToRGB" in node_types(bpy_materials.get("M"))

    def test_ramp_is_fed_by_something(self, ph, bpy_materials):
        build(ph, name="M")
        mat = bpy_materials.get("M")
        into_ramp = [
            link
            for link in mat.node_tree.links
            if link.to_node and link.to_node.bl_idname == "ShaderNodeValToRGB"
        ]
        assert into_ramp


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


def find(material, bl_idname):
    for node in material.node_tree.nodes:
        if node.bl_idname == bl_idname:
            return node
    return None


class TestParameters:
    def test_scale_reaches_the_mapping_node(self, ph, bpy_materials):
        build(ph, name="M", scale=8.0)
        mapping = find(bpy_materials.get("M"), "ShaderNodeMapping")
        assert list(mapping.inputs["Scale"].default_value) == [8.0, 8.0, 8.0]

    def test_gradient_ignores_scale(self, ph, bpy_materials):
        """A gradient runs once across the space.

        Tiling it saturates both ends and the ramp reads as a flat fill,
        which is what a scale of 5 was doing.
        """
        build(ph, name="M", pattern="gradient", scale=8.0)
        mapping = find(bpy_materials.get("M"), "ShaderNodeMapping")
        assert list(mapping.inputs["Scale"].default_value) == [1.0, 1.0, 1.0]

    def test_tiling_patterns_still_use_scale(self, ph, bpy_materials):
        build(ph, name="M", pattern="noise", scale=8.0)
        mapping = find(bpy_materials.get("M"), "ShaderNodeMapping")
        assert list(mapping.inputs["Scale"].default_value) == [8.0, 8.0, 8.0]

    def test_detail_reaches_noise(self, ph, bpy_materials):
        build(ph, name="M", pattern="noise", detail=7.0)
        noise = find(bpy_materials.get("M"), "ShaderNodeTexNoise")
        assert noise.inputs["Detail"].default_value == 7.0

    def test_distortion_reaches_noise(self, ph, bpy_materials):
        build(ph, name="M", pattern="noise", distortion=3.0)
        noise = find(bpy_materials.get("M"), "ShaderNodeTexNoise")
        assert noise.inputs["Distortion"].default_value == 3.0

    def test_roughness_and_metallic_reach_the_bsdf(self, ph, bpy_materials):
        build(ph, name="M", roughness=0.15, metallic=0.9)
        bsdf = find(bpy_materials.get("M"), "ShaderNodeBsdfPrincipled")
        assert bsdf.inputs["Roughness"].default_value == 0.15
        assert bsdf.inputs["Metallic"].default_value == 0.9

    def test_veins_uses_distance_to_edge(self, ph, bpy_materials):
        """The distinguishing feature of the veins pattern."""
        build(ph, name="M", pattern="veins")
        voronoi = find(bpy_materials.get("M"), "ShaderNodeTexVoronoi")
        assert voronoi.feature == "DISTANCE_TO_EDGE"

    def test_scales_uses_f1(self, ph, bpy_materials):
        build(ph, name="M", pattern="scales")
        voronoi = find(bpy_materials.get("M"), "ShaderNodeTexVoronoi")
        assert voronoi.feature == "F1"

    def test_math_constants_never_land_on_a_linked_socket(self, ph, bpy_materials):
        """A Math node has two inputs both named 'Value'.

        Name lookup returns inputs[0] every time, so setting a constant by
        name puts it on whichever socket happens to be linked, where it is
        ignored. Sparks shipped with its exponent on the linked input,
        rendering as x**0.5 instead of x**8.

        A Math node whose inputs are both linked is fine — it needs no
        constant. What must never happen is a non-default value sitting on
        a linked socket, which means the write went to the wrong place.
        """
        for pattern in sorted(ph.PATTERN_BUILDERS):
            name = f"M_{pattern}"
            build(ph, name=name, pattern=pattern)
            mat = bpy_materials.get(name)
            linked = {link.to_socket for link in mat.node_tree.links}
            for node in mat.node_tree.nodes:
                if node.bl_idname != "ShaderNodeMath":
                    continue
                for i, socket in enumerate(node.inputs):
                    if socket in linked and socket.default_value != 0.0:
                        raise AssertionError(
                            f"{pattern}/{node.label}: inputs[{i}] is linked "
                            f"but carries {socket.default_value}, so the "
                            f"constant went to the wrong socket"
                        )

    def test_sparks_exponent_is_on_the_free_socket(self, ph, bpy_materials):
        build(ph, name="M", pattern="sparks")
        mat = bpy_materials.get("M")
        sharpen = next(n for n in mat.node_tree.nodes if n.label == "Sharpen")
        linked = {link.to_socket for link in mat.node_tree.links}
        assert sharpen.inputs[0] in linked, "base should be linked"
        assert sharpen.inputs[1] not in linked, "exponent should be free"
        assert sharpen.inputs[1].default_value == 8.0

    def test_sparks_invert_constant_is_on_the_free_socket(self, ph, bpy_materials):
        build(ph, name="M", pattern="sparks")
        mat = bpy_materials.get("M")
        invert = next(n for n in mat.node_tree.nodes if n.label == "Invert")
        linked = {link.to_socket for link in mat.node_tree.links}
        assert invert.inputs[0] not in linked
        assert invert.inputs[0].default_value == 1.0
        assert invert.inputs[1] in linked

    def test_wood_uses_ring_bands(self, ph, bpy_materials):
        build(ph, name="M", pattern="wood")
        wave = find(bpy_materials.get("M"), "ShaderNodeTexWave")
        assert wave.wave_type == "RINGS"

    def test_stripes_uses_bands(self, ph, bpy_materials):
        build(ph, name="M", pattern="stripes")
        wave = find(bpy_materials.get("M"), "ShaderNodeTexWave")
        assert wave.wave_type == "BANDS"


# ---------------------------------------------------------------------------
# Colour ramp behaviour
# ---------------------------------------------------------------------------


class TestRamp:
    def test_banded_sets_constant_interpolation(self, ph, bpy_materials):
        build(ph, name="M", banded=True)
        ramp = find(bpy_materials.get("M"), "ShaderNodeValToRGB")
        assert ramp.color_ramp.interpolation == "CONSTANT"

    def test_unbanded_is_not_constant(self, ph, bpy_materials):
        build(ph, name="M", banded=False)
        ramp = find(bpy_materials.get("M"), "ShaderNodeValToRGB")
        assert ramp.color_ramp.interpolation != "CONSTANT"

    def test_custom_colors_replace_the_palette(self, ph, bpy_materials):
        build(
            ph,
            name="M",
            colors=[[1.0, 0.0, 0.0, 1.0], [0.0, 1.0, 0.0, 1.0], [0.0, 0.0, 1.0, 1.0]],
        )
        ramp = find(bpy_materials.get("M"), "ShaderNodeValToRGB")
        assert len(ramp.color_ramp.elements) == 3
        assert list(ramp.color_ramp.elements[0].color) == [1.0, 0.0, 0.0, 1.0]
        assert list(ramp.color_ramp.elements[2].color) == [0.0, 0.0, 1.0, 1.0]

    def test_custom_colors_spread_across_the_ramp(self, ph, bpy_materials):
        build(
            ph,
            name="M",
            colors=[[1.0, 0.0, 0.0, 1.0], [0.0, 1.0, 0.0, 1.0], [0.0, 0.0, 1.0, 1.0]],
        )
        ramp = find(bpy_materials.get("M"), "ShaderNodeValToRGB")
        positions = [e.position for e in ramp.color_ramp.elements]
        assert positions[0] == 0.0
        assert positions[-1] == 1.0
        assert positions == sorted(positions)

    def test_single_custom_color(self, ph, bpy_materials):
        build(ph, name="M", colors=[[1.0, 0.5, 0.0, 1.0]])
        ramp = find(bpy_materials.get("M"), "ShaderNodeValToRGB")
        assert len(ramp.color_ramp.elements) == 1
        assert list(ramp.color_ramp.elements[0].color) == [1.0, 0.5, 0.0, 1.0]

    def test_fire_default_palette_is_dark_to_bright(self, ph, bpy_materials):
        """Fire ramps from near-black through red to a hot bright tip."""
        build(ph, name="M", pattern="fire")
        ramp = find(bpy_materials.get("M"), "ShaderNodeValToRGB")
        elements = ramp.color_ramp.elements
        assert len(elements) >= 3
        first_sum = sum(elements[0].color[:3])
        last_sum = sum(elements[-1].color[:3])
        assert last_sum > first_sum

    def test_banded_last_stop_is_not_at_the_end(self, ph, bpy_materials):
        """CONSTANT holds a colour until the next stop.

        A final stop at position 1.0 would only show at exactly 1.0, so the
        last band would never render and a 2-colour banded ramp would look
        like a flat fill.
        """
        build(ph, name="M", banded=True, colors=[[0.0] * 4, [1.0] * 4])
        ramp = find(bpy_materials.get("M"), "ShaderNodeValToRGB")
        assert ramp.color_ramp.elements[-1].position < 1.0

    def test_banded_bands_are_evenly_wide(self, ph, bpy_materials):
        build(
            ph,
            name="M",
            banded=True,
            colors=[[0.0] * 4, [0.5] * 4, [1.0] * 4, [0.25] * 4],
        )
        ramp = find(bpy_materials.get("M"), "ShaderNodeValToRGB")
        positions = [e.position for e in ramp.color_ramp.elements]
        assert positions == [0.0, 0.25, 0.5, 0.75]

    def test_unbanded_still_spans_the_full_ramp(self, ph, bpy_materials):
        build(ph, name="M", banded=False, colors=[[0.0] * 4, [1.0] * 4])
        ramp = find(bpy_materials.get("M"), "ShaderNodeValToRGB")
        assert ramp.color_ramp.elements[-1].position == 1.0

    def test_default_palette_used_when_colors_absent(self, ph, bpy_materials):
        build(ph, name="M", pattern="fire")
        ramp = find(bpy_materials.get("M"), "ShaderNodeValToRGB")
        assert len(ramp.color_ramp.elements) >= 3


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


class TestBlenderVersionSocketNames:
    """Blender 5.x renamed 'Fac' to 'Factor' on Noise, Gradient, Wave and
    ColorRamp. Recipes must build correctly under either spelling."""

    @pytest.fixture
    def bpy_materials_v5(self, ph, monkeypatch):
        import bpy

        monkeypatch.setattr(
            sys.modules[__name__], "_USE_V5_SOCKET_NAMES", True, raising=False
        )
        materials = FakeMaterials()
        bpy.data.materials = materials
        return materials

    def test_fixture_actually_renames(self, bpy_materials_v5):
        """Guard the guard: if this fails, the rename tests prove nothing."""
        node = FakeNode("ShaderNodeTexNoise", "n")
        assert node.outputs.get("Factor") is not None
        assert node.outputs.get("Fac") is None

    def test_every_pattern_builds_with_factor_naming(self, ph, bpy_materials_v5):
        for pattern in sorted(ph.PATTERN_BUILDERS):
            build(ph, name=f"V5_{pattern}", pattern=pattern)
            mat = bpy_materials_v5.get(f"V5_{pattern}")
            ramp_fed = [
                link
                for link in mat.node_tree.links
                if link.to_node and link.to_node.bl_idname == "ShaderNodeValToRGB"
            ]
            assert ramp_fed, f"{pattern}: nothing reaches the colour ramp"

    def test_ramp_reaches_bsdf_with_factor_naming(self, ph, bpy_materials_v5):
        build(ph, name="V5", pattern="fire")
        assert ("ShaderNodeValToRGB", "ShaderNodeBsdfPrincipled") in linked_pairs(
            bpy_materials_v5.get("V5")
        )


class TestFailureHandling:
    def test_duplicate_name_still_succeeds(self, ph, bpy_materials):
        """Blender uniquifies names; a second build must not explode."""
        build(ph, name="M")
        result = build(ph, name="M")
        assert result["material"]

    def test_registers_command(self, ph):
        ph.dispatcher.register_handler.reset_mock()
        ph.register()
        registered = {
            call.args[0] for call in ph.dispatcher.register_handler.call_args_list
        }
        assert "create_procedural_material" in registered
