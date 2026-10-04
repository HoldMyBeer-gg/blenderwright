"""Mock bpy module for addon tests."""

import sys
from unittest.mock import MagicMock

# Create mock bpy module before any addon imports
mock_bpy = MagicMock()
mock_bpy.app.timers.is_registered = MagicMock(return_value=False)
mock_bpy.app.timers.register = MagicMock()
mock_bpy.app.timers.unregister = MagicMock()
sys.modules["bpy"] = mock_bpy


class _Vector(tuple):
    """Enough of mathutils.Vector for handlers that build and transform one."""

    def __new__(cls, seq=(0.0, 0.0, 0.0)):
        return super().__new__(cls, tuple(float(v) for v in seq))

    x = property(lambda self: self[0])
    y = property(lambda self: self[1])
    z = property(lambda self: self[2])


if "mathutils" not in sys.modules:
    mock_mathutils = MagicMock()
    mock_mathutils.Vector = _Vector
    sys.modules["mathutils"] = mock_mathutils
