"""Numbers and booleans that arrive as text must reach Blender as numbers.

A client that sees no type on a parameter may send 53.0 as the string "53.0".
Blender then refuses it ("assigned value not a number"), or worse, stores the
text. These tools used to forward the string untouched.
"""

import asyncio
import importlib
from unittest.mock import MagicMock, patch

import pytest

from blenderwright.server import mcp
from blenderwright.validators import coerce_scalar


class TestCoerceScalar:
    @pytest.mark.parametrize("text, expected", [
        ("53.0", 53.0),
        ("53", 53),
        ("-0.5", -0.5),
        (".25", 0.25),
        ("1e3", 1000.0),
        (" 7 ", 7),
        ("true", True),
        ("False", False),
    ])
    def test_number_and_boolean_text_is_converted(self, text, expected):
        result = coerce_scalar(text)
        assert result == expected
        assert type(result) is type(expected)

    @pytest.mark.parametrize("text", [
        "BOX", "PERSP", "", "1.2.3", "5 apples", "NaN", "Infinity", "inf", "1e999", "1_000",
    ])
    def test_other_text_is_left_alone(self, text):
        assert coerce_scalar(text) == text

    @pytest.mark.parametrize("value", [5, 2.5, True, None, [1, 2, 3]])
    def test_non_text_is_left_alone(self, value):
        assert coerce_scalar(value) is value


# tool name, arguments with the value sent as text, the value Blender should get
TEXT_CASES = [
    ("insert_keyframe",
     dict(object_name="Cube", data_path="location[2]", frame=60, value="53.0"), 53.0),
    ("set_physics_property",
     dict(object_name="Cube", physics_type="RIGID_BODY", property="mass", value="2.0"), 2.0),
    ("set_physics_property",
     dict(object_name="Cube", physics_type="RIGID_BODY", property="kinematic", value="true"),
     True),
    ("set_bone_property",
     dict(armature_name="Rig", bone_name="Bone", property="roll", value="0.5"), 0.5),
    ("set_bone_property",
     dict(armature_name="Rig", bone_name="Bone", property="use_deform", value="false"), False),
    ("set_annotation_stroke_property",
     dict(annotation_name="Notes", layer_name="Layer", stroke_index=0,
          property="line_width", value="3"), 3),
]


def _sent_value(tool_name, arguments):
    tool = mcp._tool_manager.get_tool(tool_name)
    module = importlib.import_module(tool.fn.__module__)
    conn = MagicMock()
    conn.send_command.return_value = {"status": "ok", "result": {}}
    with patch.object(module, "get_connection", return_value=conn):
        tool.fn(**arguments)
    return conn.send_command.call_args[0][1]["value"]


class TestToolsConvertText:
    @pytest.mark.parametrize("tool_name, arguments, expected", TEXT_CASES)
    def test_text_reaches_blender_typed(self, tool_name, arguments, expected):
        sent = _sent_value(tool_name, arguments)
        assert sent == expected
        assert type(sent) is type(expected)

    def test_enum_words_stay_text(self):
        sent = _sent_value("set_physics_property", dict(
            object_name="Cube", physics_type="RIGID_BODY",
            property="collision_shape", value="BOX",
        ))
        assert sent == "BOX"

    def test_geometry_node_text_is_left_for_the_handler(self):
        """Only the handler knows whether the socket is a String socket."""
        sent = _sent_value("set_geometry_node_input", dict(
            object_name="Cube", modifier_name="GeometryNodes", input_name="Label", value="5",
        ))
        assert sent == "5"


class TestInsertKeyframeSchema:
    def test_value_declares_its_type(self):
        """An untyped schema is what made the client send text in the first place."""
        schema = mcp._tool_manager.get_tool("insert_keyframe").parameters
        value = schema["properties"]["value"]
        declared = {option.get("type") for option in value["anyOf"]}
        assert {"number", "array", "null"} <= declared

    def test_text_sent_through_the_mcp_layer_becomes_a_number(self):
        tool = mcp._tool_manager.get_tool("insert_keyframe")
        module = importlib.import_module(tool.fn.__module__)
        conn = MagicMock()
        conn.send_command.return_value = {"status": "ok", "result": {}}
        with patch.object(module, "get_connection", return_value=conn):
            asyncio.run(tool.run({
                "object_name": "Cube", "data_path": "location[2]", "frame": 60, "value": "53.0",
            }))
        sent = conn.send_command.call_args[0][1]["value"]
        assert sent == 53.0 and isinstance(sent, float)

    def test_vector_values_still_pass(self):
        sent = _sent_value("insert_keyframe", dict(
            object_name="Cube", data_path="location", frame=1, value=[1.0, 2.0, 3.0],
        ))
        assert sent == [1.0, 2.0, 3.0]
