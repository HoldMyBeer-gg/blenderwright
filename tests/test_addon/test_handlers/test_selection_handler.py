"""Handler tests for sub-object selection.

select_by_axis splits at the middle of the bounding box and sets the flags
itself, flushing vertices up to edges and faces.

select_by_index must set the select mode to match the element, or Blender
  remaps the flags on the next mode switch.
"""

import os
import sys
import importlib.util
from unittest.mock import MagicMock


def _load_selection_handler():
    mock_dispatcher = MagicMock()
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher
    sys.modules.setdefault("bmesh", MagicMock())

    path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "addon", "handlers", "selection.py")
    spec = importlib.util.spec_from_file_location("addon.handlers.selection", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.selection"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestSideOfAxis:
    """Split at the middle of the bounding box. The old version seeded
    select_axis with the most extreme vertex, which on a cube gave the top
    face but on Suzanne gave 1 vertex of 507 for "the left half"."""

    def test_negative_half_of_an_organic_shape(self):
        mod = _load_selection_handler()
        xs = [-1.3, -0.9, -0.4, 0.0, 0.4, 0.9, 1.3]
        assert mod._on_side(xs, "NEG") == [True, True, True, True, False, False, False]

    def test_positive_half_includes_the_middle_seam(self):
        mod = _load_selection_handler()
        assert mod._on_side([-1.0, 0.0, 1.0], "POS") == [False, True, True]

    def test_cube_top_is_the_top_face(self):
        mod = _load_selection_handler()
        zs = [-1.0, -1.0, 1.0, 1.0]
        assert mod._on_side(zs, "POS") == [False, False, True, True]

    def test_off_centre_object_uses_its_own_middle(self):
        mod = _load_selection_handler()
        assert mod._on_side([10.0, 11.0, 12.0], "NEG") == [True, True, False]

    def test_align_is_the_middle_plane(self):
        mod = _load_selection_handler()
        assert mod._on_side([-1.0, 0.0, 0.0, 1.0], "ALIGN") == [False, True, True, False]

    def test_flat_mesh_is_all_aligned(self):
        mod = _load_selection_handler()
        assert mod._on_side([2.0, 2.0], "ALIGN") == [True, True]
        assert mod._on_side([2.0, 2.0], "POS") == [True, True]
