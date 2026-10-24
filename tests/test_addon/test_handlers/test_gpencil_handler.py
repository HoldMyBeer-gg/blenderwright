"""Unit tests for annotation handler (Blender 5.x Annotation API)."""

import sys
import os
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_gpencil_handler():
    """Load addon.handlers.gpencil directly without triggering addon/handlers/__init__.py."""
    mock_dispatcher = MagicMock()
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "gpencil.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.gpencil", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.gpencil"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def gpencil_handler():
    """Provide loaded gpencil handler module."""
    return _load_gpencil_handler()


class TestHandleCreateAnnotation:
    def test_handle_create_annotation(self, gpencil_handler):
        """Handler calls bpy.data.annotations.new(name) and returns annotation name."""
        import bpy

        mock_ann = MagicMock()
        mock_ann.name = "TestAnnotation"
        bpy.data.annotations.new.return_value = mock_ann

        result = gpencil_handler.handle_create_annotation({"name": "TestAnnotation"})

        bpy.data.annotations.new.assert_called_with("TestAnnotation")
        assert result["name"] == "TestAnnotation"

    def test_handle_create_annotation_default_name(self, gpencil_handler):
        """Handler uses default name when none provided."""
        import bpy

        mock_ann = MagicMock()
        mock_ann.name = "Annotation"
        bpy.data.annotations.new.return_value = mock_ann

        result = gpencil_handler.handle_create_annotation({})

        bpy.data.annotations.new.assert_called_with("Annotation")
        assert "name" in result


class TestHandleAddAnnotationLayer:
    def test_handle_add_annotation_layer(self, gpencil_handler):
        """Handler accesses annotation data and calls layers.new(name=layer_name)."""
        import bpy

        mock_layer = MagicMock()
        mock_layer.info = "Layer1"
        mock_ann = MagicMock()
        mock_ann.name = "TestAnnotation"
        mock_ann.layers.new.return_value = mock_layer
        bpy.data.annotations.get.return_value = mock_ann

        result = gpencil_handler.handle_add_annotation_layer({
            "annotation_name": "TestAnnotation",
            "layer_name": "Layer1",
        })

        bpy.data.annotations.get.assert_called_with("TestAnnotation")
        mock_ann.layers.new.assert_called_with(name="Layer1")
        assert result["annotation"] == "TestAnnotation"
        assert result["layer"] == "Layer1"

    def test_handle_add_annotation_layer_not_found(self, gpencil_handler):
        """Handler raises ValueError when annotation not found."""
        import bpy

        bpy.data.annotations.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            gpencil_handler.handle_add_annotation_layer({
                "annotation_name": "Missing",
                "layer_name": "Layer1",
            })


class TestHandleRemoveAnnotationLayer:
    def test_handle_remove_annotation_layer(self, gpencil_handler):
        """Handler removes named layer from annotation data."""
        import bpy

        mock_layer = MagicMock()
        mock_ann = MagicMock()
        mock_ann.name = "TestAnnotation"
        mock_ann.layers.get.return_value = mock_layer
        bpy.data.annotations.get.return_value = mock_ann

        result = gpencil_handler.handle_remove_annotation_layer({
            "annotation_name": "TestAnnotation",
            "layer_name": "Layer1",
        })

        mock_ann.layers.remove.assert_called_with(mock_layer)
        assert result["removed_layer"] == "Layer1"

    def test_handle_remove_annotation_layer_not_found(self, gpencil_handler):
        """Handler raises ValueError when layer not found."""
        import bpy

        mock_ann = MagicMock()
        mock_ann.name = "TestAnnotation"
        mock_ann.layers.get.return_value = None
        bpy.data.annotations.get.return_value = mock_ann

        with pytest.raises(ValueError, match="not found"):
            gpencil_handler.handle_remove_annotation_layer({
                "annotation_name": "TestAnnotation",
                "layer_name": "Missing",
            })


