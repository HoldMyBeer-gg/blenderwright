"""Tests for sculpting handler: validates 5.1 API compliance."""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_sculpting_handler():
    """Load addon.handlers.sculpting directly without triggering addon/handlers/__init__.py."""
    mock_dispatcher = MagicMock()
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "sculpting.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.sculpting", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.sculpting"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def sculpting_handler():
    """Provide loaded sculpting handler module."""
    return _load_sculpting_handler()


class TestHandleSetBrushProperty:
    def test_handle_set_brush_property_size(self, sculpting_handler):
        """Setting brush size assigns brush.size as int."""
        import bpy

        brush = MagicMock()
        bpy.context.tool_settings.sculpt.brush = brush
        result = sculpting_handler.handle_set_brush_property({"property": "size", "value": 50})

        assert brush.size == 50
        assert result["property"] == "size"

    def test_handle_set_brush_property_strength(self, sculpting_handler):
        """Setting brush strength assigns brush.strength as float."""
        import bpy

        brush = MagicMock()
        bpy.context.tool_settings.sculpt.brush = brush
        result = sculpting_handler.handle_set_brush_property(
            {"property": "strength", "value": 0.75}
        )

        assert brush.strength == 0.75
        assert result["property"] == "strength"

    def test_handle_set_brush_property_stroke_method_dots(self, sculpting_handler):
        """Setting stroke_method to DOTS assigns brush.stroke_method."""
        import bpy

        brush = MagicMock()
        bpy.context.tool_settings.sculpt.brush = brush
        result = sculpting_handler.handle_set_brush_property(
            {"property": "stroke_method", "value": "DOTS"}
        )

        assert brush.stroke_method == "DOTS"
        assert result["success"] is True

    def test_handle_set_brush_property_stroke_method_invalid(self, sculpting_handler):
        """Setting stroke_method to an invalid value raises ValueError."""
        import bpy

        brush = MagicMock()
        bpy.context.tool_settings.sculpt.brush = brush
        with pytest.raises(ValueError, match="stroke_method"):
            sculpting_handler.handle_set_brush_property(
                {"property": "stroke_method", "value": "INVALID"}
            )

    def test_handle_set_brush_property_unknown(self, sculpting_handler):
        """Setting an unknown brush property raises ValueError."""
        import bpy

        brush = MagicMock()
        bpy.context.tool_settings.sculpt.brush = brush
        with pytest.raises(ValueError, match="Unknown brush property"):
            sculpting_handler.handle_set_brush_property(
                {"property": "nonexistent", "value": 1}
            )


class TestHandleEnterSculptMode:
    def test_handle_enter_sculpt_mode(self, sculpting_handler):
        """Entering sculpt mode calls mode_set with SCULPT."""
        import bpy

        mock_obj = MagicMock()
        mock_obj.type = "MESH"
        mock_obj.name = "Cube"
        mock_obj.mode = "OBJECT"
        bpy.data.objects.get = MagicMock(return_value=mock_obj)

        result = sculpting_handler.handle_enter_sculpt_mode({"object_name": "Cube"})

        bpy.ops.object.mode_set.assert_called_with(mode="SCULPT")
        assert result["mode"] == "SCULPT"
        assert result["success"] is True


class TestRemeshVoxelBudget:
    """voxel_size is bounded 0.001-10.0 with no relation to object size.

    0.001 on a 2m object is a 2000^3 grid. Blender stops responding, the
    caller's socket burns all 150 retries (about five minutes) and the call
    dies with a timeout that says nothing about why. The only layer that can
    judge this is the handler, which knows the object's dimensions.
    """

    def _obj(self, dims):
        obj = MagicMock()
        obj.name = "Thing"
        obj.type = "MESH"
        obj.mode = "OBJECT"
        obj.dimensions = dims
        return obj

    def test_absurd_grid_is_refused_before_blender_sees_it(self):
        mod = _load_sculpting_handler()
        bpy = sys.modules["bpy"]
        bpy.data.objects.get.return_value = self._obj((2.0, 2.0, 2.0))
        with pytest.raises(ValueError) as exc:
            mod.handle_remesh({"object_name": "Thing", "voxel_size": 0.001,
                               "mode": "VOXEL"})
        message = str(exc.value)
        assert "voxel" in message.lower()
        assert "0.0" in message, "the error should suggest a workable size"

    def test_a_sane_voxel_size_is_allowed(self):
        mod = _load_sculpting_handler()
        bpy = sys.modules["bpy"]
        bpy.data.objects.get.return_value = self._obj((2.0, 2.0, 2.0))
        mod.handle_remesh({"object_name": "Thing", "voxel_size": 0.05,
                           "mode": "VOXEL"})

    def test_budget_scales_with_the_object(self):
        """0.05 is fine on a 2m object and absurd on a 200m one."""
        mod = _load_sculpting_handler()
        bpy = sys.modules["bpy"]
        bpy.data.objects.get.return_value = self._obj((200.0, 200.0, 200.0))
        with pytest.raises(ValueError):
            mod.handle_remesh({"object_name": "Thing", "voxel_size": 0.05,
                               "mode": "VOXEL"})

    def test_non_voxel_modes_do_not_apply_the_budget(self):
        """SHARP/SMOOTH/BLOCKS ignore voxel_size entirely."""
        mod = _load_sculpting_handler()
        bpy = sys.modules["bpy"]
        bpy.data.objects.get.return_value = self._obj((2.0, 2.0, 2.0))
        mod.handle_remesh({"object_name": "Thing", "voxel_size": 0.001,
                           "mode": "SHARP"})

    def test_result_says_voxel_size_was_ignored_for_other_modes(self):
        """It previously reported success as though it had been used."""
        mod = _load_sculpting_handler()
        bpy = sys.modules["bpy"]
        bpy.data.objects.get.return_value = self._obj((2.0, 2.0, 2.0))
        result = mod.handle_remesh({"object_name": "Thing", "voxel_size": 0.001,
                                    "mode": "SHARP"})
        assert result.get("voxel_size") is None


