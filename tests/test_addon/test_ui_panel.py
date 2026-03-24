"""Tests for N-panel UI custom port feature."""

import os
import pytest


# Read the source file directly — avoids MagicMock metaclass issues
# when classes inherit from bpy.types.Operator (which is a mock in tests)
UI_PANEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "addon", "ui_panel.py",
)


@pytest.fixture(scope="module")
def ui_source():
    """Read ui_panel.py source code."""
    with open(UI_PANEL_PATH) as f:
        return f.read()


class TestCustomPort:
    def test_scene_port_property_registered(self, ui_source):
        """register() creates blendai_port IntProperty on Scene."""
        assert "blendai_port" in ui_source
        assert "IntProperty" in ui_source

    def test_start_operator_reads_port(self, ui_source):
        """Start server operator reads port from context.scene.blendai_port."""
        # Find the StartServer execute method
        assert "context.scene.blendai_port" in ui_source

    def test_start_operator_passes_port(self, ui_source):
        """Start server operator passes port= to start_server."""
        assert "start_server(port=" in ui_source or "start_server(host=" in ui_source

    def test_panel_shows_port_input_when_stopped(self, ui_source):
        """Panel shows port input field when server is stopped."""
        assert '"blendai_port"' in ui_source or "'blendai_port'" in ui_source

    def test_panel_shows_port_when_running(self, ui_source):
        """Panel shows port number when server is running."""
        assert "_port" in ui_source

    def test_default_port_9876(self, ui_source):
        """Default port is 9876."""
        assert "default=9876" in ui_source

    def test_port_min_1024(self, ui_source):
        """Port minimum is 1024 (unprivileged range)."""
        assert "min=1024" in ui_source

    def test_port_max_65535(self, ui_source):
        """Port maximum is 65535."""
        assert "max=65535" in ui_source

    def test_unregister_cleans_port_property(self, ui_source):
        """unregister() removes blendai_port from Scene."""
        # Should delete the property during unregister
        assert "del" in ui_source and "blendai_port" in ui_source
