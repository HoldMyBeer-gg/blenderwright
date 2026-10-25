"""Object creation in a real Blender, judged by the geometry that results.
Replaces the fake-bpy objects handler tests."""

import pytest

from blenderwright.tools import objects as o
from blenderwright.tools.mesh_quality import analyze_mesh_quality


class TestCreateObject:
    def test_reports_dimensions_and_world_bounds(self, scene):
        result = o.create_object("CUBE", name="Tower", location=[0, 0, 5], scale=[5, 5, 18.5])
        assert result["dimensions"] == pytest.approx([10.0, 10.0, 37.0])
        assert result["bounds"]["min"] == pytest.approx([-5.0, -5.0, -13.5])
        assert result["bounds"]["max"] == pytest.approx([5.0, 5.0, 23.5])

    def test_plane_scale_is_honoured(self, scene):
        """primitive_plane_add ignores its scale argument; the tool bakes it."""
        result = o.create_object("PLANE", name="Floor", scale=[3, 4.5, 1])
        assert result["dimensions"][:2] == pytest.approx([6.0, 9.0])
        assert o.get_object_info("Floor")["scale"] == pytest.approx([1, 1, 1])

    def test_cube_scale_is_not_doubled(self, scene):
        assert o.create_object("CUBE", name="Box", scale=[2, 2, 2])["dimensions"] == \
            pytest.approx([4.0, 4.0, 4.0])

    def test_empty_keeps_object_scale(self, scene):
        o.create_object("EMPTY", name="Pivot", scale=[2, 3, 4])
        assert o.get_object_info("Pivot")["scale"] == pytest.approx([2, 3, 4])


class TestPolygonPrism:
    def test_six_sides_and_two_caps(self, scene):
        result = o.create_polygon_prism(6, radius=1.0, depth=0.8, name="Nut")
        assert result["name"] == "Nut"
        assert result["dimensions"][2] == pytest.approx(0.8)
        report = analyze_mesh_quality("Nut")
        assert report["face_count"] == 8 and report["vertex_count"] == 12


class TestThreadedShaft:
    @pytest.fixture
    def shaft(self, scene):
        return o.create_threaded_shaft(diameter=3.0, length=10.0, pitch=0.5, name="Bolt")

    def test_named_and_sized(self, shaft):
        assert shaft["name"] == "Bolt"
        assert shaft["dimensions"][0] == pytest.approx(3.0, abs=0.05)
        assert shaft["dimensions"][2] == pytest.approx(10.0, abs=0.05)

    @pytest.mark.parametrize("args", [
        {"diameter": 3.0, "length": 10.0, "pitch": 0.5},
        {"diameter": 8.0, "length": 20.0, "pitch": 1.25},
        {"diameter": 3.0, "length": 10.0, "pitch": 0.5, "segments": 64},
        {"diameter": 6.0, "length": 12.0, "pitch": 1.0, "thread_runout": 3.0},
    ])
    def test_watertight_for_printing(self, scene, args):
        """The thread used to sit exactly on the core, and the union left
        edges shared by four faces."""
        o.create_threaded_shaft(name="Bolt", **args)
        report = analyze_mesh_quality("Bolt")
        assert report["non_manifold_edge_count"] == 0
        assert report["loose_vertex_count"] == 0

    def test_one_object_left(self, shaft):
        names = {x["name"] for x in o.list_objects()}
        assert "Bolt" in names and not any(n.startswith(("Ridge", "Thread")) for n in names)


class TestJoin:
    def test_names_the_survivor_and_the_consumed(self, scene):
        o.create_object("CUBE", name="main_body")
        o.create_object("CUBE", name="right_wing", location=[3, 0, 0])
        o.create_object("CUBE", name="left_wing", location=[-3, 0, 0])
        result = o.join_objects(["main_body", "right_wing", "left_wing"])
        assert result["name"] == "main_body"
        assert result["removed"] == ["right_wing", "left_wing"]
        assert result["joined_count"] == 3  # objects that went into the join
        assert "main_body" in result["note"]
        assert analyze_mesh_quality("main_body")["vertex_count"] == 24
