"""Tests for the vertex group and shape key handler against small fakes."""

import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load_handler():
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = MagicMock()
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "addon", "handlers", "deform.py")
    spec = importlib.util.spec_from_file_location("addon.handlers.deform", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.deform"] = mod
    spec.loader.exec_module(mod)
    return mod


class VertexGroup:
    def __init__(self, groups, name, index):
        self._groups, self.name, self.index = groups, name, index
        self.weights = {}

    def add(self, indices, weight, mode):
        for i in indices:
            current = self.weights.get(i, 0.0)
            self.weights[i] = {"REPLACE": weight, "ADD": min(1.0, current + weight),
                               "SUBTRACT": max(0.0, current - weight)}[mode]

    def remove(self, indices):
        for i in indices:
            self.weights.pop(i, None)

    def weight(self, i):
        if i not in self.weights:
            raise RuntimeError("Error: Vertex not in group")
        return self.weights[i]


class VertexGroups(list):
    active_index = 0

    def new(self, name):
        vg = VertexGroup(self, name, len(self))
        self.append(vg)
        return vg

    def get(self, name):
        return next((g for g in self if g.name == name), None)

    def remove(self, vg):
        super().remove(vg)


class KeyBlocks(list):
    def get(self, name):
        return next((k for k in self if k.name == name), None)


def _mesh(n=4):
    verts = [SimpleNamespace(index=i, co=[float(i), 0.0, 0.0], select=(i % 2 == 0))
             for i in range(n)]
    obj = SimpleNamespace(name="Face", type="MESH", mode="OBJECT",
                          vertex_groups=VertexGroups(),
                          data=SimpleNamespace(vertices=verts, shape_keys=None))

    def shape_key_add(name, from_mix=False):
        if obj.data.shape_keys is None:
            obj.data.shape_keys = SimpleNamespace(key_blocks=KeyBlocks(), reference_key=None,
                                                  use_relative=True)
        kb = SimpleNamespace(name=name, value=0.0, slider_min=0.0, slider_max=1.0, mute=False,
                             vertex_group="", relative_key=None,
                             data=[SimpleNamespace(co=list(v.co)) for v in verts],
                             keyframe_insert=MagicMock(return_value=True))
        blocks = obj.data.shape_keys.key_blocks
        if not blocks:
            obj.data.shape_keys.reference_key = kb
        kb.relative_key = obj.data.shape_keys.reference_key
        blocks.append(kb)
        return kb

    def shape_key_remove(kb):
        obj.data.shape_keys.key_blocks.remove(kb)

    obj.shape_key_add = shape_key_add
    obj.shape_key_remove = shape_key_remove
    return obj


@pytest.fixture
def obj(monkeypatch):
    import bpy

    o = _mesh()
    monkeypatch.setattr(bpy.data, "objects", SimpleNamespace(get=lambda n: o if n == "Face" else None))
    return o


@pytest.fixture
def h(obj):
    return _load_handler()


class TestAssignVertexGroup:
    def test_creates_the_group_and_assigns_indices(self, h, obj):
        result = h.handle_assign_vertex_group({"object_name": "Face", "group_name": "Mouth",
                                               "vertex_indices": [1, 2], "weight": 0.5,
                                               "mode": "REPLACE"})
        vg = obj.vertex_groups.get("Mouth")
        assert vg.weights == {1: 0.5, 2: 0.5}
        assert result["changed"] == 2

    def test_all_and_current_selection(self, h, obj):
        h.handle_assign_vertex_group({"object_name": "Face", "group_name": "All",
                                      "selection": "ALL"})
        assert set(obj.vertex_groups.get("All").weights) == {0, 1, 2, 3}
        h.handle_assign_vertex_group({"object_name": "Face", "group_name": "Sel",
                                      "selection": "CURRENT"})
        assert set(obj.vertex_groups.get("Sel").weights) == {0, 2}

    def test_remove_mode(self, h, obj):
        h.handle_assign_vertex_group({"object_name": "Face", "group_name": "G",
                                      "selection": "ALL"})
        h.handle_assign_vertex_group({"object_name": "Face", "group_name": "G",
                                      "vertex_indices": [0], "mode": "REMOVE"})
        assert set(obj.vertex_groups.get("G").weights) == {1, 2, 3}

    def test_index_past_the_mesh_is_refused(self, h, obj):
        with pytest.raises(ValueError, match="3"):
            h.handle_assign_vertex_group({"object_name": "Face", "group_name": "G",
                                          "vertex_indices": [9]})

    def test_unknown_mode_refused_at_the_handler(self, h, obj):
        with pytest.raises(ValueError):
            h.handle_assign_vertex_group({"object_name": "Face", "group_name": "G",
                                          "mode": "__class__"})

    def test_list_reports_counts_and_ranges(self, h, obj):
        h.handle_assign_vertex_group({"object_name": "Face", "group_name": "G",
                                      "vertex_indices": [0, 1], "weight": 0.25})
        groups = h.handle_list_vertex_groups({"object_name": "Face"})["groups"]
        assert groups == [{"name": "G", "index": 0, "vertex_count": 2,
                           "min_weight": 0.25, "max_weight": 0.25}]

    def test_remove_group(self, h, obj):
        h.handle_assign_vertex_group({"object_name": "Face", "group_name": "G"})
        result = h.handle_remove_vertex_group({"object_name": "Face", "group_name": "G"})
        assert obj.vertex_groups.get("G") is None
        assert result["groups"] == []

    def test_missing_group(self, h, obj):
        with pytest.raises(ValueError, match="Nope"):
            h.handle_remove_vertex_group({"object_name": "Face", "group_name": "Nope"})

    def test_missing_object(self, h, obj):
        with pytest.raises(ValueError, match="Ghost"):
            h.handle_list_vertex_groups({"object_name": "Ghost"})


class TestVertexGroupOperation:
    def test_unknown_operation_refused(self, h, obj):
        h.handle_assign_vertex_group({"object_name": "Face", "group_name": "G"})
        with pytest.raises(ValueError):
            h.handle_vertex_group_operation({"object_name": "Face", "group_name": "G",
                                             "operation": "__init__"})

    def test_operation_runs_the_operator_on_the_active_group(self, h, obj, monkeypatch):
        import bpy

        h.handle_assign_vertex_group({"object_name": "Face", "group_name": "A"})
        h.handle_assign_vertex_group({"object_name": "Face", "group_name": "B"})
        called = {}
        monkeypatch.setattr(h, "_activate", lambda o: None)
        monkeypatch.setattr(bpy.ops.object, "vertex_group_levels",
                            lambda **kw: called.update(kw, active=obj.vertex_groups.active_index)
                            or {"FINISHED"}, raising=False)
        h.handle_vertex_group_operation({"object_name": "Face", "group_name": "A",
                                         "operation": "LEVELS", "offset": 0.1, "gain": 2.0})
        assert called == {"offset": 0.1, "gain": 2.0, "group_select_mode": "ACTIVE",
                          "active": 0}


class TestShapeKeys:
    def test_first_key_also_makes_the_basis(self, h, obj):
        result = h.handle_add_shape_key({"object_name": "Face", "key_name": "Smile"})
        assert [k.name for k in obj.data.shape_keys.key_blocks] == ["Basis", "Smile"]
        assert result["keys"] == ["Basis", "Smile"]

    def test_duplicate_name_refused(self, h, obj):
        h.handle_add_shape_key({"object_name": "Face", "key_name": "Smile"})
        with pytest.raises(ValueError, match="Smile"):
            h.handle_add_shape_key({"object_name": "Face", "key_name": "Smile"})

    def test_set_value_and_group(self, h, obj):
        h.handle_add_shape_key({"object_name": "Face", "key_name": "Smile"})
        h.handle_assign_vertex_group({"object_name": "Face", "group_name": "Mouth"})
        h.handle_set_shape_key({"object_name": "Face", "key_name": "Smile", "value": 0.7,
                                "vertex_group": "Mouth"})
        kb = obj.data.shape_keys.key_blocks.get("Smile")
        assert (kb.value, kb.vertex_group) == (0.7, "Mouth")

    def test_value_outside_slider_range_refused(self, h, obj):
        h.handle_add_shape_key({"object_name": "Face", "key_name": "Smile"})
        with pytest.raises(ValueError, match="slider"):
            h.handle_set_shape_key({"object_name": "Face", "key_name": "Smile", "value": 2.0})

    def test_unknown_vertex_group_refused(self, h, obj):
        h.handle_add_shape_key({"object_name": "Face", "key_name": "Smile"})
        with pytest.raises(ValueError, match="Lips"):
            h.handle_set_shape_key({"object_name": "Face", "key_name": "Smile",
                                    "vertex_group": "Lips"})

    def test_move_by_group_weight(self, h, obj):
        h.handle_add_shape_key({"object_name": "Face", "key_name": "Puff"})
        h.handle_assign_vertex_group({"object_name": "Face", "group_name": "Cheeks",
                                      "vertex_indices": [1], "weight": 0.5})
        result = h.handle_move_shape_key_vertices({"object_name": "Face", "key_name": "Puff",
                                                   "offset": [0, 0, 2.0],
                                                   "vertex_group": "Cheeks"})
        kb = obj.data.shape_keys.key_blocks.get("Puff")
        assert kb.data[1].co == [1.0, 0.0, 1.0]
        assert kb.data[0].co == [0.0, 0.0, 0.0]
        assert result["moved"] == 1

    def test_move_by_index_and_whole_mesh(self, h, obj):
        h.handle_add_shape_key({"object_name": "Face", "key_name": "Up"})
        h.handle_move_shape_key_vertices({"object_name": "Face", "key_name": "Up",
                                          "offset": [0, 1, 0], "vertex_indices": [3]})
        kb = obj.data.shape_keys.key_blocks.get("Up")
        assert kb.data[3].co == [3.0, 1.0, 0.0]
        h.handle_move_shape_key_vertices({"object_name": "Face", "key_name": "Up",
                                          "offset": [1, 0, 0]})
        assert [d.co[0] for d in kb.data] == [1.0, 2.0, 3.0, 4.0]

    def test_basis_cannot_be_moved(self, h, obj):
        h.handle_add_shape_key({"object_name": "Face", "key_name": "Smile"})
        # Blender hands back a fresh wrapper on every access, so identity never matches
        obj.data.shape_keys.reference_key = SimpleNamespace(name="Basis")
        with pytest.raises(ValueError, match="Basis"):
            h.handle_move_shape_key_vertices({"object_name": "Face", "key_name": "Basis",
                                              "offset": [0, 0, 1]})

    def test_keyframe(self, h, obj):
        h.handle_add_shape_key({"object_name": "Face", "key_name": "Smile"})
        h.handle_keyframe_shape_key({"object_name": "Face", "key_name": "Smile",
                                     "frame": 12, "value": 1.0})
        kb = obj.data.shape_keys.key_blocks.get("Smile")
        assert kb.value == 1.0
        kb.keyframe_insert.assert_called_once_with("value", frame=12)

    def test_list_and_remove(self, h, obj):
        assert h.handle_list_shape_keys({"object_name": "Face"}) == {"reference": None,
                                                                     "keys": []}
        h.handle_add_shape_key({"object_name": "Face", "key_name": "Smile"})
        listing = h.handle_list_shape_keys({"object_name": "Face"})
        assert listing["reference"] == "Basis"
        assert [k["name"] for k in listing["keys"]] == ["Basis", "Smile"]
        result = h.handle_remove_shape_key({"object_name": "Face", "key_name": "Smile"})
        assert result["keys"] == ["Basis"]

    def test_missing_key(self, h, obj):
        with pytest.raises(ValueError, match="Smile"):
            h.handle_set_shape_key({"object_name": "Face", "key_name": "Smile", "value": 1})


class ColorAttribute:
    def __init__(self, name, data_type, domain, size):
        self.name, self.data_type, self.domain = name, data_type, domain
        self.data = [SimpleNamespace(color=(0.0, 0.0, 0.0, 1.0)) for _ in range(size)]


class ColorAttributes(list):
    def __init__(self, mesh):
        super().__init__()
        self._mesh = mesh
        self.active_color_index = -1
        self.render_color_index = -1

    def new(self, name, type, domain):
        size = len(self._mesh.vertices) if domain == "POINT" else len(self._mesh.loops)
        attr = ColorAttribute(name, type, domain, size)
        self.append(attr)
        return attr

    def get(self, name):
        return next((a for a in self if a.name == name), None)

    @property
    def active_color(self):
        return self[self.active_color_index] if self.active_color_index >= 0 else None

    @active_color.setter
    def active_color(self, attr):
        self.active_color_index = self.index(attr)


@pytest.fixture
def quad():
    """Two triangles over four vertices: loops 0-2 and 3-5."""
    obj = _mesh(4)
    obj.data.loops = [SimpleNamespace(index=i, vertex_index=v)
                      for i, v in enumerate([0, 1, 2, 0, 2, 3])]
    obj.data.color_attributes = ColorAttributes(obj.data)
    return obj


@pytest.fixture
def color_handler(quad, monkeypatch):
    import bpy

    monkeypatch.setattr(bpy.data, "objects", {"Face": quad})
    return _load_handler()


RED = [1.0, 0.0, 0.0, 1.0]
BLACK = (0.0, 0.0, 0.0, 1.0)


def _paint(handler, **extra):
    params = {"object_name": "Face", "color": RED, "attribute_name": "Color",
              "domain": "CORNER", "data_type": "BYTE_COLOR", "selection": "ALL"} | extra
    return handler.handle_paint_color_attribute(params)


class TestPaintColorAttributeHandler:
    def test_creates_paints_all_and_makes_it_render(self, color_handler, quad):
        result = _paint(color_handler)
        attrs = quad.data.color_attributes
        assert [tuple(d.color) for d in attrs[0].data] == [tuple(RED)] * 6
        assert attrs.active_color_index == 0 and attrs.render_color_index == 0
        assert result["created"] is True and result["painted"] == 6

    def test_corner_paints_loops_of_chosen_vertices(self, color_handler, quad):
        _paint(color_handler, vertex_indices=[0])
        colors = [tuple(d.color) for d in quad.data.color_attributes[0].data]
        assert colors == [tuple(RED), BLACK, BLACK, tuple(RED), BLACK, BLACK]

    def test_point_domain_by_selection(self, color_handler, quad):
        _paint(color_handler, domain="POINT", selection="CURRENT")
        colors = [tuple(d.color) for d in quad.data.color_attributes[0].data]
        assert colors == [tuple(RED), BLACK, tuple(RED), BLACK]

    def test_existing_attribute_keeps_its_layout(self, color_handler, quad):
        quad.data.color_attributes.new("Color", "FLOAT_COLOR", "POINT")
        result = _paint(color_handler)
        assert result["created"] is False
        assert (result["domain"], result["data_type"]) == ("POINT", "FLOAT_COLOR")
        assert len(quad.data.color_attributes) == 1

    def test_out_of_range_vertex(self, color_handler):
        with pytest.raises(ValueError):
            _paint(color_handler, vertex_indices=[9])

    def test_remove(self, color_handler, quad):
        quad.data.color_attributes.new("Mask", "BYTE_COLOR", "CORNER")
        result = color_handler.handle_remove_color_attribute(
            {"object_name": "Face", "attribute_name": "Mask"})
        assert result == {"removed": "Mask", "color_attributes": []}

    def test_remove_missing(self, color_handler):
        with pytest.raises(ValueError, match="Mask"):
            color_handler.handle_remove_color_attribute(
                {"object_name": "Face", "attribute_name": "Mask"})

    def test_registered(self, color_handler):
        color_handler.register()
        calls = {c.args[0] for c in color_handler.dispatcher.register_handler.call_args_list}
        assert {"paint_color_attribute", "remove_color_attribute"} <= calls
