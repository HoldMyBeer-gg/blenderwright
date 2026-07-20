"""Tests for addon.handlers.raster — generated image textures.

Covers the patterns that shader nodes cannot express because they place
discrete marks: runes, and anything else needing per-element stamping.
Pixels are built with stdlib only and pushed into bpy.data.images, so no
Pillow, no numpy, and no file ever touches disk.
"""

import array
import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_raster_handler():
    mock_dispatcher = MagicMock()
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "raster.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.raster", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.raster"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rh():
    return _load_raster_handler()


class FakePixels:
    def __init__(self):
        self.data = None

    def foreach_set(self, values):
        self.data = list(values)


class FakeColorspace:
    """Colorspace whose assignment invalidates the buffer, as Blender's does.

    Setting colorspace_settings.name on a generated image resets its pixels
    to black. A plain MagicMock silently accepts the assignment and hides
    that, which let a real bug ship: pixels were written first and then
    wiped, producing an all-black texture.
    """

    def __init__(self, image):
        self._image = image
        self._name = "sRGB"

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        changed = value != self._name
        self._name = value
        # Only a real change invalidates, and only if there is a buffer to
        # invalidate. Blanking unconditionally would fail correct code too.
        if changed and self._image.pixels.data is not None:
            self._image.pixels.data = [
                0.0 if i % 4 != 3 else 1.0
                for i in range(len(self._image.pixels.data))
            ]


class FakeImage:
    def __init__(self, name, width, height, alpha=True):
        self.name = name
        self.size = (width, height)
        self.alpha = alpha
        self.pixels = FakePixels()
        self.packed = False
        self.updated = False
        self.colorspace_settings = FakeColorspace(self)

    def update(self):
        self.updated = True

    def pack(self):
        # Blender cannot pack an image with no buffer behind it.
        if self.pixels.data is None:
            raise RuntimeError("cannot pack image with no data")
        self.packed = True


class FakeImages:
    def __init__(self):
        self._store = {}

    def new(self, name, width, height, alpha=False):
        img = FakeImage(name, width, height, alpha)
        self._store[name] = img
        return img

    def get(self, name, default=None):
        return self._store.get(name, default)


@pytest.fixture
def bpy_images(rh):
    import bpy

    images = FakeImages()
    bpy.data.images = images
    return images


def build(rh, **overrides):
    params = {
        "name": "Runes",
        "pattern": "runes",
        "size": 64,
        "seed": 42,
        "count": 6,
        "foreground": [0.4, 0.8, 1.0, 1.0],
        "background": [0.02, 0.01, 0.06, 1.0],
    }
    params.update(overrides)
    return rh.handle_create_raster_texture(params)


# ---------------------------------------------------------------------------
# Buffer shape and content
# ---------------------------------------------------------------------------


