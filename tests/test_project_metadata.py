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
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
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
        with open(os.path.join(TOOLS_DIR, filename), encoding="utf-8") as f:
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


def test_generated_tool_reference_is_current():
    """docs/index.html is generated; a stale copy misleads the public site.

    Regenerate with: python scripts/generate_tool_docs.py
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generate_tool_docs", os.path.join(ROOT, "scripts", "generate_tool_docs.py")
    )
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    target = os.path.join(ROOT, "docs", "index.html")
    assert os.path.exists(target), (
        "docs/index.html is missing. Run: python scripts/generate_tool_docs.py"
    )
    with open(target, encoding="utf-8") as f:
        committed = f.read()
    assert committed == gen.render(gen.collect_tools()), (
        "docs/index.html is out of date with the tools in src/. "
        "Run: python scripts/generate_tool_docs.py"
    )


def test_tool_reference_documents_every_tool():
    """Every tool must appear on the public page, not just the count."""
    import re

    with open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8") as f:
        page = f.read()
    anchors = set(re.findall(r'<article class="tool" id="([^"]+)"', page))
    assert len(anchors) == _tool_count()


def test_crawler_files_are_current():
    """robots.txt and sitemap.xml are generated alongside the page."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generate_tool_docs", os.path.join(ROOT, "scripts", "generate_tool_docs.py")
    )
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    for name, expected in (
        ("sitemap.xml", gen.render_sitemap()),
        ("robots.txt", gen.render_robots()),
    ):
        path = os.path.join(ROOT, "docs", name)
        assert os.path.exists(path), f"docs/{name} is missing"
        with open(path, encoding="utf-8") as f:
            assert f.read() == expected, (
                f"docs/{name} is out of date. "
                f"Run: python scripts/generate_tool_docs.py"
            )


def test_sitemap_matches_the_canonical_url():
    """A sitemap pointing somewhere else is worse than none."""
    import re

    with open(os.path.join(ROOT, "docs", "sitemap.xml"), encoding="utf-8") as f:
        loc = re.findall(r"<loc>([^<]+)</loc>", f.read())
    with open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8") as f:
        canonical = re.findall(r'rel="canonical" href="([^"]+)"', f.read())
    assert loc == canonical, f"sitemap {loc} disagrees with canonical {canonical}"


def test_mcp_dependency_excludes_the_breaking_major():
    """mcp 2.x renamed FastMCP, so an unbounded pin breaks fresh installs.

    server.py imports `from mcp.server.fastmcp import FastMCP`. That module
    does not exist in mcp 2.x, where it became MCPServer. The lockfile keeps
    this checkout on 1.26.0, but anyone following the README's
    `uv pip install -e .` resolves the newest mcp and cannot start blend-ai.
    """
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        deps = tomllib.load(f)["project"]["dependencies"]
    mcp_pin = next((d for d in deps if d.replace(" ", "").startswith("mcp")), None)
    assert mcp_pin, "mcp is no longer a declared dependency"
    assert "<2" in mcp_pin.replace(" ", ""), (
        f"mcp pin is {mcp_pin!r}, which allows mcp 2.x. FastMCP was renamed to "
        f"MCPServer there, so src/blend_ai/server.py cannot import."
    )


def test_server_still_imports_fastmcp_from_the_pinned_path():
    """If this import ever moves, the pin above can be relaxed deliberately."""
    assert "from mcp.server.fastmcp import FastMCP" in _read("src", "blend_ai", "server.py")


def test_ollama_chat_dependency_is_declared():
    """blend_ai.ollama_chat needs the ollama package; say so.

    The import is guarded and main() prints an install hint, but nothing in
    the project metadata asks for it, so a fresh checkout has no way to
    install it except by being told.
    """
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        extras = tomllib.load(f)["project"].get("optional-dependencies", {})
    declared = [d for group in extras.values() for d in group]
    assert any(d.replace(" ", "").startswith("ollama") for d in declared), (
        "src/blend_ai/ollama_chat.py imports ollama, but no extra provides it."
    )


