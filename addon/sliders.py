"""Which custom properties of an object show as sliders. No bpy here."""

import re

# Keys that can be drawn as obj["key"] without escaping
_SAFE_KEY = re.compile(r"^[A-Za-z0-9_ .\-]{1,63}$")


def slider_keys(items):
    """Names of plain number properties, sorted; skips _private ones, flags,
    text, arrays and groups."""
    return sorted(
        key for key, value in items
        if not key.startswith("_") and _SAFE_KEY.match(key)
        and isinstance(value, (int, float)) and not isinstance(value, bool)
    )
