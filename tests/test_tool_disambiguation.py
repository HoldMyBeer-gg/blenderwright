"""Overlapping tools name each other, so a client can pick the right one.

An MCP client chooses a tool by reading its description, nothing else. Where
two tools do nearby things (a boolean via modifier versus a destructive one,
a bare material versus a configured one, selecting objects versus selecting
faces on one object), a description that does not mention the sibling leaves
the client to guess. Glama scored this server 2/5 on disambiguation for
exactly those clusters.

The rule: every tool in a cluster names the siblings it is most easily
confused with, and no two tools in a cluster share a summary line.
"""

import ast
import pathlib

import pytest

TOOLS_DIR = pathlib.Path(__file__).parent.parent / "src" / "blenderwright" / "tools"

BOOLTOOL = {
    "booltool_auto_union", "booltool_auto_difference",
    "booltool_auto_intersect", "booltool_auto_slice",
}
MATERIAL_CREATORS = {
    "create_material", "create_principled_material", "create_procedural_material",
}
GEOMETRY_SELECTORS = {
    "select_all_geometry", "select_by_index", "select_by_axis",
    "select_similar", "select_faces_by_sides", "select_linked",
}

# tool -> siblings its docstring must name.
MUST_NAME = {
    "boolean_operation": BOOLTOOL,
    **{t: {"boolean_operation"} for t in BOOLTOOL},
    **{t: MATERIAL_CREATORS - {t} for t in MATERIAL_CREATORS},
    "select_objects": {"select_by_index", "select_by_axis"},
    **{t: {"select_objects"} for t in GEOMETRY_SELECTORS},
}

CLUSTERS = {
    "boolean": BOOLTOOL | {"boolean_operation"},
    "materials": MATERIAL_CREATORS,
    "selection": GEOMETRY_SELECTORS | {"select_objects"},
}


def _docstrings():
    out = {}
    for path in sorted(TOOLS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "tool"
                   for d in node.decorator_list):
                out[node.name] = ast.get_docstring(node) or ""
    return out


DOCS = _docstrings()


class TestClusterMembersExist:
    @pytest.mark.parametrize("tool", sorted(MUST_NAME))
    def test_tool_exists(self, tool):
        assert tool in DOCS, f"{tool} is not a registered tool"


class TestSiblingsNamed:
    @pytest.mark.parametrize(
        "tool,siblings", sorted((t, sorted(s)) for t, s in MUST_NAME.items())
    )
    def test_docstring_names_siblings(self, tool, siblings):
        doc = DOCS[tool]
        missing = [s for s in siblings if s not in doc]
        assert not missing, f"{tool} never mentions {missing}"


class TestSummaryLinesDistinct:
    @pytest.mark.parametrize("cluster", sorted(CLUSTERS))
    def test_first_lines_differ(self, cluster):
        first = {t: DOCS[t].splitlines()[0].strip() for t in CLUSTERS[cluster]}
        seen = {}
        for tool, line in first.items():
            assert line not in seen, (
                f"{tool} and {seen[line]} open with the same line: {line!r}"
            )
            seen[line] = tool