class TestHandleAddAnnotationStroke:
    def test_handle_add_annotation_stroke(self, gpencil_handler):
        """Handler creates stroke on frame, sets co and pressure. Does NOT set .strength."""
        import bpy

        mock_point_0 = MagicMock(spec=["co", "pressure"])
        mock_point_1 = MagicMock(spec=["co", "pressure"])
        mock_stroke = MagicMock()

        def getitem(i):
            return [mock_point_0, mock_point_1][i]

        mock_stroke.points.__getitem__.side_effect = getitem

        mock_frame = MagicMock()
        mock_frame.strokes.new.return_value = mock_stroke

        mock_layer = MagicMock()
        mock_layer.info = "Layer1"
        mock_layer.frames = [mock_frame]

        mock_ann = MagicMock()
        mock_ann.name = "TestAnnotation"
        mock_ann.layers.get.return_value = mock_layer
        bpy.data.annotations.get.return_value = mock_ann
        bpy.context.scene.frame_current = 1

        points = [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0]]
        result = gpencil_handler.handle_add_annotation_stroke({
            "annotation_name": "TestAnnotation",
            "layer_name": "Layer1",
            "points": points,
            "pressure": 0.8,
        })

        assert result["point_count"] == 2
        assert result["annotation"] == "TestAnnotation"

    def test_handle_add_annotation_stroke_no_strength_set(self, gpencil_handler):
        """Verify that the handler does NOT set .strength on stroke points."""
        import inspect

        source = inspect.getsource(gpencil_handler.handle_add_annotation_stroke)
        assert ".strength" not in source, (
            "handle_add_annotation_stroke must not set .strength on points"
        )


class TestNoLegacyGpencilAPI:
    def test_no_gpencil_add_operator(self):
        """Handler file does not contain 'gpencil_add' string (removed in Blender 5.x)."""
        handler_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "addon", "handlers", "gpencil.py",
        )
        with open(handler_path) as f:
            content = f.read()
        assert "gpencil_add" not in content, (
            "Handler must not reference removed bpy.ops.object.gpencil_add"
        )

    def test_no_gpencil_type_check(self):
        """Handler file does not contain old GPENCIL type checks."""
        handler_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "addon", "handlers", "gpencil.py",
        )
        with open(handler_path) as f:
            content = f.read()
        assert 'obj.type != "GPENCIL"' not in content, (
            "Handler must not use obj.type != 'GPENCIL' check"
        )
        assert 'obj.type == "GPENCIL"' not in content, (
            "Handler must not use obj.type == 'GPENCIL' check"
        )


from types import SimpleNamespace  # noqa: E402


class _Points(list):
    pass


class _Drawing:
    def __init__(self):
        self.strokes = []

    def add_strokes(self, sizes):
        for n in sizes:
            self.strokes.append(SimpleNamespace(
                points=_Points(SimpleNamespace(position=None, radius=None) for _ in range(n)),
                cyclic=False, material_index=0))


class _Frames(list):
    def new(self, frame_number):
        f = SimpleNamespace(frame_number=frame_number, drawing=_Drawing())
        self.append(f)
        return f


class _Layers(list):
    active = None

    def new(self, name):
        layer = SimpleNamespace(name=name, frames=_Frames())
        self.append(layer)
        self.active = layer
        return layer

    def get(self, name):
        return next((layer for layer in self if layer.name == name), None)


class _Mats(list):
    def find(self, name):
        return next((i for i, m in enumerate(self) if m.name == name), -1)


@pytest.fixture
def gp_env(monkeypatch):
    import bpy

    objects, mats = {}, {}

    def new_gp(name):
        return SimpleNamespace(name=name, layers=_Layers(), materials=_Mats())

    def new_obj(name, data):
        obj = SimpleNamespace(name=name, data=data, type="GREASEPENCIL", location=None)
        objects[name] = obj
        return obj

    def new_mat(name):
        mats[name] = SimpleNamespace(name=name, grease_pencil=None)
        return mats[name]

    def create_gp_data(mat):
        mat.grease_pencil = SimpleNamespace(color=None, fill_color=None, show_fill=False,
                                            show_stroke=True)

    monkeypatch.setattr(bpy.data, "grease_pencils", SimpleNamespace(new=new_gp))
    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(new=new_obj, get=objects.get))
    monkeypatch.setattr(bpy.data, "materials", SimpleNamespace(
        new=new_mat, get=mats.get, create_gpencil_data=create_gp_data))
    monkeypatch.setattr(bpy.context, "scene", SimpleNamespace(collection=SimpleNamespace(
        objects=SimpleNamespace(link=lambda o: None))))
    return SimpleNamespace(objects=objects, mats=mats)


