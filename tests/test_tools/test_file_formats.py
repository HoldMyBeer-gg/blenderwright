"""Import/export formats match what Blender 5.2 actually ships."""

from blenderwright.tools.file_ops import ALLOWED_EXPORT_TYPES, ALLOWED_IMPORT_TYPES
from blenderwright.validators import ALLOWED_EXPORT_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS


class TestRemovedFormats:
    def test_collada_is_gone(self):
        """Blender 5.0 removed Collada import and export."""
        assert ".dae" not in ALLOWED_IMPORT_EXTENSIONS | ALLOWED_EXPORT_EXTENSIONS
        assert "DAE" not in ALLOWED_IMPORT_TYPES | ALLOWED_EXPORT_TYPES

    def test_x3d_is_gone(self):
        """X3D is no longer bundled with Blender."""
        assert ".x3d" not in ALLOWED_IMPORT_EXTENSIONS | ALLOWED_EXPORT_EXTENSIONS
        assert "X3D" not in ALLOWED_IMPORT_TYPES | ALLOWED_EXPORT_TYPES

    def test_svg_is_import_only(self):
        """Blender can import SVG curves but has no SVG curve exporter."""
        assert ".svg" in ALLOWED_IMPORT_EXTENSIONS
        assert "SVG" in ALLOWED_IMPORT_TYPES
        assert ".svg" not in ALLOWED_EXPORT_EXTENSIONS
        assert "SVG" not in ALLOWED_EXPORT_TYPES
