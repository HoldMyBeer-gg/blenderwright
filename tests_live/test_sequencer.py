"""The sequencer in a real Blender, checked by rendering frames and reading pixels."""

import pytest

from blenderwright.tools.animation import set_frame
from blenderwright.tools.render_settings import set_color_management
from blenderwright.tools.rendering import render_image, set_render_resolution
from blenderwright.tools.sequencer import add_sequencer_strip, add_strip_fade, set_strip_property
from tests_live.pixels import centre


def _render(scene, name, frame=1):
    set_frame(frame)
    out = scene / f"{name}.png"
    render_image(filepath=str(out))
    return centre(out)


@pytest.fixture
def small(scene):
    """Tiny frames, and Standard colour so red renders as red (AgX shifts it)."""
    set_render_resolution(width=32, height=32)
    set_color_management(view_transform="Standard")
    return scene


def test_color_strip_fills_the_frame(small):
    add_sequencer_strip("COLOR", name="Red", color=[1, 0, 0], length=10)
    r, g, b = _render(small, "red")
    assert r > 200 and g < 30 and b < 30


def test_fade_in_starts_dark(small):
    add_sequencer_strip("COLOR", name="White", color=[1, 1, 1], length=40)
    add_strip_fade("White", fade_in=20)
    first, settled = _render(small, "f1", 1), _render(small, "f30", 30)
    assert sum(first) < 60 and sum(settled) > 600


def test_transform_moves_the_strip_off_centre(small):
    add_sequencer_strip("COLOR", name="Green", color=[0, 1, 0], length=10)
    set_strip_property("Green", transform={"scale_x": 0.2, "scale_y": 0.2, "offset_x": 12})
    r, g, b = _render(small, "moved")
    assert g < 50  # the centre pixel is no longer covered


def test_text_strip_settings(small):
    result = add_sequencer_strip("TEXT", name="Title", text="Hello", length=24, font_size=60)
    assert result["type"] == "TEXT" and result["frame_end"] == 24


def test_unknown_setting_is_refused(small):
    add_sequencer_strip("COLOR", name="Red", color=[1, 0, 0], length=10)
    with pytest.raises(RuntimeError, match="setting"):
        set_strip_property("Red", settings={"use_flip_z": True})
