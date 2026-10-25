"""Procedural materials in a real Blender, read back through get_node_tree.
Replaces the fake-bpy procedural handler tests."""

import pytest

from blenderwright.tools import materials as m

PATTERNS = ["gradient", "noise", "cloud", "voronoi", "veins", "scales", "stripes", "wood",
            "marble", "weave", "plasma", "fire", "sparks"]


def _nodes(material):
    return {n["name"]: n for n in m.get_node_tree(material)["nodes"]}


def _of_type(material, node_type):
    return [n for n in m.get_node_tree(material)["nodes"] if n["type"] == node_type]


@pytest.mark.parametrize("pattern", PATTERNS)
def test_every_pattern_builds_and_reaches_the_bsdf(scene, pattern):
    result = m.create_procedural_material(f"M_{pattern}", pattern)
    assert result["material"] == f"M_{pattern}" and result["pattern"] == pattern
    nodes = _nodes(f"M_{pattern}")
    assert set(result["nodes"].values()) <= set(nodes)
    links = m.get_node_tree(f"M_{pattern}")["links"]
    ramp = result["nodes"]["color_ramp"]
    assert any(lk["from_node"] == ramp and lk["to_node"] == "Principled BSDF" for lk in links)
    assert any(lk["to_node"] == ramp for lk in links)  # something feeds the ramp


def test_scale_reaches_the_mapping_node(scene):
    m.create_procedural_material("M", "noise", scale=7.0)
    mapping = _of_type("M", "ShaderNodeMapping")[0]
    assert mapping["values"]["Scale"] == pytest.approx([7.0, 7.0, 7.0])


def test_detail_and_distortion_reach_the_noise(scene):
    m.create_procedural_material("M", "noise", detail=6.0, distortion=0.4)
    noise = _of_type("M", "ShaderNodeTexNoise")[0]
    assert noise["values"]["Detail"] == pytest.approx(6.0)
    assert noise["values"]["Distortion"] == pytest.approx(0.4)


def test_roughness_and_metallic_reach_the_bsdf(scene):
    m.create_procedural_material("M", "marble", roughness=0.2, metallic=0.9)
    bsdf = _nodes("M")["Principled BSDF"]
    assert bsdf["values"]["Roughness"] == pytest.approx(0.2)
    assert bsdf["values"]["Metallic"] == pytest.approx(0.9)


def test_veins_use_distance_to_edge(scene):
    m.create_procedural_material("M", "veins")
    assert _of_type("M", "ShaderNodeTexVoronoi")[0]["settings"]["feature"] == "DISTANCE_TO_EDGE"


def test_wood_uses_ring_bands(scene):
    m.create_procedural_material("M", "wood")
    assert _of_type("M", "ShaderNodeTexWave")[0]["settings"]["wave_type"] == "RINGS"


def test_not_connected_leaves_the_bsdf_alone(scene):
    result = m.create_procedural_material("M", "noise", connect_to_bsdf=False)
    links = m.get_node_tree("M")["links"]
    assert not any(lk["from_node"] == result["nodes"]["color_ramp"] for lk in links)


def test_banded_ramp_is_constant_with_even_bands(scene):
    m.create_procedural_material("M", "stripes", banded=True,
                                 colors=[[1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 1]])
    ramp = m.get_color_ramp("M", "Color Ramp")
    assert ramp["interpolation"] == "CONSTANT"
    positions = [e["position"] for e in ramp["elements"]]
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    assert max(gaps) == pytest.approx(min(gaps), abs=0.01)
    assert positions[-1] < 1.0  # the last band still gets its share


def test_custom_colours_replace_the_palette_and_span_it(scene):
    m.create_procedural_material("M", "noise", colors=[[1, 0, 0, 1], [0, 0, 1, 1]])
    elements = m.get_color_ramp("M", "Color Ramp")["elements"]
    assert [e["color"] for e in elements] == [pytest.approx([1, 0, 0, 1]),
                                              pytest.approx([0, 0, 1, 1])]
    assert (elements[0]["position"], elements[-1]["position"]) == pytest.approx((0.0, 1.0))


def test_fire_runs_dark_to_bright(scene):
    m.create_procedural_material("M", "fire")
    brightness = [sum(e["color"][:3]) for e in m.get_color_ramp("M", "Color Ramp")["elements"]]
    assert brightness == sorted(brightness) and brightness[0] < brightness[-1]


def test_unknown_pattern(scene):
    with pytest.raises(Exception):
        m.create_procedural_material("M", "runes")
