"""Tests for drivers. Only simple expressions are allowed: Blender evaluates
those itself, without Python, so a driver can never run code."""

from unittest.mock import MagicMock, patch

import pytest

from blenderwright.tools.animation import add_driver, list_drivers, remove_driver
from blenderwright.validators import ValidationError, validate_driver_expression, validate_data_path


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blenderwright.tools.animation.get_connection", return_value=mock):
        yield mock


def _sent(mock_conn):
    return mock_conn.send_command.call_args[0]


class TestExpressionValidator:
    @pytest.mark.parametrize("expr", [
        "lx * 2", "sin(frame / 10) * 0.5", "lx + 1 if lx > 0 else 0", "max(lx, 1)",
        "clamp(a - b, 0, 1)", "-lx", "radians(45)", "pi * r", "a and not b", "a % 2 == 0",
        "1.5e-3 * frame",
    ])
    def test_simple_expressions_pass(self, expr):
        assert validate_driver_expression(expr, {"lx", "a", "b", "r"}) == expr

    @pytest.mark.parametrize("expr", [
        '__import__("os")', "bpy.data.objects", "lx.real", "lx[0]", "open('x')",
        "eval('1')", "getattr(lx, 'x')", "lx ** 2", "lambda: 1", "unknown_var * 2",
        "exec", "a; b", "a\nb", "x" * 300, "", "__class__", "{1: 2}", "lx @ 2",
    ])
    def test_anything_else_is_refused(self, expr):
        with pytest.raises(ValidationError):
            validate_driver_expression(expr, {"lx", "a", "b"})


class TestDataPathValidator:
    @pytest.mark.parametrize("path", [
        "location", "rotation_euler", "data.energy", 'modifiers["Bend"].angle',
        'data.shape_keys.key_blocks["Smile"].value', "scale", "color",
    ])
    def test_rna_paths_pass(self, path):
        assert validate_data_path(path) == path

    @pytest.mark.parametrize("path", [
        "", "location()", "__class__", "data.__dict__", 'modifiers["a"]["b"', "a..b",
        "location; x", "location[0]", 'modifiers["a\\"b"]', "x" * 300, "data.energy + 1",
    ])
    def test_everything_else_is_refused(self, path):
        with pytest.raises(ValidationError):
            validate_data_path(path)


class TestAddDriver:
    def test_scripted_with_transform_variable(self, mock_conn):
        add_driver("Cube", "location", index=2, expression="lx * 2", variables=[
            {"name": "lx", "type": "TRANSFORMS", "object": "Light",
             "transform_type": "LOC_X"}])
        assert _sent(mock_conn) == ("add_driver", {
            "object_name": "Cube", "data_path": "location", "index": 2,
            "driver_type": "SCRIPTED", "expression": "lx * 2",
            "variables": [{"name": "lx", "type": "TRANSFORMS", "object": "Light",
                           "transform_type": "LOC_X", "transform_space": "WORLD_SPACE"}]})

    def test_single_property_variable(self, mock_conn):
        add_driver("Lamp", "data.energy", expression="e * 10", variables=[
            {"name": "e", "type": "SINGLE_PROP", "object": "Dial", "data_path": "location"}])
        var = _sent(mock_conn)[1]["variables"][0]
        assert var == {"name": "e", "type": "SINGLE_PROP", "object": "Dial",
                       "data_path": "location"}

    def test_frame_needs_no_variable(self, mock_conn):
        add_driver("Cube", "rotation_euler", index=2, expression="frame / 24")
        assert _sent(mock_conn)[1]["variables"] == []

    def test_average_driver_needs_no_expression(self, mock_conn):
        add_driver("Cube", "scale", index=0, driver_type="AVERAGE", variables=[
            {"name": "a", "type": "TRANSFORMS", "object": "A", "transform_type": "SCALE_X"}])
        assert _sent(mock_conn)[1]["expression"] == ""

    @pytest.mark.parametrize("kwargs", [
        {"expression": "__import__('os')"},
        {"expression": "lx * 2", "variables": []},
        {"expression": "a", "variables": [{"name": "a", "type": "CONTEXT_PROP"}]},
        {"expression": "a", "variables": [{"name": "1a", "type": "TRANSFORMS",
                                           "object": "L", "transform_type": "LOC_X"}]},
        {"expression": "a", "variables": [{"name": "a", "type": "TRANSFORMS",
                                           "object": "L", "transform_type": "LOC_Q"}]},
        {"expression": "a", "variables": [{"name": "a", "type": "SINGLE_PROP",
                                           "object": "L", "data_path": "__class__"}]},
        {"driver_type": "PYTHON", "expression": "1"},
        {"data_path": "location()", "expression": "1"},
        {"expression": "1", "index": 5},
    ])
    def test_rejects(self, mock_conn, kwargs):
        args = {"object_name": "Cube", "data_path": "location", "expression": "1", **kwargs}
        with pytest.raises(ValidationError):
            add_driver(**args)
        mock_conn.send_command.assert_not_called()


class TestRemoveAndList:
    def test_remove(self, mock_conn):
        remove_driver("Cube", "location", index=2)
        assert _sent(mock_conn) == ("remove_driver", {"object_name": "Cube",
                                                      "data_path": "location", "index": 2})

    def test_list(self, mock_conn):
        list_drivers("Cube")
        assert _sent(mock_conn) == ("list_drivers", {"object_name": "Cube"})


def test_handler_allowlists_mirror_the_tool():
    """The add-on keeps its own copy (it cannot import the MCP package)."""
    import ast
    import pathlib

    from blenderwright import validators

    tree = ast.parse((pathlib.Path(__file__).parents[2] / "addon" / "handlers" /
                      "animation.py").read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in ("DRIVER_FUNCTIONS", "DRIVER_WORDS"):
            found[node.targets[0].id] = set(ast.literal_eval(node.value.args[0]))
    assert found["DRIVER_FUNCTIONS"] == set(validators.DRIVER_FUNCTIONS)
    assert found["DRIVER_WORDS"] == set(validators.DRIVER_WORDS)
