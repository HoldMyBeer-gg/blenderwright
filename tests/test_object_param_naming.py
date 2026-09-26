"""One spelling for "which object", across every tool.

The same concept was spelled two ways. 75 tools took `object_name`; 15 took a
bare `name` to mean an object that already exists. A caller reading one tool's
schema could not predict the next one, so every call was a guess, and
strict.py (correctly) turns a wrong guess into an error rather than a silent
no-op. Two round trips per tool, out of a fixed budget.

`object_name` wins on count, and because `name` is already taken: the create_*
tools use it for the object being made. Those are a different concept and are
deliberately left alone -- create_material(name=...) names the new material,
and aliasing it to `object_name` would be a lie.

Renaming alone would break anything already calling with `name`, so the old
spelling stays valid as a pydantic validation alias. The published schema
advertises one name; both are accepted.
"""

import ast
import pathlib

import pytest

from blend_ai.aliases import RENAMED_FROM_NAME

TOOLS_DIR = pathlib.Path(__file__).parent.parent / "src" / "blend_ai" / "tools"

# The single source of truth lives beside the implementation.
RENAMED = set(RENAMED_FROM_NAME)

# Tools where `name` means the thing being created. Must not change.
CREATORS = {
    "create_object", "create_material", "create_principled_material",
    "create_procedural_material", "create_raster_texture", "create_light",
    "create_camera", "create_armature", "create_curve", "create_text",
    "create_collection", "create_scene", "create_polygon_prism",
    "create_threaded_shaft", "create_geometry_nodes", "create_annotation",
    "add_modifier", "sweep_profile_along_path",
}


def _tool_functions():
    for path in sorted(TOOLS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "tool"
                   for d in node.decorator_list):
                yield path.name, node


def _params(node):
    return [a.arg for a in node.args.args]


def _doc_args(node):
    """Parameter names documented in the Args: block."""
    doc = ast.get_docstring(node) or ""
    out, in_args = [], False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith("Args:"):
            in_args = True
            continue
        if in_args and stripped.startswith(("Returns:", "Raises:")):
            break
        if in_args and ":" in stripped and not line.startswith(" " * 12):
            out.append(stripped.split(":")[0].strip())
    return out


class TestRenamed:
    def test_every_renamed_tool_exists(self):
        found = {n.name for _f, n in _tool_functions()}
        missing = RENAMED - found
        assert not missing, f"listed tools that no longer exist: {sorted(missing)}"

    @pytest.mark.parametrize("tool", sorted(RENAMED))
    def test_uses_object_name(self, tool):
        node = next(n for _f, n in _tool_functions() if n.name == tool)
        params = _params(node)
        want = RENAMED_FROM_NAME[tool]
        assert want in params, f"{tool}{params} should take {want}"
        assert "name" not in params, f"{tool} still takes a bare name"

    @pytest.mark.parametrize("tool", sorted(RENAMED))
    def test_docstring_matches_the_signature(self, tool):
        """A renamed parameter with a stale docstring loses its schema description."""
        node = next(n for _f, n in _tool_functions() if n.name == tool)
        want = RENAMED_FROM_NAME[tool]
        assert want in _doc_args(node), f"{tool} docs still say 'name'"


class TestCreatorsUntouched:
    @pytest.mark.parametrize("tool", sorted(CREATORS))
    def test_creators_keep_name(self, tool):
        node = next((n for _f, n in _tool_functions() if n.name == tool), None)
        if node is None:
            pytest.skip(f"{tool} not present")
        assert "name" in _params(node), (
            f"{tool} names the thing it creates; that parameter stays `name`")


class TestNoRegression:
    def test_no_tool_takes_a_bare_name_for_an_existing_object(self):
        """The guard. A new tool must not reintroduce the old spelling.

        Heuristic: a tool whose `name` parameter is documented as "Name of the
        ..." refers to something that already exists. "Name for the ..." names
        something being created.
        """
        offenders = []
        for fname, node in _tool_functions():
            if "name" not in _params(node):
                continue
            doc = ast.get_docstring(node) or ""
            for line in doc.splitlines():
                s = line.strip()
                if not s.startswith("name:"):
                    continue
                text = s[len("name:"):].strip().lower()
                if text.startswith("name of the") and node.name not in CREATORS:
                    offenders.append(f"{fname}:{node.name}")
        assert not offenders, (
            "these reference an existing thing but take a bare `name`; use "
            f"object_name (or a typed *_name): {offenders}")


class TestAliasing:
    """The old spelling keeps working, and the schema advertises the new one."""

    @pytest.fixture(scope="class")
    def server(self):
        from blend_ai.server import mcp
        return mcp

    @pytest.mark.parametrize("tool", sorted(RENAMED))
    def test_schema_publishes_object_name(self, server, tool):
        model = server._tool_manager._tools[tool].fn_metadata.arg_model
        props = model.model_json_schema().get("properties", {})
        want = RENAMED_FROM_NAME[tool]
        assert want in props, f"{tool} schema shows {sorted(props)}"
        assert "name" not in props, f"{tool} schema still advertises `name`"

    @pytest.mark.parametrize("tool", sorted(RENAMED))
    def test_both_spellings_validate(self, server, tool):
        model = server._tool_manager._tools[tool].fn_metadata.arg_model
        required = [f for f, i in model.model_fields.items() if i.is_required()]
        filler = {
            "location": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1],
            "property": "energy", "value": 1.0,
        }
        canonical = RENAMED_FROM_NAME[tool]
        for spelling in (canonical, "name"):
            payload = {spelling: "Cube"}
            for f in required:
                if f != canonical:
                    payload[f] = filler.get(f, 1.0)
            model.model_validate(payload)   # must not raise

    def test_an_unknown_spelling_is_still_rejected(self, server):
        """strict.py must keep working: aliasing is not a licence for anything."""
        from pydantic import ValidationError
        model = server._tool_manager._tools["delete_object"].fn_metadata.arg_model
        with pytest.raises(ValidationError):
            model.model_validate({"obj_name": "Cube"})

    def test_creators_do_not_gain_the_alias(self, server):
        from pydantic import ValidationError
        model = server._tool_manager._tools["create_collection"].fn_metadata.arg_model
        model.model_validate({"name": "Things"})
        with pytest.raises(ValidationError):
            model.model_validate({"object_name": "Things"})
