"""Lattices in a real Blender: the mesh actually changes shape.

get_object_info's dimensions come from the evaluated mesh, modifiers included.
"""

import pytest

from blenderwright.tools.deform import create_lattice, move_lattice_points
from blenderwright.tools.objects import create_object, get_object_info


def _dims(name):
    return get_object_info(name)["dimensions"]


def test_lattice_fits_the_object(scene):
    create_object("CYLINDER", name="Vase", location=[3, 0, 1], scale=[1, 1, 2])
    result = create_lattice("Vase", resolution=[3, 3, 4])
    assert result["points"] == 36
    cage = get_object_info(result["lattice"])
    assert cage["location"] == pytest.approx([3.0, 0.0, 1.0], abs=0.01)
    assert _dims("Vase") == pytest.approx([2.0, 2.0, 4.0], abs=0.01)  # fitted: no change yet


def test_scaling_every_point_narrows_the_mesh(scene):
    create_object("CUBE", name="Block")
    lattice = create_lattice("Block")["lattice"]
    move_lattice_points(lattice, scale=[0.5, 1, 1])
    assert _dims("Block") == pytest.approx([1.0, 2.0, 2.0], abs=0.01)


def test_side_moves_only_the_top(scene):
    create_object("CUBE", name="Block")
    lattice = create_lattice("Block")["lattice"]
    result = move_lattice_points(lattice, offset=[0, 0, 2], axis="Z", sign="POS")
    assert result["moved"] == 4
    assert _dims("Block") == pytest.approx([2.0, 2.0, 4.0], abs=0.01)


def test_reset_restores_the_shape(scene):
    create_object("CUBE", name="Block")
    lattice = create_lattice("Block")["lattice"]
    move_lattice_points(lattice, offset=[0, 0, 2], axis="Z", sign="POS")
    move_lattice_points(lattice, reset=True)
    assert _dims("Block") == pytest.approx([2.0, 2.0, 2.0], abs=0.01)


def test_bspline_is_softer_than_its_points(scene):
    """B-spline approximates the cage: half-scaled points give a 2/3-wide cube."""
    create_object("CUBE", name="Block")
    lattice = create_lattice("Block", interpolation="KEY_BSPLINE")["lattice"]
    move_lattice_points(lattice, scale=[0.5, 1, 1])
    assert _dims("Block")[0] == pytest.approx(4 / 3, abs=0.01)


def test_unknown_lattice(scene):
    with pytest.raises(RuntimeError, match="Ghost"):
        move_lattice_points("Ghost", offset=[0, 0, 1])