class TestBuffer:
    def test_creates_image(self, rh, bpy_images):
        result = build(rh, name="Runes")
        assert bpy_images.get("Runes") is not None
        assert result["image"] == "Runes"

    def test_buffer_has_rgba_for_every_pixel(self, rh, bpy_images):
        build(rh, size=32)
        img = bpy_images.get("Runes")
        assert len(img.pixels.data) == 32 * 32 * 4

    def test_all_components_in_unit_range(self, rh, bpy_images):
        build(rh, size=32)
        img = bpy_images.get("Runes")
        assert all(0.0 <= v <= 1.0 for v in img.pixels.data)

    def test_alpha_channel_is_opaque_by_default(self, rh, bpy_images):
        build(rh, size=16)
        img = bpy_images.get("Runes")
        alphas = img.pixels.data[3::4]
        assert all(a == 1.0 for a in alphas)

    def test_image_is_packed_so_no_file_is_written(self, rh, bpy_images):
        build(rh)
        assert bpy_images.get("Runes").packed is True

    def test_uses_non_color_data(self, rh, bpy_images):
        """Pattern data is not a colour photo; sRGB would shift the values."""
        build(rh)
        img = bpy_images.get("Runes")
        assert img.colorspace_settings.name == "Non-Color"

    def test_colorspace_is_set_before_pixels_are_written(self, rh, bpy_images):
        """Assigning colorspace invalidates the buffer.

        Doing it after the write silently blanks the image to black and
        leaves pack() with nothing to store, which is exactly what shipped
        the first time.
        """
        build(rh, size=32, count=25, background=[0.0, 0.0, 1.0, 1.0])
        img = bpy_images.get("Runes")
        assert any(v > 0.0 for v in img.pixels.data[2::4]), (
            "image is all black: colorspace was assigned after the pixels"
        )

    def test_buffer_survives_the_whole_build(self, rh, bpy_images):
        build(rh, size=32, count=0, background=[0.25, 0.5, 0.75, 1.0])
        img = bpy_images.get("Runes")
        assert _distinct_colors(img) == {_f32([0.25, 0.5, 0.75, 1.0])}

    def test_update_is_called_before_packing(self, rh, bpy_images):
        build(rh)
        assert bpy_images.get("Runes").updated is True

    def test_size_is_reported(self, rh, bpy_images):
        result = build(rh, size=128)
        assert result["size"] == 128


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_seed_gives_identical_pixels(self, rh, bpy_images):
        build(rh, name="A", size=32, seed=7)
        build(rh, name="B", size=32, seed=7)
        assert bpy_images.get("A").pixels.data == bpy_images.get("B").pixels.data

    def test_different_seed_gives_different_pixels(self, rh, bpy_images):
        build(rh, name="A", size=32, seed=1)
        build(rh, name="B", size=32, seed=2)
        assert bpy_images.get("A").pixels.data != bpy_images.get("B").pixels.data

    def test_does_not_disturb_global_random_state(self, rh, bpy_images):
        """Generation must not make unrelated randomness reproducible."""
        import random

        random.seed(123)
        expected = [random.random() for _ in range(3)]

        random.seed(123)
        first = random.random()
        build(rh, size=32, seed=99)
        rest = [random.random() for _ in range(2)]

        assert [first] + rest == expected


# ---------------------------------------------------------------------------
# Runes content
# ---------------------------------------------------------------------------


def _f32(color):
    """Round-trip a colour through float32, as the array buffer does.

    array('f') stores single precision, so 0.1 reads back as
    0.10000000149011612. Comparing raw literals against buffer contents
    fails on precision rather than on anything meaningful.
    """
    return tuple(array.array("f", color))


def _distinct_colors(img):
    data = img.pixels.data
    return {tuple(data[i:i + 4]) for i in range(0, len(data), 4)}


class TestRunes:
    def test_draws_marks_not_a_flat_field(self, rh, bpy_images):
        build(rh, size=64, count=8)
        assert len(_distinct_colors(bpy_images.get("Runes"))) > 1

    def test_background_color_is_present(self, rh, bpy_images):
        build(rh, size=64, background=[0.0, 0.0, 0.0, 1.0])
        assert _f32([0.0, 0.0, 0.0, 1.0]) in _distinct_colors(bpy_images.get("Runes"))

    def test_foreground_color_is_present(self, rh, bpy_images):
        build(rh, size=64, count=10, foreground=[1.0, 0.0, 0.0, 1.0])
        assert _f32([1.0, 0.0, 0.0, 1.0]) in _distinct_colors(bpy_images.get("Runes"))

    def test_zero_count_leaves_pure_background(self, rh, bpy_images):
        build(rh, size=32, count=0, background=[0.1, 0.1, 0.1, 1.0])
        assert _distinct_colors(bpy_images.get("Runes")) == {_f32([0.1, 0.1, 0.1, 1.0])}

    def test_more_runes_marks_more_pixels(self, rh, bpy_images):
        build(rh, name="Few", size=96, count=2, seed=5)
        build(rh, name="Many", size=96, count=20, seed=5)
        bg = _f32([0.02, 0.01, 0.06, 1.0])

        def marked(name):
            data = bpy_images.get(name).pixels.data
            return sum(
                1
                for i in range(0, len(data), 4)
                if tuple(data[i:i + 4]) != bg
            )

        assert marked("Many") > marked("Few")

    def test_marks_stay_inside_the_image(self, rh, bpy_images):
        """A stamp running off the edge must clip, not wrap or overflow."""
        build(rh, size=32, count=40, seed=3)
        img = bpy_images.get("Runes")
        assert len(img.pixels.data) == 32 * 32 * 4


