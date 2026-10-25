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


class TestSelectByAxisFlushes:
    def _quad_strip(self):
        from types import SimpleNamespace as NS

        # Two quads side by side along X: verts 0-5, x = -1, 0, 1
        co = [(-1, 0, 0), (0, 0, 0), (1, 0, 0), (-1, 1, 0), (0, 1, 0), (1, 1, 0)]
        verts = [NS(index=i, co=c, select=False) for i, c in enumerate(co)]
        edges = [NS(vertices=v, select=False) for v in
                 ((0, 1), (1, 2), (3, 4), (4, 5), (0, 3), (1, 4), (2, 5))]
        faces = [NS(vertices=(0, 1, 4, 3), select=False),
                 NS(vertices=(1, 2, 5, 4), select=False)]
        return NS(name="Strip", type="MESH", mode="OBJECT",
                  data=NS(vertices=verts, edges=edges, polygons=faces))

    def test_faces_on_the_side_are_selected(self, monkeypatch):

        mod = _load_selection_handler()
        obj = self._quad_strip()
        monkeypatch.setattr(mod, "_get_mesh", lambda name: obj)
        monkeypatch.setattr(mod, "_activate", lambda o: None)
        result = mod.handle_select_by_axis({"object_name": "Strip", "axis": "X",
                                            "sign": "NEG"})
        assert [v.select for v in obj.data.vertices] == [True, True, False, True, True, False]
        assert [f.select for f in obj.data.polygons] == [True, False]
        assert result["faces"]["selected"] == 1

    def test_extend_keeps_existing(self, monkeypatch):
        mod = _load_selection_handler()
        obj = self._quad_strip()
        obj.data.vertices[2].select = True
        monkeypatch.setattr(mod, "_get_mesh", lambda name: obj)
        monkeypatch.setattr(mod, "_activate", lambda o: None)
        mod.handle_select_by_axis({"object_name": "Strip", "axis": "X", "sign": "NEG",
                                   "extend": True})
        assert obj.data.vertices[2].select is True


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
