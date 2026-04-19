"""Unit tests for object tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError
from blend_ai.tools.objects import (
    create_object,
    create_polygon_prism,
    create_threaded_shaft,
    delete_object,
    duplicate_object,
    rename_object,
    select_objects,
    get_object_info,
    list_objects,
    set_object_visibility,
    parent_objects,
    join_objects,
    set_origin,
    convert_object,
    shade_auto_smooth,
    make_single_user,
)


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"some": "data"}}
    with patch("blend_ai.tools.objects.get_connection", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# create_object
# ---------------------------------------------------------------------------


class TestCreateObject:
    def test_valid_cube(self, mock_conn):
        create_object("CUBE", name="MyCube")
        mock_conn.send_command.assert_called_once_with(
            "create_object",
            {
                "type": "CUBE",
                "name": "MyCube",
                "location": [0, 0, 0],
                "rotation": [0, 0, 0],
                "scale": [1, 1, 1],
            },
        )

    def test_valid_with_location(self, mock_conn):
        create_object("SPHERE", location=[1.0, 2.0, 3.0])
        call_args = mock_conn.send_command.call_args
        assert call_args[0][1]["location"] == [1.0, 2.0, 3.0]
        assert call_args[0][1]["type"] == "SPHERE"

    def test_valid_all_params(self, mock_conn):
        create_object(
            "CYLINDER",
            name="Cyl",
            location=[1, 0, 0],
            rotation=[0, 1.57, 0],
            scale=[2, 2, 2],
        )
        args = mock_conn.send_command.call_args[0][1]
        assert args["type"] == "CYLINDER"
        assert args["name"] == "Cyl"
        assert args["rotation"] == [0, 1.57, 0]
        assert args["scale"] == [2, 2, 2]

    def test_no_name_sends_empty(self, mock_conn):
        create_object("PLANE")
        args = mock_conn.send_command.call_args[0][1]
        assert args["name"] == ""

    def test_invalid_type_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_object("INVALID_TYPE")

    def test_invalid_name_chars_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_object("CUBE", name="bad;name")

    def test_invalid_location_wrong_size_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_object("CUBE", location=[1, 2])

    def test_invalid_location_non_numeric_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_object("CUBE", location=["a", "b", "c"])

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            create_object("CUBE")


# ---------------------------------------------------------------------------
# delete_object
# ---------------------------------------------------------------------------


class TestDeleteObject:
    def test_valid(self, mock_conn):
        delete_object("Cube")
        mock_conn.send_command.assert_called_once_with(
            "delete_object", {"name": "Cube"}
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            delete_object("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "not found"}
        with pytest.raises(RuntimeError):
            delete_object("Cube")


# ---------------------------------------------------------------------------
# duplicate_object
# ---------------------------------------------------------------------------


class TestDuplicateObject:
    def test_valid(self, mock_conn):
        duplicate_object("Cube")
        mock_conn.send_command.assert_called_once_with(
            "duplicate_object", {"name": "Cube", "linked": False}
        )

    def test_linked(self, mock_conn):
        duplicate_object("Cube", linked=True)
        mock_conn.send_command.assert_called_once_with(
            "duplicate_object", {"name": "Cube", "linked": True}
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            duplicate_object("")


# ---------------------------------------------------------------------------
# rename_object
# ---------------------------------------------------------------------------


class TestRenameObject:
    def test_valid(self, mock_conn):
        rename_object("OldName", "NewName")
        mock_conn.send_command.assert_called_once_with(
            "rename_object", {"old_name": "OldName", "new_name": "NewName"}
        )

    def test_empty_old_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            rename_object("", "NewName")

    def test_empty_new_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            rename_object("OldName", "")

    def test_invalid_new_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            rename_object("OldName", "bad<>name")


# ---------------------------------------------------------------------------
# select_objects
# ---------------------------------------------------------------------------


class TestSelectObjects:
    def test_valid(self, mock_conn):
        select_objects(["Cube", "Sphere"])
        mock_conn.send_command.assert_called_once_with(
            "select_objects", {"names": ["Cube", "Sphere"], "deselect_others": True}
        )

    def test_deselect_false(self, mock_conn):
        select_objects(["Cube"], deselect_others=False)
        args = mock_conn.send_command.call_args[0][1]
        assert args["deselect_others"] is False

    def test_invalid_name_in_list_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            select_objects(["Cube", "bad;name"])


# ---------------------------------------------------------------------------
# get_object_info
# ---------------------------------------------------------------------------


class TestGetObjectInfo:
    def test_valid(self, mock_conn):
        mock_conn.send_command.return_value = {
            "status": "ok",
            "result": {"name": "Cube", "type": "MESH"},
        }
        result = get_object_info("Cube")
        mock_conn.send_command.assert_called_once_with(
            "get_object_info", {"name": "Cube"}
        )
        assert result["type"] == "MESH"

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            get_object_info("")


# ---------------------------------------------------------------------------
# list_objects
# ---------------------------------------------------------------------------


class TestListObjects:
    def test_no_filter(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "ok", "result": []}
        list_objects()
        mock_conn.send_command.assert_called_once_with(
            "list_objects", {"type_filter": ""}
        )

    def test_with_filter(self, mock_conn):
        list_objects(type_filter="MESH")
        mock_conn.send_command.assert_called_once_with(
            "list_objects", {"type_filter": "MESH"}
        )

    def test_invalid_filter_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            list_objects(type_filter="INVALID")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "err"}
        with pytest.raises(RuntimeError):
            list_objects()


# ---------------------------------------------------------------------------
# set_object_visibility
# ---------------------------------------------------------------------------


class TestSetObjectVisibility:
    def test_valid(self, mock_conn):
        set_object_visibility("Cube", visible=False)
        mock_conn.send_command.assert_called_once_with(
            "set_object_visibility",
            {"name": "Cube", "visible": False, "viewport": True, "render": True},
        )

    def test_viewport_only(self, mock_conn):
        set_object_visibility("Cube", visible=True, viewport=True, render=False)
        args = mock_conn.send_command.call_args[0][1]
        assert args["viewport"] is True
        assert args["render"] is False

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_object_visibility("", visible=True)


# ---------------------------------------------------------------------------
# parent_objects
# ---------------------------------------------------------------------------


class TestParentObjects:
    def test_valid(self, mock_conn):
        parent_objects("Child", "Parent")
        mock_conn.send_command.assert_called_once_with(
            "parent_objects", {"child": "Child", "parent": "Parent"}
        )

    def test_empty_child_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            parent_objects("", "Parent")

    def test_empty_parent_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            parent_objects("Child", "")


# ---------------------------------------------------------------------------
# join_objects
# ---------------------------------------------------------------------------


class TestJoinObjects:
    def test_valid(self, mock_conn):
        join_objects(["Cube", "Sphere"])
        mock_conn.send_command.assert_called_once_with(
            "join_objects", {"names": ["Cube", "Sphere"]}
        )

    def test_too_few_objects_raises(self, mock_conn):
        with pytest.raises(ValidationError, match="At least 2"):
            join_objects(["Cube"])

    def test_empty_list_raises(self, mock_conn):
        with pytest.raises(ValidationError, match="At least 2"):
            join_objects([])

    def test_invalid_name_in_list_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            join_objects(["Cube", "bad;name"])

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            join_objects(["Cube", "Sphere"])


# ---------------------------------------------------------------------------
# set_origin
# ---------------------------------------------------------------------------


class TestSetOrigin:
    def test_valid(self, mock_conn):
        set_origin("Cube")
        mock_conn.send_command.assert_called_once_with(
            "set_origin",
            {"object_name": "Cube", "type": "ORIGIN_GEOMETRY"},
        )

    def test_valid_with_type(self, mock_conn):
        set_origin("Cube", type="ORIGIN_CURSOR")
        mock_conn.send_command.assert_called_once_with(
            "set_origin",
            {"object_name": "Cube", "type": "ORIGIN_CURSOR"},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_origin("")

    def test_invalid_type_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            set_origin("Cube", type="INVALID")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            set_origin("Cube")


# ---------------------------------------------------------------------------
# convert_object
# ---------------------------------------------------------------------------


class TestConvertObject:
    def test_valid(self, mock_conn):
        convert_object("Cube")
        mock_conn.send_command.assert_called_once_with(
            "convert_object",
            {"object_name": "Cube", "target": "MESH"},
        )

    def test_valid_with_target(self, mock_conn):
        convert_object("Cube", target="CURVE")
        mock_conn.send_command.assert_called_once_with(
            "convert_object",
            {"object_name": "Cube", "target": "CURVE"},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            convert_object("")

    def test_invalid_target_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            convert_object("Cube", target="INVALID")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            convert_object("Cube")


# ---------------------------------------------------------------------------
# shade_auto_smooth
# ---------------------------------------------------------------------------


class TestShadeAutoSmooth:
    def test_valid(self, mock_conn):
        shade_auto_smooth("Cube")
        mock_conn.send_command.assert_called_once_with(
            "shade_auto_smooth",
            {"object_name": "Cube", "angle": 0.523599},
        )

    def test_valid_with_angle(self, mock_conn):
        shade_auto_smooth("Cube", angle=1.0)
        mock_conn.send_command.assert_called_once_with(
            "shade_auto_smooth",
            {"object_name": "Cube", "angle": 1.0},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            shade_auto_smooth("")

    def test_angle_too_low_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            shade_auto_smooth("Cube", angle=-0.1)

    def test_angle_too_high_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            shade_auto_smooth("Cube", angle=3.15)

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            shade_auto_smooth("Cube")


# ---------------------------------------------------------------------------
# make_single_user
# ---------------------------------------------------------------------------


class TestMakeSingleUser:
    def test_valid(self, mock_conn):
        make_single_user("Cube")
        mock_conn.send_command.assert_called_once_with(
            "make_single_user",
            {"object_name": "Cube", "object": True, "data": True},
        )

    def test_valid_with_params(self, mock_conn):
        make_single_user("Cube", object=False, data=True)
        mock_conn.send_command.assert_called_once_with(
            "make_single_user",
            {"object_name": "Cube", "object": False, "data": True},
        )

    def test_empty_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            make_single_user("")

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            make_single_user("Cube")


# ---------------------------------------------------------------------------
# create_polygon_prism
# ---------------------------------------------------------------------------


class TestCreatePolygonPrism:
    def test_valid_hex(self, mock_conn):
        create_polygon_prism(sides=6, radius=1.0, depth=0.5, name="Hex")
        mock_conn.send_command.assert_called_once_with(
            "create_polygon_prism",
            {
                "sides": 6,
                "radius": 1.0,
                "depth": 0.5,
                "name": "Hex",
                "location": [0, 0, 0],
                "rotation": [0, 0, 0],
                "scale": [1, 1, 1],
            },
        )

    def test_defaults_applied(self, mock_conn):
        create_polygon_prism(sides=8)
        args = mock_conn.send_command.call_args[0][1]
        assert args["sides"] == 8
        assert args["radius"] == 1.0
        assert args["depth"] == 2.0
        assert args["name"] == ""

    def test_sides_below_minimum_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_polygon_prism(sides=2)

    def test_sides_above_maximum_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_polygon_prism(sides=65)

    def test_sides_non_integer_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_polygon_prism(sides=6.5)

    def test_radius_zero_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_polygon_prism(sides=6, radius=0)

    def test_radius_negative_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_polygon_prism(sides=6, radius=-1.0)

    def test_depth_zero_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_polygon_prism(sides=6, depth=0)

    def test_invalid_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_polygon_prism(sides=6, name="bad;name")

    def test_invalid_location_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_polygon_prism(sides=6, location=[1, 2])

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            create_polygon_prism(sides=6)


# ---------------------------------------------------------------------------
# create_threaded_shaft
# ---------------------------------------------------------------------------


class TestCreateThreadedShaft:
    def test_valid_m3(self, mock_conn):
        create_threaded_shaft(
            diameter=3.0, length=10.0, pitch=0.5, name="M3Shaft"
        )
        args = mock_conn.send_command.call_args[0][1]
        assert args["diameter"] == 3.0
        assert args["length"] == 10.0
        assert args["pitch"] == 0.5
        assert args["name"] == "M3Shaft"
        # thread_depth defaults to 0 (auto — handler computes it)
        assert args["thread_depth"] == 0.0
        assert args["segments"] == 32
        # thread_runout defaults to -1 (auto — handler sets to one pitch)
        assert args["thread_runout"] == -1.0

    def test_explicit_thread_runout(self, mock_conn):
        create_threaded_shaft(
            diameter=3.0, length=10.0, pitch=0.5, thread_runout=2.0
        )
        args = mock_conn.send_command.call_args[0][1]
        assert args["thread_runout"] == 2.0

    def test_thread_runout_zero_threads_full_length(self, mock_conn):
        """thread_runout=0 means no smooth cylinder at the top — threads all
        the way up. Distinct from the -1 auto sentinel."""
        create_threaded_shaft(
            diameter=3.0, length=10.0, pitch=0.5, thread_runout=0.0
        )
        args = mock_conn.send_command.call_args[0][1]
        assert args["thread_runout"] == 0.0

    def test_thread_runout_exceeds_length_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_threaded_shaft(
                diameter=3.0, length=10.0, pitch=0.5, thread_runout=15.0
            )

    def test_explicit_thread_depth(self, mock_conn):
        create_threaded_shaft(
            diameter=3.0, length=10.0, pitch=0.5, thread_depth=0.27
        )
        args = mock_conn.send_command.call_args[0][1]
        assert args["thread_depth"] == 0.27

    def test_custom_segments(self, mock_conn):
        create_threaded_shaft(diameter=3.0, length=10.0, pitch=0.5, segments=64)
        args = mock_conn.send_command.call_args[0][1]
        assert args["segments"] == 64

    def test_diameter_zero_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_threaded_shaft(diameter=0, length=10.0, pitch=0.5)

    def test_diameter_negative_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_threaded_shaft(diameter=-1.0, length=10.0, pitch=0.5)

    def test_length_zero_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_threaded_shaft(diameter=3.0, length=0, pitch=0.5)

    def test_pitch_zero_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_threaded_shaft(diameter=3.0, length=10.0, pitch=0)

    def test_pitch_larger_than_length_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_threaded_shaft(diameter=3.0, length=0.3, pitch=0.5)

    def test_thread_depth_exceeds_radius_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            # radius = 1.5, thread_depth = 2.0 would eat through the shaft
            create_threaded_shaft(
                diameter=3.0, length=10.0, pitch=0.5, thread_depth=2.0
            )

    def test_segments_too_few_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_threaded_shaft(
                diameter=3.0, length=10.0, pitch=0.5, segments=2
            )

    def test_segments_too_many_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_threaded_shaft(
                diameter=3.0, length=10.0, pitch=0.5, segments=1024
            )

    def test_invalid_name_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_threaded_shaft(
                diameter=3.0, length=10.0, pitch=0.5, name="bad;name"
            )

    def test_invalid_location_raises(self, mock_conn):
        with pytest.raises(ValidationError):
            create_threaded_shaft(
                diameter=3.0, length=10.0, pitch=0.5, location=[1, 2]
            )

    def test_error_response_raises(self, mock_conn):
        mock_conn.send_command.return_value = {"status": "error", "result": "fail"}
        with pytest.raises(RuntimeError):
            create_threaded_shaft(diameter=3.0, length=10.0, pitch=0.5)
