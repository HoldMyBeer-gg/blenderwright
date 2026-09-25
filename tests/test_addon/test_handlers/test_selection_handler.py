"""Handler tests for sub-object selection.

Three things here were found only by running the operators against a live
Blender 5.1, not by reading the API:

  select_axis compares against the *active* element, and an element becomes
  active through the bmesh select_history, not by setting its select flag.
  Without that it warns "requires an active vertex" and selects nothing.

  The result of select_axis lands on vertices. Without select_flush, a caller
  asking for "the top" gets 9 vertices and 0 faces.

  select_by_index must set the select mode to match the element, or Blender
  remaps the flags on the next mode switch.
"""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


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


class TestSelectByAxisUsesSelectHistory:
    def test_the_seed_is_added_to_select_history(self):
        """Setting .select is not enough; select_axis needs an active element."""
        source = open(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                   "addon", "handlers", "selection.py")).read()
        assert "select_history.add" in source, (
            "select_axis warns 'requires an active vertex' without this"
        )

    def test_the_selection_is_flushed_to_faces(self):
        source = open(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                   "addon", "handlers", "selection.py")).read()
        assert "select_flush" in source, (
            "select_axis lands on vertices; without a flush a caller asking "
            "for the top sees 0 faces selected"
        )

    def test_negative_sign_seeds_from_the_other_end(self):
        """A NEG selection seeded from the most positive vertex selects nothing."""
        source = open(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                   "addon", "handlers", "selection.py")).read()
        assert "direction = -1 if sign == \"NEG\" else 1" in source


class TestSelectByIndexSetsTheMode:
    def test_select_mode_matches_the_element(self):
        """Otherwise Blender remaps the flags on the next mode switch."""
        source = open(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                   "addon", "handlers", "selection.py")).read()
        assert "_SELECT_MODE" in source and "select_mode(type=_SELECT_MODE" in source

    def test_out_of_range_index_names_the_limit(self):
        mod = _load_selection_handler()
        bpy = sys.modules["bpy"]
        obj = MagicMock()
        obj.name = "Cube"
        obj.type = "MESH"
        obj.data.polygons = [MagicMock() for _ in range(6)]
        bpy.data.objects.get.return_value = obj
        with pytest.raises(ValueError) as exc:
            mod.handle_select_by_index({"object_name": "Cube", "element": "FACE",
                                        "indices": [0, 99]})
        assert "99" in str(exc.value) and "6" in str(exc.value)


class TestLoopSelectIsAbsent:
    def test_no_loop_select_handler(self):
        """It needs a view3d region; over a socket it always fails."""
        mod = _load_selection_handler()
        assert not any("loop" in name for name in dir(mod))