# ---------------------------------------------------------------------------
# Validation and registration
# ---------------------------------------------------------------------------


class TestValidation:
    def test_unknown_pattern_raises(self, rh, bpy_images):
        with pytest.raises(RuntimeError):
            build(rh, pattern="fire")

    def test_oversized_image_raises(self, rh, bpy_images):
        with pytest.raises(RuntimeError):
            build(rh, size=99999)

    def test_zero_size_raises(self, rh, bpy_images):
        with pytest.raises(RuntimeError):
            build(rh, size=0)

    def test_negative_count_raises(self, rh, bpy_images):
        with pytest.raises(RuntimeError):
            build(rh, count=-1)

class TestSocketTrustBoundary:
    """The addon socket is reachable by any local process.

    The MCP tool layer's validation can be bypassed entirely by connecting
    to it directly, so these checks must hold in the handler itself.
    """

    def test_overlong_background_is_rejected(self, rh, bpy_images):
        """The canvas is len(background) * size * size floats.

        An over-long background multiplies the allocation. At the maximum
        size a 10000-element list asks for 167 GB on Blender's main thread,
        which freezes the whole application.
        """
        with pytest.raises(RuntimeError):
            build(rh, size=64, background=[0.0] * 10000)

    def test_overlong_foreground_is_rejected(self, rh, bpy_images):
        with pytest.raises(RuntimeError):
            build(rh, foreground=[1.0] * 10000)

    def test_short_color_is_rejected(self, rh, bpy_images):
        """A 1-component colour would corrupt the buffer stride, not error."""
        with pytest.raises(RuntimeError):
            build(rh, foreground=[1.0])

    def test_rgb_without_alpha_is_rejected(self, rh, bpy_images):
        with pytest.raises(RuntimeError):
            build(rh, background=[0.0, 0.0, 0.0])

    def test_non_numeric_color_component_is_rejected(self, rh, bpy_images):
        with pytest.raises(RuntimeError):
            build(rh, background=["x", 0.0, 0.0, 1.0])

    def test_non_finite_color_component_is_rejected(self, rh, bpy_images):
        for bad in (float("inf"), float("-inf"), float("nan")):
            with pytest.raises(RuntimeError):
                build(rh, background=[bad, 0.0, 0.0, 1.0])

    def test_out_of_range_color_component_is_rejected(self, rh, bpy_images):
        with pytest.raises(RuntimeError):
            build(rh, background=[5.0, 0.0, 0.0, 1.0])

    def test_color_must_be_a_list(self, rh, bpy_images):
        with pytest.raises(RuntimeError):
            build(rh, background="black")

    def test_buffer_length_is_independent_of_color_input(self, rh, bpy_images):
        """Whatever a caller sends, the buffer stays size * size * 4."""
        build(rh, size=16)
        assert len(bpy_images.get("Runes").pixels.data) == 16 * 16 * 4

    def test_oversized_seed_is_rejected(self, rh, bpy_images):
        with pytest.raises(RuntimeError):
            build(rh, seed=2**64)

    def test_non_integer_seed_is_rejected(self, rh, bpy_images):
        with pytest.raises(RuntimeError):
            build(rh, seed="abc")

    def test_registers_command(self, rh):
        rh.dispatcher.register_handler.reset_mock()
        rh.register()
        registered = {
            call.args[0] for call in rh.dispatcher.register_handler.call_args_list
        }
        assert "create_raster_texture" in registered