class TestGreasePencilDrawing:
    def test_create_has_a_layer_and_frame(self, gpencil_handler, gp_env):
        result = gpencil_handler.handle_create_grease_pencil(
            {"name": "Sketch", "location": [0, 0, 1], "layer_name": "Ink"})
        layer = gp_env.objects["Sketch"].data.layers[0]
        assert layer.name == "Ink" and layer.frames[0].frame_number == 1
        assert result["layer"] == "Ink"

    def test_material(self, gpencil_handler, gp_env):
        gpencil_handler.handle_create_gp_material({"name": "Red", "color": [1, 0, 0, 1]})
        assert gp_env.mats["Red"].grease_pencil.color == [1, 0, 0, 1]

    def test_stroke_with_material_and_new_layer(self, gpencil_handler, gp_env):
        gpencil_handler.handle_create_grease_pencil({"name": "Sketch", "location": [0, 0, 0],
                                                     "layer_name": "Ink"})
        gpencil_handler.handle_create_gp_material({"name": "Red", "color": [1, 0, 0, 1]})
        result = gpencil_handler.handle_add_gp_stroke({
            "object_name": "Sketch", "points": [[0, 0, 0], [1, 0, 0], [1, 0, 1]],
            "layer": "Shading", "frame": 5, "radius": [0.01, 0.03, 0.01], "cyclic": True,
            "material": "Red"})
        data = gp_env.objects["Sketch"].data
        layer = data.layers.get("Shading")
        stroke = layer.frames[0].drawing.strokes[0]
        assert layer.frames[0].frame_number == 5
        assert [p.position for p in stroke.points] == [(0, 0, 0), (1, 0, 0), (1, 0, 1)]
        assert [p.radius for p in stroke.points] == [0.01, 0.03, 0.01]
        assert stroke.cyclic is True and data.materials[stroke.material_index].name == "Red"
        assert result["strokes_on_frame"] == 1

    def test_stroke_gets_default_ink_without_materials(self, gpencil_handler, gp_env):
        gpencil_handler.handle_create_grease_pencil({"name": "Sketch", "location": [0, 0, 0],
                                                     "layer_name": "Ink"})
        gpencil_handler.handle_add_gp_stroke({"object_name": "Sketch",
                                              "points": [[0, 0, 0], [1, 0, 0]], "layer": "",
                                              "frame": 1, "radius": [0.02, 0.02],
                                              "cyclic": False, "material": ""})
        assert gp_env.objects["Sketch"].data.materials[0].grease_pencil is not None

    def test_non_gp_material_refused(self, gpencil_handler, gp_env):
        gpencil_handler.handle_create_grease_pencil({"name": "Sketch", "location": [0, 0, 0],
                                                     "layer_name": "Ink"})
        gp_env.mats["Paint"] = SimpleNamespace(name="Paint", grease_pencil=None)
        with pytest.raises(ValueError, match="Paint"):
            gpencil_handler.handle_add_gp_stroke({"object_name": "Sketch",
                                                  "points": [[0, 0, 0], [1, 0, 0]],
                                                  "radius": [0.02, 0.02], "material": "Paint"})

    def test_not_a_grease_pencil(self, gpencil_handler, gp_env):
        gp_env.objects["Cube"] = SimpleNamespace(name="Cube", type="MESH")
        with pytest.raises(ValueError, match="Grease Pencil"):
            gpencil_handler.handle_add_gp_stroke({"object_name": "Cube",
                                                  "points": [[0, 0, 0], [1, 0, 0]],
                                                  "radius": [0.02, 0.02]})


class TestLineartHandler:
    def test_unknown_source(self, gpencil_handler, gp_env):
        with pytest.raises(ValueError):
            gpencil_handler.handle_add_lineart({"source": "WORLD"})

    def test_needs_a_camera(self, gpencil_handler, gp_env, monkeypatch):
        import bpy

        monkeypatch.setattr(bpy.context, "scene", SimpleNamespace(camera=None))
        with pytest.raises(ValueError, match="camera"):
            gpencil_handler.handle_add_lineart({"source": "SCENE"})
