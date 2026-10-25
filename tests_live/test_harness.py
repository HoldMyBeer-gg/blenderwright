"""The harness itself: real tools reach a real Blender."""

from blenderwright.tools.objects import list_objects
from blenderwright.tools.scene import get_scene_info


def test_factory_scene(scene):
    names = {o["name"] for o in list_objects()}
    assert {"Cube", "Camera", "Light"} <= names


def test_each_test_starts_fresh(scene):
    from blenderwright.tools.objects import create_object

    create_object("UV_SPHERE", name="Leftover")
    assert "Leftover" in {o["name"] for o in list_objects()}


def test_previous_test_left_nothing(scene):
    assert "Leftover" not in {o["name"] for o in list_objects()}
    assert get_scene_info()["object_count"] == 3