class TestHandleSetSculptBrush:
    """Since 4.3 sculpt brushes are Essentials assets, not builtin_brush tools."""

    @pytest.mark.parametrize("brush_type, asset_name", [
        ("DRAW", "Draw"),
        ("CLAY_STRIPS", "Clay Strips"),
        ("INFLATE", "Inflate/Deflate"),
        ("CREASE", "Crease Polish"),
        ("MULTIRES_DISPLACEMENT_SMEAR", "Smear Multires Displacement"),
    ])
    def test_activates_the_essentials_asset(self, sculpting_handler, brush_type, asset_name):
        import bpy

        bpy.ops.brush.asset_activate.reset_mock()
        bpy.ops.brush.asset_activate.return_value = {"FINISHED"}
        sculpting_handler.handle_set_sculpt_brush({"brush_type": brush_type})

        bpy.ops.brush.asset_activate.assert_called_once_with(
            asset_library_type="ESSENTIALS",
            relative_asset_identifier=(
                f"brushes/essentials_brushes-mesh_sculpt.blend/Brush/{asset_name}"
            ),
        )

    def test_does_not_use_removed_builtin_brush_tools(self, sculpting_handler):
        import bpy

        bpy.ops.wm.tool_set_by_id.reset_mock()
        bpy.ops.brush.asset_activate.return_value = {"FINISHED"}
        sculpting_handler.handle_set_sculpt_brush({"brush_type": "GRAB"})

        for call in bpy.ops.wm.tool_set_by_id.call_args_list:
            assert not call.kwargs.get("name", "").startswith("builtin_brush.")

    def test_unknown_brush_is_rejected(self, sculpting_handler):
        with pytest.raises(ValueError):
            sculpting_handler.handle_set_sculpt_brush({"brush_type": "LASER"})

    def test_failed_activation_raises(self, sculpting_handler):
        import bpy

        bpy.ops.brush.asset_activate.return_value = {"CANCELLED"}
        with pytest.raises(RuntimeError):
            sculpting_handler.handle_set_sculpt_brush({"brush_type": "DRAW"})


from types import SimpleNamespace  # noqa: E402


class _Attributes(dict):
    def __init__(self, mesh):
        super().__init__()
        self._mesh = mesh

    def new(self, name, type, domain):
        size = len(self._mesh.vertices) if domain == "POINT" else len(self._mesh.polygons)
        attr = SimpleNamespace(name=name, data_type=type, domain=domain,
                               data=[SimpleNamespace(value=0.0 if type == "FLOAT" else 0)
                                     for _ in range(size)])
        self[name] = attr
        return attr

    def remove(self, attr):
        del self[attr.name]


def _two_part_mesh():
    """Faces 0-1 share vertices (one part); face 2 stands alone."""
    groups = {0: [SimpleNamespace(group=0, weight=0.25)], 1: [], 2: [],
              3: [SimpleNamespace(group=0, weight=1.0)], 4: [], 5: [], 6: []}
    verts = [SimpleNamespace(index=i, groups=groups.get(i, [])) for i in range(7)]
    polys = [SimpleNamespace(index=0, vertices=[0, 1, 2], material_index=0),
             SimpleNamespace(index=1, vertices=[1, 2, 3], material_index=1),
             SimpleNamespace(index=2, vertices=[4, 5, 6], material_index=1)]
    mesh = SimpleNamespace(vertices=verts, polygons=polys)
    mesh.attributes = _Attributes(mesh)
    vgroups = {"Ears": SimpleNamespace(name="Ears", index=0)}
    return SimpleNamespace(name="Head", type="MESH", mode="OBJECT", data=mesh,
                           vertex_groups=vgroups)


