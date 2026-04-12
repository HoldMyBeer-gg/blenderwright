#!/usr/bin/env python3
"""
Interactive installer for the blend-ai Blender addon.
Searches for Blender installations in the background while letting
you paste a path manually.

Requires: pip install textual
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal
    from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, RichLog
except ImportError:
    print("textual is required: pip install textual")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).parent.resolve()
MODULE_NAME = "blend_ai"


class BlenderRunningError(RuntimeError):
    """Raised when a destructive operation is attempted while Blender is running."""


# ---------------------------------------------------------------------------
# Blender discovery
# ---------------------------------------------------------------------------

def _blender_candidates() -> list[Path]:
    """Return candidate paths to check (may not exist yet)."""
    system = platform.system()
    candidates: list[Path | str] = []

    if system == "Windows":
        roots = list(dict.fromkeys(filter(None, [  # deduplicate while preserving order
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramW6432", r"C:\Program Files"),
            os.environ.get("LOCALAPPDATA", ""),
        ])))
        for root in roots:
            candidates += glob.glob(
                os.path.join(root, "Blender Foundation", "**", "blender.exe"),
                recursive=True,
            )
        # Steam
        steam = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / \
            "Steam" / "steamapps" / "common" / "Blender" / "blender.exe"
        candidates.append(steam)

    elif system == "Darwin":
        candidates += glob.glob("/Applications/Blender*.app/Contents/MacOS/Blender")
        candidates += glob.glob(
            str(Path.home() / "Applications" / "Blender*.app" / "Contents" / "MacOS" / "Blender")
        )
        candidates += [
            "/opt/homebrew/bin/blender",
            "/usr/local/bin/blender",
        ]

    else:  # Linux
        candidates += [
            "/usr/bin/blender",
            "/usr/local/bin/blender",
            "/snap/bin/blender",
        ]
        candidates += glob.glob(str(Path.home() / ".local" / "share" / "Steam" /
                                    "steamapps" / "common" / "Blender" / "blender"))
        # Flatpak — check if installed
        flatpak_app = Path.home() / ".local" / "share" / "flatpak" / "app" / "org.blender.Blender"
        system_flatpak = Path("/var/lib/flatpak/app/org.blender.Blender")
        if flatpak_app.exists() or system_flatpak.exists():
            candidates.append("flatpak run org.blender.Blender")

    return [Path(c) if not str(c).startswith("flatpak") else c for c in candidates]


async def _get_blender_version(blender: str | Path) -> str | None:
    """Run blender --version and return version string, or None on failure."""
    try:
        cmd = [str(blender), "--version"] if not str(blender).startswith("flatpak") \
              else str(blender).split() + ["--version"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=8)
        first_line = stdout.decode(errors="replace").splitlines()[0]
        return first_line.strip()  # e.g. "Blender 4.3.2"
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Build helper
# ---------------------------------------------------------------------------

def find_zip() -> Path | None:
    zips = sorted(SCRIPT_DIR.glob("blend-ai-v*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return zips[0] if zips else None


def _read_manifest_version(addon_dir: Path) -> str:
    """Extract `version = "X.Y.Z"` from blender_manifest.toml without tomllib (3.10 compat)."""
    manifest = addon_dir / "blender_manifest.toml"
    if not manifest.exists():
        return "0.0.0"
    match = re.search(
        r'^\s*version\s*=\s*"([^"]+)"',
        manifest.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return match.group(1) if match else "0.0.0"


def build_zip(log_fn) -> Path | None:
    """Build a Blender extension zip (flat layout, manifest at root).

    This intentionally does not shell out to `blender --command extension build`
    so that contributors without Blender installed can still run tests and build
    a zip. The layout matches what Blender's builder produces.
    """
    addon_dir = SCRIPT_DIR / "addon"
    if not addon_dir.exists():
        log_fn("[red]addon/ directory not found.[/red]")
        return None

    version = _read_manifest_version(addon_dir)
    output = SCRIPT_DIR / f"blend-ai-v{version}.zip"
    log_fn(f"Building addon zip v{version}...")

    import tempfile
    import zipfile

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "src"
        shutil.copytree(addon_dir, dest)
        for cache in dest.rglob("__pycache__"):
            shutil.rmtree(cache)
        for pyc in dest.rglob("*.pyc"):
            pyc.unlink()
        output.unlink(missing_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(dest.rglob("*")):
                if f.is_file():
                    zf.write(f, f.relative_to(dest))

    log_fn(f"Built: {output.name}")
    return output


# ---------------------------------------------------------------------------
# Install helper
# ---------------------------------------------------------------------------

INSTALL_SCRIPT = """
import bpy
import sys

