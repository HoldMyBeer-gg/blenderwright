"""The installer's non-TUI commands must work without textual installed.

doctor, uninstall and upgrade use nothing but the standard library, but a
module-level `from textual... import` once made them unreachable: the import
failed and took the whole script with it, so the documented recovery commands
could not run on a machine that had never installed a TUI dependency.

tests/test_installer.py cannot catch that, because it skips itself entirely
when textual is missing. This module instead imports install_addon with
textual forcibly blocked, whether or not it is present in the environment.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

INSTALLER = Path(__file__).parent.parent / "install_addon.py"


class _BlockTextual:
    """Meta path finder that makes `import textual` fail."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "textual" or fullname.startswith("textual."):
            raise ImportError("textual is blocked for this test")
        return None


@pytest.fixture
def installer_without_textual():
    blocker = _BlockTextual()
    saved = {
        name: mod for name, mod in sys.modules.items()
        if name == "textual" or name.startswith("textual.")
    }
    for name in saved:
        del sys.modules[name]
    sys.modules.pop("install_addon_no_textual", None)
    sys.meta_path.insert(0, blocker)
    try:
        spec = importlib.util.spec_from_file_location(
            "install_addon_no_textual", INSTALLER
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.pop("install_addon_no_textual", None)
        sys.modules.update(saved)


def test_module_imports_without_textual(installer_without_textual):
    """Importing must not raise or call sys.exit."""
    assert installer_without_textual.TEXTUAL_AVAILABLE is False


def test_maintenance_functions_are_callable(installer_without_textual):
    """doctor/uninstall/upgrade are the documented recovery path."""
    mod = installer_without_textual
    for name in ("doctor", "uninstall", "upgrade", "is_blender_running"):
        assert callable(getattr(mod, name)), f"{name} unavailable without textual"


def test_doctor_runs_without_textual(installer_without_textual):
    report = installer_without_textual.doctor()
    assert set(report) == {"installs", "blender_running"}
    assert isinstance(report["installs"], list)


def test_uninstall_dry_run_touches_nothing(installer_without_textual):
    removed = installer_without_textual.uninstall(dry_run=True)
    assert all(entry["removed"] is False for entry in removed)


def test_tui_reports_missing_textual_instead_of_crashing(
    installer_without_textual, capsys
):
    mod = installer_without_textual
    args = type("Args", (), {"blender": None})()
    assert mod._cmd_install_tui(args) == 2
    out = capsys.readouterr().out
    assert "textual" in out
    assert "doctor" in out, "the message should point at the commands that do work"


def test_cli_subcommands_registered_without_textual(installer_without_textual):
    """argparse must still expose the maintenance commands."""
    mod = installer_without_textual
    with pytest.raises(SystemExit) as exc:
        mod.main(["--help"])
    assert exc.value.code == 0
