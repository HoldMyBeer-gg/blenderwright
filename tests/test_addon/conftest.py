"""Mock bpy module for addon tests."""

import sys
from unittest.mock import MagicMock

# Create mock bpy module before any addon imports
mock_bpy = MagicMock()
mock_bpy.app.timers.is_registered = MagicMock(return_value=False)
mock_bpy.app.timers.register = MagicMock()
mock_bpy.app.timers.unregister = MagicMock()
sys.modules["bpy"] = mock_bpy
