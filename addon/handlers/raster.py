"""Blender handlers for generated image textures.

For patterns that place discrete marks, which the shader graph cannot do.
Shader nodes evaluate a function per point with no notion of "draw a glyph
here, then another one over there", so runes need a pixel buffer.

Pixels are built with the standard library only and pushed straight into
bpy.data.images, then packed. No Pillow, no numpy, and nothing written to
disk. That keeps the addon's zero-external-dependency rule intact.
"""

import array
import math
import random

import bpy
from .. import dispatcher

# A 4K buffer is 67 million floats. Cap well below that: these are stamped
# detail maps, not photographs, and the cost is quadratic in size.
MAX_RASTER_SIZE = 2048
MAX_RASTER_COUNT = 512
MAX_RASTER_SEED = 2**31 - 1

# Exactly RGBA. Enforced here rather than trusted from the tool layer: the
# canvas allocation scales with this length, so it is the one field where a
# wrong size turns into an out-of-memory rather than a wrong colour.
RASTER_COLOR_COMPONENTS = 4


def _validate_color(color, name: str) -> list[float]:
    """Validate an RGBA colour arriving over the socket."""
    if not isinstance(color, (list, tuple)):
        raise ValueError(f"{name} must be a list of {RASTER_COLOR_COMPONENTS} numbers")
    if len(color) != RASTER_COLOR_COMPONENTS:
        raise ValueError(
            f"{name} must have exactly {RASTER_COLOR_COMPONENTS} components, "
            f"got {len(color)}"
        )
    for i, component in enumerate(color):
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            raise ValueError(f"{name} component {i} must be a number")
        if component != component or component in (float("inf"), float("-inf")):
            raise ValueError(f"{name} component {i} must be finite")
        if not 0.0 <= component <= 1.0:
            raise ValueError(f"{name} component {i} must be between 0.0 and 1.0")
    return [float(c) for c in color]


class _Canvas:
    """A flat RGBA float buffer with origin at bottom-left, as Blender wants."""

    def __init__(self, size, background):
        self.size = size
        self.data = array.array("f", list(background) * (size * size))

    def _offset(self, x, y):
        return (y * self.size + x) * 4

    def point(self, x, y, color):
        """Set one pixel, ignoring anything outside the canvas."""
        if 0 <= x < self.size and 0 <= y < self.size:
            i = self._offset(x, y)
            self.data[i:i + 4] = array.array("f", color)

    def line(self, x1, y1, x2, y2, color, jitter=0, rng=None):
        """Draw a straight line by walking the longer axis.

        Jitter nudges each step sideways so strokes look carved by hand
        rather than plotted, which is what sells a rune as a rune.
        """
        steps = max(abs(x2 - x1), abs(y2 - y1))
        if steps == 0:
            self.point(x1, y1, color)
            return
        for step in range(steps + 1):
            t = step / steps
            x = int(round(x1 + (x2 - x1) * t))
            y = int(round(y1 + (y2 - y1) * t))
            if jitter and rng is not None:
                x += rng.randint(-jitter, jitter)
                y += rng.randint(-jitter, jitter)
            self.point(x, y, color)


def _draw_runes(canvas, params, rng):
    """Stamp angular glyphs at random positions.

    Each glyph is a few connected strokes radiating from a centre, which
    reads as carved script without needing a real alphabet.
    """
    size = canvas.size
    color = tuple(params["foreground"])
    count = params["count"]
    margin = max(4, size // 16)

    for _ in range(count):
        cx = rng.randint(margin, max(margin, size - margin))
        cy = rng.randint(margin, max(margin, size - margin))
        extent = rng.randint(max(2, size // 24), max(3, size // 10))
        heading = rng.uniform(0.0, 2.0 * math.pi)

        for _ in range(rng.randint(3, 5)):
            spread = rng.uniform(-0.6, 0.6)
            reach = rng.uniform(0.5, 1.4)
            x1 = int(cx + math.cos(heading + spread) * extent)
            y1 = int(cy + math.sin(heading + spread) * extent)
            x2 = int(cx + math.cos(heading - spread) * extent * reach)
            y2 = int(cy + math.sin(heading - spread) * extent * reach)
            canvas.line(x1, y1, x2, y2, color, jitter=1, rng=rng)


RASTER_PATTERNS = {
    "runes": _draw_runes,
}


def handle_create_raster_texture(params: dict) -> dict:
    """Generate an image texture and pack it into the blend file."""
    image = None
    try:
        pattern = params["pattern"]
        draw = RASTER_PATTERNS.get(pattern)
        if draw is None:
            raise ValueError(
                f"Unknown raster pattern '{pattern}'. "
                f"Available: {sorted(RASTER_PATTERNS)}"
            )

        size = params["size"]
        if not isinstance(size, int) or isinstance(size, bool):
            raise ValueError("size must be an integer")
        if not 1 <= size <= MAX_RASTER_SIZE:
            raise ValueError(f"size must be 1-{MAX_RASTER_SIZE}, got {size}")

        count = params.get("count", 12)
        if not isinstance(count, int) or isinstance(count, bool):
            raise ValueError("count must be an integer")
        if not 0 <= count <= MAX_RASTER_COUNT:
            raise ValueError(f"count must be 0-{MAX_RASTER_COUNT}, got {count}")

        # Colours are validated here, not only in the MCP tool layer. The
        # canvas buffer is len(background) * size * size, so an over-long
        # background multiplies the allocation: a 10000-element list at the
        # maximum size asks for 167 GB on Blender's main thread and freezes
        # the application. Any local process can reach this socket, so the
        # length check has to live on this side of it.
        foreground = _validate_color(params.get("foreground"), "foreground")
        background = _validate_color(params.get("background"), "background")

        seed = params.get("seed", 0)
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError("seed must be an integer")
        if not 0 <= seed <= MAX_RASTER_SEED:
            raise ValueError(f"seed must be 0-{MAX_RASTER_SEED}, got {seed}")

        # A private Random keeps generation reproducible via seed without
        # reseeding the global RNG, which would make unrelated code in
        # Blender suddenly deterministic.
        rng = random.Random(seed)

        canvas = _Canvas(size, background)
        draw(canvas, {**params, "count": count, "foreground": foreground}, rng)

        image = bpy.data.images.new(params["name"], size, size, alpha=True)
        # Colorspace MUST be set before the pixels are written. Changing it
        # invalidates the image buffer, so doing it afterwards silently wipes
        # everything back to black and leaves pack() with nothing to store.
        # Pattern data, not a photograph; sRGB would shift the values.
        image.colorspace_settings.name = "Non-Color"
        image.pixels.foreach_set(canvas.data)
        image.update()
        image.pack()

        return {
            "image": image.name,
            "pattern": pattern,
            "size": size,
            "count": count,
            "packed": True,
        }
    except Exception as e:
        # Do not leave a half-written image datablock behind on failure.
        if image is not None:
            try:
                bpy.data.images.remove(image)
            except Exception:
                pass
        raise RuntimeError(f"Failed to create raster texture: {e}") from e


def register():
    """Register raster texture handlers with the dispatcher."""
    dispatcher.register_handler("create_raster_texture", handle_create_raster_texture)
