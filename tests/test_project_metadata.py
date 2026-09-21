"""Guard against the version and the documented tool count drifting.

The version lives in four places that nothing keeps in step: pyproject,
the extension manifest, bl_info, and the lockfile. A release tag builds
its zip from the manifest, so a bump that misses that file ships a zip
named after the previous release. The lockfile has already drifted once
this way.

The tool count is quoted in the README and in CLAUDE.md as a headline
number. Nothing recomputes it, so every tool added since it was written
has made it more wrong.
"""

import ast
import os
import re
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(ROOT, "src", "blend_ai", "tools")


def _read(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return f.read()


def _pyproject_version():
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        return tomllib.load(f)["project"]["version"]


def _manifest_version():
    with open(os.path.join(ROOT, "addon", "blender_manifest.toml"), "rb") as f:
        return tomllib.load(f)["version"]


def _bl_info_version():
    """bl_info holds the version as a tuple, e.g. (1, 3, 1)."""
    tree = ast.parse(_read("addon", "__init__.py"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "bl_info":
                    info = ast.literal_eval(node.value)
                    return ".".join(str(part) for part in info["version"])
    raise AssertionError("bl_info not found in addon/__init__.py")


def _lock_version():
    """The blend-ai entry in uv.lock, which uv regenerates from pyproject."""
    lock = _read("uv.lock")
    match = re.search(
        r'\[\[package\]\]\s*\nname = "blend-ai"\s*\nversion = "([^"]+)"', lock
    )
    assert match, "blend-ai package entry not found in uv.lock"
    return match.group(1)


def _tool_count():
    total = 0
    for filename in sorted(os.listdir(TOOLS_DIR)):
        if not filename.endswith(".py") or filename == "__init__.py":
            continue
        with open(os.path.join(TOOLS_DIR, filename)) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                func = decorator.func if isinstance(decorator, ast.Call) else decorator
                if isinstance(func, ast.Attribute) and func.attr == "tool":
                    total += 1
                    break
    return total


def test_version_is_consistent_across_all_declarations():
    versions = {
        "pyproject.toml": _pyproject_version(),
        "addon/blender_manifest.toml": _manifest_version(),
        "addon/__init__.py (bl_info)": _bl_info_version(),
        "uv.lock": _lock_version(),
    }
    assert len(set(versions.values())) == 1, (
        f"Version declarations disagree: {versions}. The release zip takes its "
        f"version from blender_manifest.toml, so a partial bump ships a "
        f"mislabelled asset."
    )


def test_readme_tool_count_matches_reality():
    actual = _tool_count()
    claimed = set(re.findall(r"(\d+) tools", _read("README.md")))
    assert claimed, "README no longer states a tool count"
    assert claimed == {str(actual)}, (
        f"README claims {sorted(claimed)} tools; the code defines {actual}. "
        f"Update every '<n> tools' in README.md."
    )


def test_readme_module_count_matches_reality():
    modules = [
        f for f in os.listdir(TOOLS_DIR)
        if f.endswith(".py") and f != "__init__.py"
    ]
    claimed = set(re.findall(r"(\d+) modules", _read("README.md")))
    assert claimed == {str(len(modules))}, (
        f"README claims {sorted(claimed)} modules; there are {len(modules)}."
    )
