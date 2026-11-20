"""Sliders in a real Blender: moving one moves what it drives."""

import pytest

from blenderwright.server import mcp
from blenderwright.tools.objects import create_object, get_object_info

T = {x.name: x.fn for x in mcp._tool_manager.list_tools()}


def test_slider_drives_a_property(scene):
    create_object("CUBE", name="Box")
    T["add_slider"]("Box", "Slide", min=0, max=4, drives=[
        {"data_path": "location", "index": 0, "expression": "value * 2"}])
    T["set_slider"]("Box", "Slide", 1.5)
    assert get_object_info("Box")["location"][0] == pytest.approx(3.0)


def test_slider_on_one_object_drives_another(scene):
    create_object("CUBE", name="Box")
    create_object("EMPTY", name="Rig")
    T["add_slider"]("Rig", "Lift", drives=[
        {"object": "Box", "data_path": "location", "index": 2}])
    T["set_slider"]("Rig", "Lift", 0.75)
    assert get_object_info("Box")["location"][2] == pytest.approx(0.75)


def test_slider_drives_a_shape_key(scene):
    create_object("CUBE", name="Box")
    T["add_shape_key"]("Box", "Basis")
    T["add_shape_key"]("Box", "Bulge")
    T["add_slider"]("Box", "Bulge", drives=[
        {"data_path": 'data.shape_keys.key_blocks["Bulge"].value'}])
    T["set_slider"]("Box", "Bulge", 0.6)
    keys = {k["name"]: k["value"] for k in T["list_shape_keys"]("Box")["keys"]}
    assert keys["Bulge"] == pytest.approx(0.6)


def test_values_outside_the_range_are_refused(scene):
    create_object("CUBE", name="Box")
    T["add_slider"]("Box", "Open", min=0, max=1)
    with pytest.raises(RuntimeError, match="range"):
        T["set_slider"]("Box", "Open", 2)


def test_remove_slider_takes_its_drivers_with_it(scene):
    create_object("CUBE", name="Box")
    T["add_slider"]("Box", "Slide", drives=[{"data_path": "location", "index": 0}])
    assert T["list_drivers"]("Box")["drivers"]
    T["remove_slider"]("Box", "Slide")
    assert T["list_drivers"]("Box")["drivers"] == []
    with pytest.raises(RuntimeError):
        T["set_slider"]("Box", "Slide", 0.5)


def test_a_drive_to_a_missing_property_leaves_nothing_behind(scene):
    create_object("CUBE", name="Box")
    with pytest.raises(RuntimeError):
        T["add_slider"]("Box", "Oops", drives=[{"data_path": "data.nope"}])
    with pytest.raises(RuntimeError):
        T["set_slider"]("Box", "Oops", 0.5)
