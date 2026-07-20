"""Guard against handler modules that are imported but never registered.

addon/handlers/__init__.py keeps two lists: the import block and _modules.
A module present in the first but missing from the second imports cleanly and
registers nothing, so every tool it backs fails at runtime with
'Unknown command'. Nothing else in the suite catches that.
"""

import ast
import os

HANDLERS_INIT = os.path.join(
    os.path.dirname(__file__), "..", "..", "addon", "handlers", "__init__.py"
)
HANDLERS_DIR = os.path.dirname(HANDLERS_INIT)


def _parse():
    with open(HANDLERS_INIT) as f:
        return ast.parse(f.read())


def _imported_modules(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            names.update(alias.name for alias in node.names)
    return names


def _registered_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_modules":
                    return {
                        element.id
                        for element in node.value.elts
                        if isinstance(element, ast.Name)
                    }
    return set()


def test_every_imported_handler_is_registered():
    tree = _parse()
    missing = _imported_modules(tree) - _registered_modules(tree)
    assert not missing, (
        f"Handler modules imported but absent from _modules: {sorted(missing)}. "
        f"Their commands would fail with 'Unknown command' at runtime."
    )


def test_every_handler_file_is_imported():
    tree = _parse()
    on_disk = {
        f[:-3]
        for f in os.listdir(HANDLERS_DIR)
        if f.endswith(".py") and f != "__init__.py"
    }
    missing = on_disk - _imported_modules(tree)
    assert not missing, (
        f"Handler files on disk but never imported: {sorted(missing)}."
    )


def test_procedural_is_wired_up():
    tree = _parse()
    assert "procedural" in _imported_modules(tree)
    assert "procedural" in _registered_modules(tree)
