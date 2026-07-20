"""Tests for addon.handlers.materials — shader node value control.

Covers socket default assignment, allowlisted node-property writes, and
ColorRamp stop editing. The allowlist is re-checked here rather than trusted
from the MCP layer: anything on the machine can open the addon's TCP port,
so the handler is the real trust boundary.
"""

import os
import sys
import importlib.util
from unittest.mock import MagicMock
import pytest


def _load_materials_handler():
    """Load addon.handlers.materials without triggering addon/__init__.py."""
    mock_dispatcher = MagicMock()
    mock_addon = MagicMock()
    mock_addon.dispatcher = mock_dispatcher
    sys.modules["addon"] = mock_addon
    sys.modules["addon.dispatcher"] = mock_dispatcher

    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "addon", "handlers", "materials.py",
    )
    spec = importlib.util.spec_from_file_location(
        "addon.handlers.materials", handler_path
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["addon.handlers.materials"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mh():
    return _load_materials_handler()


# ---------------------------------------------------------------------------
# Fakes — closer to the real bpy shape than bare MagicMocks
# ---------------------------------------------------------------------------


class FakeSocket:
    def __init__(self, name, default_value=0.0):
        self.name = name
        self.default_value = default_value


class FakeNoDefaultSocket:
    """A shader socket, which has no default_value at all."""

    def __init__(self, name):
        self.name = name


class FakeCollection(list):
    def get(self, name, default=None):
        for item in self:
            if getattr(item, "name", None) == name:
                return item
        return default


class FakeElement:
    def __init__(self, position, color):
        self.position = position
        self.color = list(color)


class FakeElements(list):
    """Ramp elements, kept sorted by position as Blender keeps them.

    Real Blender reorders and reindexes stops on insert and on position
    change. An append-only fake hides every index-shift bug, which is the
    same class of defect as the ramp-spacing bug that already shipped.
    """

    def new(self, position):
        element = FakeElement(position, [0.0, 0.0, 0.0, 1.0])
        self.append(element)
        self.sort(key=lambda e: e.position)
        return element

    def remove(self, element):
        list.remove(self, element)

    def resort(self):
        self.sort(key=lambda e: e.position)


class FakeRamp:
    def __init__(self):
        self.elements = FakeElements(
            [
                FakeElement(0.0, [0.0, 0.0, 0.0, 1.0]),
                FakeElement(1.0, [1.0, 1.0, 1.0, 1.0]),
            ]
        )
        self.interpolation = "LINEAR"
        self.color_mode = "RGB"


class FakePlainNode:
    """A node with sockets but no colour ramp."""

    def __init__(self, name, inputs=None):
        self.name = name
        self.inputs = FakeCollection(inputs or [])
        self.operation = "ADD"
        self.use_clamp = False


class FakeRampNode(FakePlainNode):
    def __init__(self, name, inputs=None):
        super().__init__(name, inputs)
        self.color_ramp = FakeRamp()


class FakeTree:
    def __init__(self, nodes):
        self.nodes = FakeCollection(nodes)


class FakeMaterial:
    def __init__(self, name, nodes, use_nodes=True):
        self.name = name
        self.use_nodes = use_nodes
        self.node_tree = FakeTree(nodes) if use_nodes else None


@pytest.fixture
def scene(mh):
    """Install a material into the mocked bpy.data and hand back its nodes."""
    import bpy

    math_node = FakePlainNode(
        "Math", [FakeSocket("Value", 0.0), FakeSocket("Value", 0.0)]
    )
    noise = FakePlainNode(
        "Noise", [FakeSocket("Scale", 5.0), FakeSocket("Vector", [0.0, 0.0, 0.0])]
    )
    ramp = FakeRampNode("ColorRamp", [FakeSocket("Fac", 0.5)])
    shader = FakePlainNode("Mix", [FakeNoDefaultSocket("Shader")])
    mat = FakeMaterial("Mat", [math_node, noise, ramp, shader])

    bpy.data.materials.get = lambda name: mat if name == "Mat" else None
    return {
        "mat": mat,
        "math": math_node,
        "noise": noise,
        "ramp": ramp,
        "shader": shader,
    }


# ---------------------------------------------------------------------------
# handle_set_shader_node_input
# ---------------------------------------------------------------------------


class TestSetShaderNodeInput:
    def test_sets_by_socket_name(self, mh, scene):
        mh.handle_set_shader_node_input(
            {"material_name": "Mat", "node_name": "Noise", "socket": "Scale", "value": 12.0}
        )
        assert scene["noise"].inputs[0].default_value == 12.0

    def test_sets_by_index(self, mh, scene):
        """Index reaches the second 'Value' socket, which name lookup cannot."""
        mh.handle_set_shader_node_input(
            {"material_name": "Mat", "node_name": "Math", "socket": 1, "value": 3.0}
        )
        assert scene["math"].inputs[1].default_value == 3.0
        assert scene["math"].inputs[0].default_value == 0.0

    def test_sets_vector_value(self, mh, scene):
        mh.handle_set_shader_node_input(
            {
                "material_name": "Mat",
                "node_name": "Noise",
                "socket": "Vector",
                "value": [1.0, 2.0, 3.0],
            }
        )
        assert list(scene["noise"].inputs[1].default_value) == [1.0, 2.0, 3.0]

    def test_returns_applied_value(self, mh, scene):
        result = mh.handle_set_shader_node_input(
            {"material_name": "Mat", "node_name": "Noise", "socket": "Scale", "value": 7.0}
        )
        assert result["value"] == 7.0
        assert result["node_name"] == "Noise"

    def test_unknown_socket_name_raises(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_set_shader_node_input(
                {"material_name": "Mat", "node_name": "Noise", "socket": "Nope", "value": 1.0}
            )

    def test_index_out_of_range_raises(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_set_shader_node_input(
                {"material_name": "Mat", "node_name": "Math", "socket": 99, "value": 1.0}
            )

    def test_socket_without_default_value_raises(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_set_shader_node_input(
                {"material_name": "Mat", "node_name": "Mix", "socket": "Shader", "value": 1.0}
            )

    def test_unknown_node_raises(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_set_shader_node_input(
                {"material_name": "Mat", "node_name": "Ghost", "socket": "Scale", "value": 1.0}
            )

    def test_unknown_material_raises(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_set_shader_node_input(
                {"material_name": "Nope", "node_name": "Noise", "socket": "Scale", "value": 1.0}
            )


# ---------------------------------------------------------------------------
# handle_set_shader_node_property
# ---------------------------------------------------------------------------


class TestSetShaderNodeProperty:
    def test_sets_allowed_property(self, mh, scene):
        mh.handle_set_shader_node_property(
            {
                "material_name": "Mat",
                "node_name": "Math",
                "property": "operation",
                "value": "MULTIPLY",
            }
        )
        assert scene["math"].operation == "MULTIPLY"

    def test_sets_bool_property(self, mh, scene):
        mh.handle_set_shader_node_property(
            {
                "material_name": "Mat",
                "node_name": "Math",
                "property": "use_clamp",
                "value": True,
            }
        )
        assert scene["math"].use_clamp is True

    def test_rejects_property_outside_allowlist(self, mh, scene):
        """The handler must not trust the MCP layer's validation."""
        with pytest.raises(RuntimeError):
            mh.handle_set_shader_node_property(
                {
                    "material_name": "Mat",
                    "node_name": "Math",
                    "property": "bl_idname",
                    "value": "X",
                }
            )

    def test_rejects_dunder_property(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_set_shader_node_property(
                {
                    "material_name": "Mat",
                    "node_name": "Math",
                    "property": "__class__",
                    "value": "X",
                }
            )

    def test_rejects_property_the_node_lacks(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_set_shader_node_property(
                {
                    "material_name": "Mat",
                    "node_name": "Math",
                    "property": "wave_type",
                    "value": "BANDS",
                }
            )


# ---------------------------------------------------------------------------
# ColorRamp handlers
# ---------------------------------------------------------------------------


class TestColorRampElements:
    def test_add_element(self, mh, scene):
        result = mh.handle_add_color_ramp_element(
            {
                "material_name": "Mat",
                "node_name": "ColorRamp",
                "position": 0.5,
                "color": [1.0, 0.0, 0.0, 1.0],
            }
        )
        elements = scene["ramp"].color_ramp.elements
        assert len(elements) == 3
        assert result["position"] == 0.5
        # Not elements[-1]: Blender keeps stops sorted, so a stop added at
        # 0.5 lands between the 0.0 and 1.0 ones rather than at the end.
        assert list(elements[result["index"]].color) == [1.0, 0.0, 0.0, 1.0]

    def test_add_on_non_ramp_node_raises(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_add_color_ramp_element(
                {
                    "material_name": "Mat",
                    "node_name": "Math",
                    "position": 0.5,
                    "color": [1.0, 0.0, 0.0, 1.0],
                }
            )

    def test_remove_element(self, mh, scene):
        result = mh.handle_remove_color_ramp_element(
            {"material_name": "Mat", "node_name": "ColorRamp", "index": 0}
        )
        assert len(scene["ramp"].color_ramp.elements) == 1
        assert result["remaining"] == 1

    def test_remove_out_of_range_raises(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_remove_color_ramp_element(
                {"material_name": "Mat", "node_name": "ColorRamp", "index": 9}
            )

    def test_remove_last_element_raises(self, mh, scene):
        ramp = scene["ramp"].color_ramp
        del ramp.elements[1]
        with pytest.raises(RuntimeError):
            mh.handle_remove_color_ramp_element(
                {"material_name": "Mat", "node_name": "ColorRamp", "index": 0}
            )

    def test_set_element_position(self, mh, scene):
        mh.handle_set_color_ramp_element(
            {"material_name": "Mat", "node_name": "ColorRamp", "index": 0, "position": 0.3}
        )
        assert scene["ramp"].color_ramp.elements[0].position == 0.3

    def test_set_element_color(self, mh, scene):
        mh.handle_set_color_ramp_element(
            {
                "material_name": "Mat",
                "node_name": "ColorRamp",
                "index": 1,
                "color": [0.0, 1.0, 0.0, 1.0],
            }
        )
        assert list(scene["ramp"].color_ramp.elements[1].color) == [0.0, 1.0, 0.0, 1.0]

    def test_set_element_leaves_unspecified_fields(self, mh, scene):
        before = scene["ramp"].color_ramp.elements[0].color[:]
        mh.handle_set_color_ramp_element(
            {"material_name": "Mat", "node_name": "ColorRamp", "index": 0, "position": 0.2}
        )
        assert scene["ramp"].color_ramp.elements[0].color == before

    def test_add_reports_the_index_after_reordering(self, mh, scene):
        """Blender keeps ramp stops sorted, so a new stop lands mid-list.

        The handler scans for the element by identity precisely because
        the insert reorders. Adding at 0.5 between stops at 0.0 and 1.0
        must report index 1, not the append position of 2.
        """
        result = mh.handle_add_color_ramp_element(
            {
                "material_name": "Mat",
                "node_name": "ColorRamp",
                "position": 0.5,
                "color": [1.0, 0.0, 0.0, 1.0],
            }
        )
        assert result["index"] == 1
        elements = scene["ramp"].color_ramp.elements
        assert [e.position for e in elements] == [0.0, 0.5, 1.0]
        assert list(elements[1].color) == [1.0, 0.0, 0.0, 1.0]

    def test_add_at_the_start_reports_index_zero(self, mh, scene):
        ramp = scene["ramp"].color_ramp
        ramp.elements[0].position = 0.4
        result = mh.handle_add_color_ramp_element(
            {
                "material_name": "Mat",
                "node_name": "ColorRamp",
                "position": 0.1,
                "color": [0.0, 1.0, 0.0, 1.0],
            }
        )
        assert result["index"] == 0

    def test_set_element_out_of_range_raises(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_set_color_ramp_element(
                {"material_name": "Mat", "node_name": "ColorRamp", "index": 9, "position": 0.5}
            )


class TestColorRampSettings:
    def test_set_interpolation(self, mh, scene):
        mh.handle_set_color_ramp_interpolation(
            {"material_name": "Mat", "node_name": "ColorRamp", "interpolation": "CONSTANT"}
        )
        assert scene["ramp"].color_ramp.interpolation == "CONSTANT"

    def test_set_color_mode(self, mh, scene):
        mh.handle_set_color_ramp_interpolation(
            {
                "material_name": "Mat",
                "node_name": "ColorRamp",
                "interpolation": "LINEAR",
                "color_mode": "HSV",
            }
        )
        assert scene["ramp"].color_ramp.color_mode == "HSV"

    def test_rejects_bad_interpolation(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_set_color_ramp_interpolation(
                {"material_name": "Mat", "node_name": "ColorRamp", "interpolation": "SMOOTH"}
            )

    def test_rejects_bad_color_mode(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_set_color_ramp_interpolation(
                {
                    "material_name": "Mat",
                    "node_name": "ColorRamp",
                    "interpolation": "LINEAR",
                    "color_mode": "CMYK",
                }
            )

    def test_get_color_ramp(self, mh, scene):
        result = mh.handle_get_color_ramp(
            {"material_name": "Mat", "node_name": "ColorRamp"}
        )
        assert result["interpolation"] == "LINEAR"
        assert result["color_mode"] == "RGB"
        assert len(result["elements"]) == 2
        assert result["elements"][0] == {
            "index": 0,
            "position": 0.0,
            "color": [0.0, 0.0, 0.0, 1.0],
        }

    def test_get_on_non_ramp_node_raises(self, mh, scene):
        with pytest.raises(RuntimeError):
            mh.handle_get_color_ramp({"material_name": "Mat", "node_name": "Math"})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_new_commands_are_registered(self, mh):
        mh.dispatcher.register_handler.reset_mock()
        mh.register()
        registered = {
            call.args[0] for call in mh.dispatcher.register_handler.call_args_list
        }
        assert {
            "set_shader_node_input",
            "set_shader_node_property",
            "add_color_ramp_element",
            "remove_color_ramp_element",
            "set_color_ramp_element",
            "set_color_ramp_interpolation",
            "get_color_ramp",
        } <= registered