@pytest.fixture
def head(sculpting_handler, monkeypatch):
    import bpy

    obj = _two_part_mesh()
    monkeypatch.setattr(bpy.data, "objects", {"Head": obj})
    return sculpting_handler, obj


def _mask(obj):
    return [round(d.value, 3) for d in obj.data.attributes[".sculpt_mask"].data]


def _sets(obj):
    return [d.value for d in obj.data.attributes[".sculpt_face_set"].data]


class TestSculptMaskHandler:
    def test_mask_all(self, head):
        h, obj = head
        result = h.handle_set_sculpt_mask({"object_name": "Head", "value": 1.0})
        assert _mask(obj) == [1.0] * 7 and result["masked"] == 7

    def test_vertices_keep_the_rest(self, head):
        h, obj = head
        h.handle_set_sculpt_mask({"object_name": "Head", "value": 1.0})
        h.handle_set_sculpt_mask({"object_name": "Head", "value": 0.0, "vertex_indices": [1]})
        assert _mask(obj) == [1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0]

    def test_vertex_group_weights_scale_the_value(self, head):
        h, obj = head
        h.handle_set_sculpt_mask({"object_name": "Head", "value": 1.0, "vertex_group": "Ears"})
        assert _mask(obj) == [0.25, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]

    def test_invert(self, head):
        h, obj = head
        h.handle_set_sculpt_mask({"object_name": "Head", "value": 1.0, "vertex_indices": [0]})
        h.handle_set_sculpt_mask({"object_name": "Head", "invert": True})
        assert _mask(obj) == [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]

    def test_clear_removes_the_mask(self, head):
        h, obj = head
        h.handle_set_sculpt_mask({"object_name": "Head", "value": 1.0})
        h.handle_set_sculpt_mask({"object_name": "Head", "clear": True})
        assert ".sculpt_mask" not in obj.data.attributes

    def test_bad_vertex(self, head):
        h, _ = head
        with pytest.raises(ValueError, match="out of range"):
            h.handle_set_sculpt_mask({"object_name": "Head", "value": 1.0,
                                      "vertex_indices": [7]})

    def test_missing_group(self, head):
        h, _ = head
        with pytest.raises(ValueError, match="Nose"):
            h.handle_set_sculpt_mask({"object_name": "Head", "value": 1.0,
                                      "vertex_group": "Nose"})

    def test_sculpt_mode_is_left_and_restored(self, head, monkeypatch):
        import bpy

        h, obj = head
        obj.mode = "SCULPT"
        modes = []

        def mode_set(mode):
            modes.append(mode)
            obj.mode = mode

        monkeypatch.setattr(bpy.ops.object, "mode_set", mode_set)
        monkeypatch.setattr(h, "_select_only", lambda o: None, raising=False)
        h.handle_set_sculpt_mask({"object_name": "Head", "value": 1.0})
        assert modes == ["OBJECT", "SCULPT"]


class TestFaceSetsHandler:
    def test_loose_parts(self, head):
        h, obj = head
        result = h.handle_set_face_sets({"object_name": "Head", "mode": "LOOSE_PARTS"})
        assert _sets(obj) == [1, 1, 2] and result["face_sets"] == 2

    def test_materials(self, head):
        h, obj = head
        h.handle_set_face_sets({"object_name": "Head", "mode": "MATERIALS"})
        assert _sets(obj) == [1, 2, 2]

    def test_assign_keeps_others(self, head):
        h, obj = head
        h.handle_set_face_sets({"object_name": "Head", "mode": "LOOSE_PARTS"})
        h.handle_set_face_sets({"object_name": "Head", "mode": "ASSIGN",
                                "face_indices": [0], "face_set": 7})
        assert _sets(obj) == [7, 1, 2]

    def test_bad_face(self, head):
        h, _ = head
        with pytest.raises(ValueError, match="out of range"):
            h.handle_set_face_sets({"object_name": "Head", "mode": "ASSIGN",
                                    "face_indices": [3], "face_set": 1})

    def test_clear(self, head):
        h, obj = head
        h.handle_set_face_sets({"object_name": "Head", "mode": "LOOSE_PARTS"})
        h.handle_set_face_sets({"object_name": "Head", "mode": "CLEAR"})
        assert ".sculpt_face_set" not in obj.data.attributes
