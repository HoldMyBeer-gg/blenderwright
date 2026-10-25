"""Geometry node zones in a real Blender: a repeat loop and a frame-by-frame simulation."""

import pytest

from blenderwright.tools.animation import set_frame
from blenderwright.tools.geometry_nodes import build_geometry_nodes
from blenderwright.tools.objects import create_object, get_object_info


def _dims(name):
    return get_object_info(name)["dimensions"]


def test_repeat_zone_scales_three_times(scene):
    create_object("CUBE", name="Box")
    build_geometry_nodes("Box", {
        "nodes": [
            {"name": "loop_in", "type": "GeometryNodeRepeatInput", "pair_with": "loop_out",
             "inputs": {"Iterations": 3}},
            {"name": "loop_out", "type": "GeometryNodeRepeatOutput"},
            {"name": "grow", "type": "GeometryNodeTransform", "inputs": {"Scale": [2, 2, 2]}},
        ],
        "links": [
            ["Group Input", "Geometry", "loop_in", "Geometry"],
            ["loop_in", "Geometry", "grow", "Geometry"],
            ["grow", "Geometry", "loop_out", "Geometry"],
            ["loop_out", "Geometry", "Group Output", "Geometry"],
        ]})
    assert _dims("Box") == pytest.approx([16.0, 16.0, 16.0], rel=0.01)  # 2 * 2^3


def test_simulation_zone_grows_frame_by_frame(scene):
    create_object("CUBE", name="Box")
    build_geometry_nodes("Box", {
        "nodes": [
            {"name": "sim_in", "type": "GeometryNodeSimulationInput", "pair_with": "sim_out"},
            {"name": "sim_out", "type": "GeometryNodeSimulationOutput"},
            {"name": "grow", "type": "GeometryNodeTransform", "inputs": {"Scale": [1.1, 1.1, 1.1]}},
        ],
        "links": [
            ["Group Input", "Geometry", "sim_in", "Geometry"],
            ["sim_in", "Geometry", "grow", "Geometry"],
            ["grow", "Geometry", "sim_out", "Geometry"],
            ["sim_out", "Geometry", "Group Output", "Geometry"],
        ]})
    sizes = []
    for frame in range(1, 6):
        set_frame(frame)
        sizes.append(_dims("Box")[0])
    assert sizes == sorted(sizes) and sizes[-1] > sizes[0] * 1.3


def test_pairing_a_node_that_is_not_a_zone(scene):
    create_object("CUBE", name="Box")
    with pytest.raises(RuntimeError, match="zone"):
        build_geometry_nodes("Box", {"nodes": [
            {"name": "math", "type": "ShaderNodeMath", "pair_with": "out"},
            {"name": "out", "type": "GeometryNodeRepeatOutput"}]})