zip_path = r'{zip_path}'
module   = '{module}'

# Install as a Blender Extension (4.2+). The user_default repo is the local
# sideload target; enable_on_install flips the checkbox as a single op.
try:
    bpy.ops.extensions.package_install_files(
        filepath=zip_path,
        repo='user_default',
        enable_on_install=True,
    )
    print('Installed extension:', zip_path)
except Exception as e:
    print('ERROR during package_install_files:', e)
    sys.exit(1)

bpy.ops.wm.save_userpref()
print('SUCCESS: blend_ai extension installed and preferences saved.')
"""


def install(blender: str | Path, zip_path: Path, log_fn) -> bool:
    script = INSTALL_SCRIPT.format(zip_path=str(zip_path).replace("\\", "\\\\"), module=MODULE_NAME)
    cmd = [str(blender), "--background", "--python-expr", script] \
        if not str(blender).startswith("flatpak") \
        else str(blender).split() + ["--background", "--python-expr", script]
    log_fn(f"Running: {' '.join(cmd[:2])} --background --python-expr ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout + result.stderr
    for line in output.splitlines():
        if line.strip():
            log_fn(line)
    return "SUCCESS:" in output


# ---------------------------------------------------------------------------
# Doctor / uninstall / upgrade — Extensions system aware
# ---------------------------------------------------------------------------

_VERSION_DIR_RE = re.compile(r"^\d+\.\d+$")


def blender_user_config_dirs() -> list[Path]:
    """Return per-OS root dir(s) under which Blender stores user config/versions.

    Each returned path contains X.Y subdirectories (4.2, 5.1, ...), each of
    which has `scripts/addons/` and/or `extensions/user_default/`.
    """
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return [home / "Library" / "Application Support" / "Blender"]
    if system == "Windows":
        appdata = os.environ.get("APPDATA", str(home / "AppData" / "Roaming"))
        return [Path(appdata) / "Blender Foundation" / "Blender"]
    # Linux and other Unix
    return [home / ".config" / "blender"]


def blender_version_dirs(root: Path) -> list[Path]:
    """Return X.Y version subdirectories under a Blender user config root."""
    if not root.exists() or not root.is_dir():
        return []
    out = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and _VERSION_DIR_RE.match(child.name):
            out.append(child)
    return out


def _looks_like_blend_ai(path: Path) -> bool:
    """Return True if a directory or file appears to belong to blend-ai.

    Checks (without following symlinks into the target for dir contents):
    - `blender_manifest.toml` containing `id = "blend_ai"` or `name = "blend-ai"`
    - `__init__.py` containing a `bl_info` with `name` == `blend-ai` / `blend_ai`
    """
    try:
        if path.is_file():
            if path.name == "__init__.py":
                text = path.read_text(encoding="utf-8", errors="replace")
                return "blend-ai" in text and "bl_info" in text
            if path.name == "blender_manifest.toml":
                text = path.read_text(encoding="utf-8", errors="replace")
                return 'id = "blend_ai"' in text or 'name = "blend-ai"' in text
            return False
        if path.is_dir():
            manifest = path / "blender_manifest.toml"
            if manifest.exists() and _looks_like_blend_ai(manifest):
                return True
            init = path / "__init__.py"
            if init.exists() and _looks_like_blend_ai(init):
                return True
    except OSError:
        return False
    return False


def find_blend_ai_installs(version_dir: Path) -> list[dict]:
    """Scan one Blender version dir for blend-ai leftovers.

    Returns a list of finding dicts with keys: path, kind, version.
    Kinds:
      - "legacy_dir"    — directory under scripts/addons/ identified as blend-ai
      - "extension_dir" — directory under extensions/user_default/ identified as blend-ai
      - "symlink"       — symlink (legacy dev install) identified as blend-ai without following
      - "orphan_file"   — loose file directly in scripts/addons/ from a botched install
    """
    findings: list[dict] = []
    version = version_dir.name

    addons_dir = version_dir / "scripts" / "addons"
    if addons_dir.exists():
        for entry in sorted(addons_dir.iterdir()):
            if entry.is_symlink():
                # Resolve target WITHOUT following for deletion; read target files
                # only to decide if it belongs to us.
                try:
                    target = entry.resolve()
                except OSError:
                    continue
                if target.exists() and _looks_like_blend_ai(target):
                    findings.append({
                        "path": entry,
                        "kind": "symlink",
                        "version": version,
                    })
                continue
            if entry.is_dir():
                if _looks_like_blend_ai(entry):
                    findings.append({
                        "path": entry,
                        "kind": "legacy_dir",
                        "version": version,
                    })
                continue
            # Loose file directly in addons/ — botched install artifact.
            if entry.is_file() and _looks_like_blend_ai(entry):
                findings.append({
                    "path": entry,
                    "kind": "orphan_file",
                    "version": version,
                })

    ext_dir = version_dir / "extensions" / "user_default"
    if ext_dir.exists():
        for entry in sorted(ext_dir.iterdir()):
            if entry.is_symlink():
                try:
                    target = entry.resolve()
                except OSError:
                    continue
                if target.exists() and _looks_like_blend_ai(target):
                    findings.append({
                        "path": entry,
                        "kind": "symlink",
                        "version": version,
                    })
                continue
            if entry.is_dir() and _looks_like_blend_ai(entry):
                findings.append({
                    "path": entry,
                    "kind": "extension_dir",
                    "version": version,
                })

    return findings


def is_blender_running() -> bool:
    """Return True if a Blender process is currently running on this machine."""
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq blender.exe"],
                capture_output=True, text=True, timeout=5,
            )
            return "blender.exe" in result.stdout.lower()
        # macOS and Linux
        result = subprocess.run(
            ["pgrep", "-xi", "blender"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def doctor() -> dict:
    """Scan every Blender version dir for blend-ai leftovers.

    Returns a dict with:
      - installs: list of finding dicts (see find_blend_ai_installs)
      - blender_running: bool
    """
    installs: list[dict] = []
    for root in blender_user_config_dirs():
        for vdir in blender_version_dirs(root):
            installs.extend(find_blend_ai_installs(vdir))
    return {"installs": installs, "blender_running": is_blender_running()}


def uninstall(dry_run: bool = True) -> list[dict]:
    """Remove every blend-ai leftover across all Blender versions.

    With dry_run=True (default), only returns what would be removed.
    With dry_run=False, actually removes them. Raises BlenderRunningError
    if Blender is currently running.
    """
    if not dry_run and is_blender_running():
        raise BlenderRunningError(
            "Blender is currently running. Quit Blender before running uninstall."
        )

    report = doctor()
    removed: list[dict] = []
    for finding in report["installs"]:
        path: Path = finding["path"]
        entry = {**finding, "removed": not dry_run}
        removed.append(entry)
        if dry_run:
            continue
        try:
            if path.is_symlink():
                # Never follow the link — just unlink.
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()
        except OSError as e:
            entry["error"] = str(e)
    return removed


def upgrade(blender: str | Path, zip_path: Path | None = None, log_fn=print) -> bool:
    """Uninstall everything, then install the given (or freshly built) zip."""
    if is_blender_running():
        raise BlenderRunningError(
            "Blender is currently running. Quit Blender before running upgrade."
        )
    uninstall(dry_run=False)
    if zip_path is None:
        zip_path = build_zip(log_fn) or find_zip()
        if zip_path is None:
            log_fn("No zip available to install.")
            return False
    return install(blender, zip_path, log_fn)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_doctor(_args) -> int:
    report = doctor()
    installs = report["installs"]
    if report["blender_running"]:
        print("Warning: Blender is currently running.")
    if not installs:
        print("No blend-ai installs found — system is clean.")
        return 0
    print(f"Found {len(installs)} blend-ai install(s):")
    for f in installs:
        print(f"  [{f['kind']}] {f['path']} (Blender {f['version']})")
    return 0


def _cmd_uninstall(args) -> int:
    dry_run = not args.yes
    try:
        removed = uninstall(dry_run=dry_run)
    except BlenderRunningError as e:
        print(f"error: {e}")
        return 2
    if not removed:
        print("Nothing to remove.")
        return 0
    verb = "Would remove" if dry_run else "Removed"
    for f in removed:
        print(f"  {verb}: [{f['kind']}] {f['path']}")
    if dry_run:
        print("(dry run) re-run with --yes to actually delete.")
    return 0


def _cmd_upgrade(args) -> int:
    try:
        ok = upgrade(args.blender, None, log_fn=print)
    except BlenderRunningError as e:
        print(f"error: {e}")
        return 2
    return 0 if ok else 1


def _cmd_install_tui(args) -> int:
    app = InstallerApp(preselected=args.blender)
    app.run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install_addon.py", description=__doc__)
    sub = parser.add_subparsers(dest="command")

    p_doctor = sub.add_parser("doctor", help="Scan for blend-ai installs and report")
    p_doctor.set_defaults(func=_cmd_doctor)

    p_uninstall = sub.add_parser("uninstall", help="Remove blend-ai from all Blender versions")
    p_uninstall.add_argument("--yes", action="store_true", help="Actually delete (default is dry run)")
    p_uninstall.set_defaults(func=_cmd_uninstall)

    p_upgrade = sub.add_parser("upgrade", help="Uninstall then install fresh")
    p_upgrade.add_argument("blender", help="Path to the Blender executable")
    p_upgrade.set_defaults(func=_cmd_upgrade)

    p_install = sub.add_parser("install", help="Interactive install via TUI")
    p_install.add_argument("blender", nargs="?", default=None)
    p_install.set_defaults(func=_cmd_install_tui)

    args = parser.parse_args(argv)
    if args.command is None:
        # Default: launch TUI (back-compat with `python install_addon.py`).
        preselected = sys.argv[1] if len(sys.argv) > 1 and argv is None else None
        InstallerApp(preselected=preselected).run()
        return 0
    return args.func(args)


# ---------------------------------------------------------------------------
# TUI
# ---------------------------------------------------------------------------

class InstallerApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    #found-label {
        padding: 1 2 0 2;
        color: $text-muted;
    }
    #found-list {
        height: auto;
        max-height: 10;
        margin: 0 2;
        border: solid $primary-darken-2;
    }
    #manual-label {
        padding: 1 2 0 2;
        color: $text-muted;
    }
    #path-input {
        margin: 0 2;
    }
    #btn-row {
        height: 3;
        margin: 1 2;
        align: center middle;
    }
    #install-btn {
        min-width: 16;
    }
    #log {
        margin: 0 2 1 2;
        height: 1fr;
        border: solid $primary-darken-2;
    }
    .found-item {
        padding: 0 1;
    }
    .found-item:hover {
        background: $primary-darken-1;
    }
    .found-item.--highlight {
        background: $primary;
    }
    #searching {
        padding: 0 2;
        color: $warning;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("enter", "install", "Install", show=False),
    ]

    def __init__(self, preselected: str | None = None):
        super().__init__()
        self._found: list[tuple[str | Path, str]] = []  # (path, label)
        self._preselected = preselected
        self._selected: str | Path | None = preselected
        self._searching = True

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label("Found Blender installations:", id="found-label")
        yield Label("  Searching...", id="searching")
        yield ListView(id="found-list")
        yield Label("Or paste Blender path:", id="manual-label")
        yield Input(placeholder="/path/to/blender  or  C:\\...\\blender.exe", id="path-input",
                    value=str(self._selected) if self._selected else "")
        with Horizontal(id="btn-row"):
            yield Button("Install", id="install-btn", variant="primary")
        yield RichLog(id="log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "blend-ai Addon Installer"
        self.sub_title = "Select a Blender install, then press Install"
        self.run_worker(self._search_blender(), exclusive=False)

    async def _search_blender(self) -> None:
        found_list = self.query_one("#found-list", ListView)
        searching = self.query_one("#searching", Label)

        candidates = list(dict.fromkeys(_blender_candidates()))  # deduplicate

        async def check(candidate):
            version = await _get_blender_version(candidate)
            if version:
                label = f"{candidate}  [{version}]"
                self._found.append((candidate, label))
                item = ListItem(Label(label, classes="found-item"))
                await found_list.append(item)
                if not self._selected and not self._preselected:
                    self._selected = candidate
                    self.query_one("#path-input", Input).value = str(candidate)

        await asyncio.gather(*[check(c) for c in candidates])

        self._searching = False
        searching.update("  " + (f"{len(self._found)} installation(s) found." if self._found
                                  else "No Blender found — paste path below."))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is not None and idx < len(self._found):
            path, _ = self._found[idx]
            self._selected = path
            self.query_one("#path-input", Input).value = str(path)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "path-input":
            self._selected = event.value.strip() or None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "install-btn":
            self.run_worker(self._do_install(), exclusive=True)

    async def _do_install(self) -> None:
        log = self.query_one("#log", RichLog)
        btn = self.query_one("#install-btn", Button)
        btn.disabled = True

        blender = self._selected
        if not blender:
            log.write("[red]No Blender path selected.[/red]")
            btn.disabled = False
            return

        log.write(f"[bold]Blender:[/bold] {blender}")

        zip_path = await asyncio.get_event_loop().run_in_executor(
            None, lambda: build_zip(log.write)
        )
        if not zip_path:
            log.write("[red]Could not find or build addon zip. Aborting.[/red]")
            btn.disabled = False
            return

        log.write(f"[bold]Zip:[/bold] {zip_path}")

        success = await asyncio.get_event_loop().run_in_executor(
            None, lambda: install(blender, zip_path, log.write)
        )

        if success:
            log.write("\n[bold green]Installation complete![/bold green]")
            self.sub_title = "Done — restart Blender if it was open."
        else:
            log.write("\n[bold red]Installation may have failed — check output above.[/bold red]")

        btn.label = "Done" if success else "Retry"
        btn.disabled = False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main() or 0)
