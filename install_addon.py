#!/usr/bin/env python3
"""
Interactive installer for the blend-ai Blender addon.
Searches for Blender installations in the background while letting
you paste a path manually.

Requires: pip install textual
"""

from __future__ import annotations

import asyncio
import glob
import os
import platform
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


def build_zip(log_fn) -> Path | None:
    build_script = SCRIPT_DIR / "build.sh"
    if not build_script.exists():
        log_fn("[red]build.sh not found — cannot build zip.[/red]")
        return None
    log_fn("Building addon zip...")
    result = subprocess.run(
        ["bash", str(build_script)],
        cwd=SCRIPT_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log_fn(f"[red]Build failed:[/red]\n{result.stderr}")
        return None
    log_fn(result.stdout.strip())
    return find_zip()


# ---------------------------------------------------------------------------
# Install helper
# ---------------------------------------------------------------------------

INSTALL_SCRIPT = """
import bpy, sys

zip_path = r'{zip_path}'
module   = '{module}'

addons = bpy.context.preferences.addons
if module in addons:
    bpy.ops.preferences.addon_disable(module=module)
    bpy.ops.preferences.addon_remove(module=module)
    print('Removed existing', module, 'addon.')

bpy.ops.preferences.addon_install(filepath=zip_path, overwrite=True)
print('Installed:', zip_path)

bpy.ops.preferences.addon_enable(module=module)
bpy.ops.wm.save_userpref()
print('SUCCESS: blend_ai enabled and preferences saved.')
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
    preselected = sys.argv[1] if len(sys.argv) > 1 else None
    app = InstallerApp(preselected=preselected)
    app.run()
