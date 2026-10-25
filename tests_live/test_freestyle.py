"""Freestyle in a real Blender: rendered lines add dark pixels around the cube."""

from blenderwright.tools.render_settings import set_color_management, set_freestyle
from blenderwright.tools.rendering import (render_image, set_render_engine,
                                           set_render_resolution, set_render_samples)
from tests_live.pixels import read_png


def _dark_pixels(path):
    _, _, rows = read_png(path)
    return sum(1 for row in rows for pixel in row if sum(pixel) < 40)


def _render(scene, name):
    out = scene / f"{name}.png"
    render_image(filepath=str(out))
    return _dark_pixels(out)


def test_lines_are_drawn(scene):
    set_render_resolution(width=64, height=64)
    set_render_engine(engine="CYCLES")
    set_render_samples(samples=1)
    set_color_management(view_transform="Standard")
    without = _render(scene, "plain")
    result = set_freestyle(thickness=3, color=[0, 0, 0], edges=["SILHOUETTE", "CREASE"])
    assert result["enabled"] is True
    with_lines = _render(scene, "inked")
    assert with_lines > without + 50


def test_turning_off(scene):
    set_freestyle(thickness=3)
    assert set_freestyle(enabled=False)["enabled"] is False