def test_numeric_validation_results_are_not_discarded():
    """validate_numeric_range coerces, so throwing away its result loses that.

    A model sent value='0.85'. The validator accepted and converted it, the
    caller ignored the return, and the original string reached Blender:
    "NodeSocketFloatFactor.default_value expected a float type, not str".
    Calling it as a bare statement is now always a bug.
    """
    offenders = []
    for root, _, files in os.walk(os.path.join(ROOT, "src", "blend_ai")):
        for filename in sorted(files):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(root, filename)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
                    continue
                func = node.value.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                if name == "validate_numeric_range":
                    rel = os.path.relpath(path, ROOT)
                    offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        f"{len(offenders)} call(s) discard the coerced value, so a numeric "
        f"string is validated and then passed on unconverted: "
        f"{offenders[:5]}{'...' if len(offenders) > 5 else ''}"
    )


def test_dev_tools_are_in_a_group_uv_installs_by_default():
    """`uv run pytest` must use the project's pytest, not one from PATH.

    pytest lived only in the optional `dev` extra, which uv does not install,
    so the command fell through to the pyenv pytest. That interpreter had
    mcp 2.x, where FastMCP was renamed, so every test importing
    blend_ai.server errored and the failures looked unexplained and
    pre-existing.
    """
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        config = tomllib.load(f)
    groups = config.get("dependency-groups", {})
    assert "dev" in groups, (
        "no [dependency-groups] dev, so `uv run pytest` will not install pytest"
    )
    names = {d.split(">")[0].split("=")[0].split("[")[0].strip() for d in groups["dev"]}
    assert "pytest" in names


def test_the_dev_extra_still_exists_for_ci():
    """CI installs with pip, which does not read [dependency-groups]."""
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        config = tomllib.load(f)
    extras = config["project"].get("optional-dependencies", {})
    assert "dev" in extras, "CI's `pip install -e .[dev]` would break"


def test_the_two_dev_lists_agree():
    """Two lists of the same tools drift; pin them together."""
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        config = tomllib.load(f)
    extra = sorted(config["project"]["optional-dependencies"]["dev"])
    group = sorted(config["dependency-groups"]["dev"])
    assert extra == group, (
        f"the dev extra and the dev group differ: {set(extra) ^ set(group)}"
    )


def test_no_conftest_permanently_fakes_the_server_module():
    """A fake blend_ai.server in sys.modules makes results depend on import order.

    tests/test_tools/conftest.py used sys.modules.setdefault and never cleaned
    up, so the real registry was visible to some tests and not others, and
    fifteen collection errors in test_ollama_chat.py went unexplained for
    months. Nothing needs the fake; keep it that way.
    """
    import re
    for dirpath, _, filenames in os.walk(os.path.join(ROOT, "tests")):
        for filename in filenames:
            if filename != "conftest.py":
                continue
            path = os.path.join(dirpath, filename)
            with open(path, encoding="utf-8") as f:
                body = f.read()
            offending = re.findall(
                r"sys\.modules(?:\.setdefault\(|\[)\s*[\"']blend_ai\.server[\"']", body)
            assert not offending, (
                f"{os.path.relpath(path, ROOT)} installs a fake blend_ai.server "
                f"at collection; that makes test results depend on import order."
            )


def test_readme_domain_table_adds_up():
    """The per-domain table drifted to 172 while the code had 183.

    The headline count was already guarded, so it stayed right while the
    table under it quietly went wrong. Any number a human maintains by hand
    will do this; pin the total to the code.
    """
    import re
    readme = _read("README.md")
    block = re.search(r"All (\d+) tools.*?</details>", readme, re.S)
    assert block, "the tool table is gone"
    rows = [int(n) for n in re.findall(r"^\| [^|]+ \| (\d+) \|", block.group(0), re.M)]
    assert sum(rows) == _tool_count(), (
        f"the domain table sums to {sum(rows)}, but the code defines "
        f"{_tool_count()} tools"
    )
    assert int(block.group(1)) == _tool_count()
