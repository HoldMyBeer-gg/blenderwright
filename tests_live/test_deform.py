"""Vertex groups, shape keys and colour attributes in a real Blender.
Replaces the fake-bpy deform handler tests."""

import pytest

from blenderwright.tools import deform as d
from blenderwright.tools.objects import create_object, get_object_info
from blenderwright.tools.selection import select_by_axis


def _group(obj, name):
    return next(g for g in d.list_vertex_groups(obj)["groups"] if g["name"] == name)


@pytest.fixture
def box(scene):
    create_object("CUBE", name="Box")
    return "Box"


class TestVertexGroups:
    def test_creates_and_assigns(self, box):
        result = d.assign_vertex_group(box, "Top", vertex_indices=[1, 3], weight=0.5)
        assert result["created"] is True and result["changed"] == 2
        assert _group(box, "Top") == {"name": "Top", "index": 0, "vertex_count": 2,
                                      "min_weight": 0.5, "max_weight": 0.5}

    def test_whole_mesh_and_current_selection(self, box):
        d.assign_vertex_group(box, "All")
        assert _group(box, "All")["vertex_count"] == 8
        select_by_axis(box, axis="Z", sign="POS")
        d.assign_vertex_group(box, "Upper", selection="CURRENT")
        assert _group(box, "Upper")["vertex_count"] == 4

    def test_add_subtract_remove(self, box):
        d.assign_vertex_group(box, "G", weight=0.5)
        d.assign_vertex_group(box, "G", weight=0.25, mode="ADD")
        assert _group(box, "G")["max_weight"] == pytest.approx(0.75)
        d.assign_vertex_group(box, "G", vertex_indices=[0, 1], mode="REMOVE")
        assert _group(box, "G")["vertex_count"] == 6

    def test_index_past_the_mesh(self, box):
        with pytest.raises(RuntimeError, match="out of range"):
            d.assign_vertex_group(box, "G", vertex_indices=[8])

    def test_operation_on_the_group(self, box):
        d.assign_vertex_group(box, "G", weight=0.25)
        d.vertex_group_operation(box, "G", "NORMALIZE")
        assert _group(box, "G")["max_weight"] == pytest.approx(1.0)

    def test_remove_and_missing(self, box):
        d.assign_vertex_group(box, "G")
        assert d.remove_vertex_group(box, "G")["groups"] == []
        with pytest.raises(RuntimeError, match="G"):
            d.remove_vertex_group(box, "G")
        with pytest.raises(RuntimeError, match="Ghost"):
            d.list_vertex_groups("Ghost")


class TestShapeKeys:
    def test_first_key_makes_the_basis(self, box):
        d.add_shape_key(box, "Bulge")
        assert [k["name"] for k in d.list_shape_keys(box)["keys"]] == ["Basis", "Bulge"]

    def test_duplicate_refused(self, box):
        d.add_shape_key(box, "Bulge")
        with pytest.raises(RuntimeError, match="Bulge"):
            d.add_shape_key(box, "Bulge")

    def test_a_new_key_starts_on_and_its_value_blends(self, box):
        """In 5.2 a new key starts at 1.0, so moving it shows at once."""
        d.add_shape_key(box, "Tall")
        assert d.list_shape_keys(box)["keys"][1]["value"] == 1.0
        d.move_shape_key_vertices(box, "Tall", offset=[0, 0, 1],
                                  vertex_indices=[1, 3, 5, 7])
        assert get_object_info(box)["dimensions"][2] == pytest.approx(3.0)
        d.set_shape_key(box, "Tall", value=0.0)
        assert get_object_info(box)["dimensions"][2] == pytest.approx(2.0)
        d.set_shape_key(box, "Tall", value=0.5)
        assert get_object_info(box)["dimensions"][2] == pytest.approx(2.5)

    def test_move_by_group_weight(self, box):
        d.assign_vertex_group(box, "Half", vertex_indices=[1, 3, 5, 7], weight=0.5)
        d.add_shape_key(box, "Tall")
        d.move_shape_key_vertices(box, "Tall", offset=[0, 0, 1], vertex_group="Half")
        d.set_shape_key(box, "Tall", value=1.0)
        assert get_object_info(box)["dimensions"][2] == pytest.approx(2.5)

    def test_value_outside_the_slider_refused(self, box):
        d.add_shape_key(box, "Tall")
        with pytest.raises(RuntimeError):
            d.set_shape_key(box, "Tall", value=5.0)

    def test_basis_cannot_be_moved(self, box):
        d.add_shape_key(box, "Tall")
        with pytest.raises(RuntimeError, match="Basis"):
            d.move_shape_key_vertices(box, "Basis", offset=[0, 0, 1])

    def test_keyframe_list_and_remove(self, box):
        d.add_shape_key(box, "Tall")
        d.keyframe_shape_key(box, "Tall", frame=10, value=1.0)
        assert d.remove_shape_key(box, "Tall")["keys"] == ["Basis"]
        with pytest.raises(RuntimeError, match="Tall"):
            d.set_shape_key(box, "Tall", value=0.5)


class TestColorAttributes:
    def test_paints_all_and_becomes_the_render_colour(self, box):
        result = d.paint_color_attribute(box, [1, 0, 0])
        assert result["created"] is True and result["painted"] == 24  # face corners

    def test_point_domain_by_selection(self, box):
        select_by_axis(box, axis="Z", sign="POS")
        result = d.paint_color_attribute(box, [0, 1, 0], attribute_name="Mask",
                                         domain="POINT", selection="CURRENT")
        assert result["painted"] == 4

    def test_existing_attribute_keeps_its_layout(self, box):
        d.paint_color_attribute(box, [1, 0, 0], attribute_name="C", domain="POINT",
                                data_type="FLOAT_COLOR")
        again = d.paint_color_attribute(box, [0, 0, 1], attribute_name="C")
        assert again["created"] is False
        assert (again["domain"], again["data_type"]) == ("POINT", "FLOAT_COLOR")

    def test_out_of_range_and_remove(self, box):
        with pytest.raises(RuntimeError, match="out of range"):
            d.paint_color_attribute(box, [1, 0, 0], vertex_indices=[9])
        d.paint_color_attribute(box, [1, 0, 0])
        assert d.remove_color_attribute(box, "Color")["color_attributes"] == []
        with pytest.raises(RuntimeError, match="Color"):
            d.remove_color_attribute(box, "Color")
