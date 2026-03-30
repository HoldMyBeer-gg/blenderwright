"""Tests for mesh quality analysis handler."""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_mesh_quality_handler():
    """Load addon.handlers.mesh_quality directly without triggering addon/handlers/__init__.py."""
    mock_dispatcher = MagicMock()
    sys.modules.setdefault("addon", MagicMock())
    sys.modules["addon.dispatcher"] = mock_dispatcher

    # Mock bmesh before loading handler
    mock_bmesh = MagicMock()
    sys.modules["bmesh"] = mock_bmesh

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "mesh_quality.py",
    )
    spec = importlib.util.spec_from_file_location("addon.handlers.mesh_quality", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.mesh_quality"] = mod
    spec.loader.exec_module(mod)
    return mod, mock_bmesh


@pytest.fixture
def handler_and_bmesh():
    """Provide loaded mesh quality handler module and mock bmesh."""
    return _load_mesh_quality_handler()


def _make_mock_vert(index, has_faces=True, is_wire=False):
    """Create a mock BMVert."""
    vert = MagicMock()
    vert.index = index
    vert.link_faces = [MagicMock()] if has_faces else []
    vert.is_wire = is_wire
    return vert


def _make_mock_edge(index, is_manifold=True, is_wire=False):
    """Create a mock BMEdge."""
    edge = MagicMock()
    edge.index = index
    edge.is_manifold = is_manifold
    edge.is_wire = is_wire
    return edge


def _make_mock_face(index, area=1.0):
    """Create a mock BMFace."""
    face = MagicMock()
    face.index = index
    face.calc_area.return_value = area
    return face


def _make_bm_sequence(items):
    """Create a MagicMock that behaves like a BMesh element sequence (iterable + len + ensure_lookup_table)."""
    seq = MagicMock()
    seq.__iter__ = MagicMock(side_effect=lambda: iter(items))
    seq.__len__ = MagicMock(return_value=len(items))
    seq.ensure_lookup_table = MagicMock()
    return seq


def _configure_bm(bm, verts, edges, faces):
    """Configure a mock BMesh with the given elements."""
    bm.verts = _make_bm_sequence(verts)
    bm.edges = _make_bm_sequence(edges)
    bm.faces = _make_bm_sequence(faces)
    bm.free = MagicMock()
    return bm


class TestAnalyzeMeshQuality:
    """Tests for successful mesh quality analysis."""

    def test_returns_all_expected_keys(self, handler_and_bmesh):
        """Return dict contains all required report keys."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        verts = [_make_mock_vert(0), _make_mock_vert(1)]
        edges = [_make_mock_edge(0), _make_mock_edge(1)]
        faces = [_make_mock_face(0), _make_mock_face(1)]
        _configure_bm(bm, verts, edges, faces)
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {"targetmap": {}}

        result = mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        expected_keys = {
            "object",
            "vertex_count",
            "edge_count",
            "face_count",
            "non_manifold_edge_count",
            "non_manifold_edge_indices",
            "wire_edge_count",
            "loose_vertex_count",
            "loose_vertex_indices",
            "zero_area_face_count",
            "zero_area_face_indices",
            "duplicate_vertex_count",
            "issues_found",
        }
        assert set(result.keys()) == expected_keys

    def test_counts_non_manifold_edges(self, handler_and_bmesh):
        """non_manifold_edge_count reflects edges where is_manifold=False and is_wire=False."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        edges = [
            _make_mock_edge(0, is_manifold=True, is_wire=False),
            _make_mock_edge(1, is_manifold=False, is_wire=False),  # non-manifold
            _make_mock_edge(2, is_manifold=False, is_wire=True),   # wire (excluded)
        ]
        _configure_bm(bm, [], edges, [])
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {"targetmap": {}}

        result = mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        assert result["non_manifold_edge_count"] == 1
        assert result["non_manifold_edge_indices"] == [1]

    def test_counts_wire_edges(self, handler_and_bmesh):
        """wire_edge_count reflects edges where is_wire=True."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        edges = [
            _make_mock_edge(0, is_manifold=True, is_wire=False),
            _make_mock_edge(1, is_manifold=False, is_wire=True),  # wire
        ]
        _configure_bm(bm, [], edges, [])
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {"targetmap": {}}

        result = mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        assert result["wire_edge_count"] == 1

    def test_counts_loose_vertices(self, handler_and_bmesh):
        """loose_vertex_count reflects verts with no linked faces."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        verts = [
            _make_mock_vert(0, has_faces=True),   # connected
            _make_mock_vert(1, has_faces=False),  # loose
            _make_mock_vert(2, has_faces=False),  # loose
        ]
        _configure_bm(bm, verts, [], [])
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {"targetmap": {}}

        result = mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        assert result["loose_vertex_count"] == 2
        assert set(result["loose_vertex_indices"]) == {1, 2}

    def test_counts_zero_area_faces(self, handler_and_bmesh):
        """zero_area_face_count reflects faces where calc_area() < AREA_EPSILON."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        faces = [
            _make_mock_face(0, area=1.0),     # normal face
            _make_mock_face(1, area=0.0),     # zero area
            _make_mock_face(2, area=1e-9),    # below epsilon
        ]
        _configure_bm(bm, [], [], faces)
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {"targetmap": {}}

        result = mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        assert result["zero_area_face_count"] == 2
        assert set(result["zero_area_face_indices"]) == {1, 2}

    def test_counts_duplicate_vertices(self, handler_and_bmesh):
        """duplicate_vertex_count reflects number of entries in targetmap."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        verts = [_make_mock_vert(i) for i in range(4)]
        _configure_bm(bm, verts, [], [])
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {
            "targetmap": {"v0": "v1", "v2": "v3"}  # 2 duplicates
        }

        result = mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        assert result["duplicate_vertex_count"] == 2

    def test_issues_found_true_when_defects_exist(self, handler_and_bmesh):
        """issues_found is True when any defect count > 0."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        verts = [_make_mock_vert(0, has_faces=False)]  # loose vert
        _configure_bm(bm, verts, [], [])
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {"targetmap": {}}

        result = mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        assert result["issues_found"] is True

    def test_issues_found_false_for_clean_mesh(self, handler_and_bmesh):
        """issues_found is False when all counts are 0."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        verts = [_make_mock_vert(0, has_faces=True)]
        edges = [_make_mock_edge(0, is_manifold=True, is_wire=False)]
        faces = [_make_mock_face(0, area=1.0)]
        _configure_bm(bm, verts, edges, faces)
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {"targetmap": {}}

        result = mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        assert result["issues_found"] is False

    def test_non_manifold_indices_capped_at_50(self, handler_and_bmesh):
        """non_manifold_edge_indices is capped at 50 elements."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        # Create 100 non-manifold edges
        edges = [_make_mock_edge(i, is_manifold=False, is_wire=False) for i in range(100)]
        _configure_bm(bm, [], edges, [])
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {"targetmap": {}}

        result = mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        assert result["non_manifold_edge_count"] == 100
        assert len(result["non_manifold_edge_indices"]) == 50

    def test_loose_vertex_indices_capped_at_50(self, handler_and_bmesh):
        """loose_vertex_indices is capped at 50 elements."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        verts = [_make_mock_vert(i, has_faces=False) for i in range(100)]
        _configure_bm(bm, verts, [], [])
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {"targetmap": {}}

        result = mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        assert result["loose_vertex_count"] == 100
        assert len(result["loose_vertex_indices"]) == 50

    def test_zero_area_face_indices_capped_at_50(self, handler_and_bmesh):
        """zero_area_face_indices is capped at 50 elements."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        faces = [_make_mock_face(i, area=0.0) for i in range(100)]
        _configure_bm(bm, [], [], faces)
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {"targetmap": {}}

        result = mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        assert result["zero_area_face_count"] == 100
        assert len(result["zero_area_face_indices"]) == 50

    def test_bmesh_freed_on_success(self, handler_and_bmesh):
        """bm.free() is called after successful analysis."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        _configure_bm(bm, [], [], [])
        mock_bmesh.new.return_value = bm
        mock_bmesh.ops.find_doubles.return_value = {"targetmap": {}}

        mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        bm.free.assert_called_once()

    def test_bmesh_freed_on_exception(self, handler_and_bmesh):
        """bm.free() is called even when an exception occurs during analysis."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Cube"
        mock_obj.type = "MESH"
        mock_obj.data = MagicMock()
        bpy.data.objects.get.return_value = mock_obj
        bpy.context.active_object = None

        bm = MagicMock()
        bm.free = MagicMock()
        _configure_bm(bm, [], [], [])
        # Make from_mesh raise an exception
        bm.from_mesh.side_effect = RuntimeError("mesh error")
        mock_bmesh.new.return_value = bm

        with pytest.raises(RuntimeError):
            mod.handle_analyze_mesh_quality({"object_name": "Cube"})

        bm.free.assert_called_once()


class TestAnalyzeMeshQualityErrors:
    """Tests for error conditions in mesh quality analysis."""

    def test_raises_value_error_when_object_not_found(self, handler_and_bmesh):
        """Raises ValueError when object_name not found in bpy.data.objects."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        bpy.data.objects.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            mod.handle_analyze_mesh_quality({"object_name": "NonExistent"})

    def test_raises_value_error_when_not_mesh(self, handler_and_bmesh):
        """Raises ValueError when object type is not MESH."""
        mod, mock_bmesh = handler_and_bmesh

        import bpy
        mock_obj = MagicMock()
        mock_obj.name = "Camera"
        mock_obj.type = "CAMERA"
        bpy.data.objects.get.return_value = mock_obj

        with pytest.raises(ValueError, match="not a mesh"):
            mod.handle_analyze_mesh_quality({"object_name": "Camera"})
