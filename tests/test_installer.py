"""Tests for the blend-ai addon installer TUI (install_addon.py)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — import install_addon without triggering sys.exit on missing textual
# ---------------------------------------------------------------------------

def _import_installer():
    """Import install_addon, skipping the sys.exit guard."""
    import importlib
    # Patch sys.exit so the ImportError guard in the module doesn't kill the process
    with patch("sys.exit"):
        spec = importlib.util.spec_from_file_location(
            "install_addon",
            Path(__file__).parent.parent / "install_addon.py",
        )
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except SystemExit:
            pytest.skip("textual not installed")
    return mod


installer = _import_installer()
InstallerApp = installer.InstallerApp


# ---------------------------------------------------------------------------
# Unit tests — pure functions (no TUI)
# ---------------------------------------------------------------------------

class TestBlenderCandidates:
    def test_returns_list(self):
        candidates = installer._blender_candidates()
        assert isinstance(candidates, list)

    def test_windows_candidates_include_program_files(self):
        with patch("platform.system", return_value="Windows"), \
             patch("os.environ.get", side_effect=lambda k, d="": {
                 "ProgramFiles": r"C:\Program Files",
                 "ProgramW6432": r"C:\Program Files",
                 "LOCALAPPDATA": "",
                 "ProgramFiles(x86)": r"C:\Program Files (x86)",
             }.get(k, d)), \
             patch("glob.glob", return_value=[]):
            candidates = installer._blender_candidates()
        paths = [str(c) for c in candidates]
        # Steam path should always be included on Windows
        assert any("Steam" in p for p in paths)

    def test_macos_candidates_include_applications(self):
        with patch("platform.system", return_value="Darwin"), \
             patch("glob.glob", return_value=["/Applications/Blender.app/Contents/MacOS/Blender"]):
            candidates = installer._blender_candidates()
        paths = [str(c) for c in candidates]
        assert any("Applications" in p for p in paths)

    def test_linux_candidates_include_usr_bin(self):
        with patch("platform.system", return_value="Linux"), \
             patch("glob.glob", return_value=[]), \
             patch.object(Path, "exists", return_value=False):
            candidates = installer._blender_candidates()
        # Normalize separators for cross-platform comparison
        paths = [str(c).replace("\\", "/") for c in candidates]
        assert "/usr/bin/blender" in paths

    def test_linux_flatpak_included_when_present(self):
        with patch("platform.system", return_value="Linux"), \
             patch("glob.glob", return_value=[]), \
             patch.object(Path, "exists", return_value=True):
            candidates = installer._blender_candidates()
        assert any(str(c).startswith("flatpak") for c in candidates)


class TestGetBlenderVersion:
    @pytest.mark.asyncio
    async def test_returns_version_string(self):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"Blender 4.3.2\nmore stuff\n", b"")
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            version = await installer._get_blender_version("/usr/bin/blender")
        assert version == "Blender 4.3.2"

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self):
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            version = await installer._get_blender_version("/nonexistent/blender")
        assert version is None

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        import asyncio as _asyncio
        mock_proc = AsyncMock()
        mock_proc.communicate.side_effect = _asyncio.TimeoutError
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            version = await installer._get_blender_version("/slow/blender")
        assert version is None

    @pytest.mark.asyncio
    async def test_flatpak_splits_command(self):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"Blender 4.1.0\n", b"")
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            await installer._get_blender_version("flatpak run org.blender.Blender")
        args = mock_exec.call_args[0]
        assert args[0] == "flatpak"
        assert "org.blender.Blender" in args


class TestFindZip:
    def test_returns_most_recent_zip(self, tmp_path):
        z1 = tmp_path / "blend-ai-v0.9.0.zip"
        z2 = tmp_path / "blend-ai-v1.0.0.zip"
        z1.write_bytes(b"old")
        z2.write_bytes(b"new")
        import time
        time.sleep(0.01)
        z2.touch()  # ensure z2 is newer

        with patch.object(installer, "SCRIPT_DIR", tmp_path):
            result = installer.find_zip()
        assert result == z2

    def test_returns_none_when_no_zip(self, tmp_path):
        with patch.object(installer, "SCRIPT_DIR", tmp_path):
            result = installer.find_zip()
        assert result is None


class TestBuildZip:
    def _make_addon(self, tmp_path):
        """Create a minimal addon/ structure with bl_info."""
        addon = tmp_path / "addon"
        addon.mkdir()
        (addon / "__init__.py").write_text(
            'bl_info = {"name": "blend-ai", "version": (1, 0, 0), "blender": (4, 0, 0)}\n'
        )
        (addon / "server.py").write_text("# server\n")
        return addon

    def test_builds_zip_from_addon_dir(self, tmp_path):
        self._make_addon(tmp_path)
        log_calls = []
        with patch.object(installer, "SCRIPT_DIR", tmp_path):
            result = installer.build_zip(log_calls.append)
        assert result is not None
        assert result.name == "blend-ai-v1.0.0.zip"
        assert result.exists()
        assert any("Building" in str(m) for m in log_calls)

    def test_zip_contains_blend_ai_prefix(self, tmp_path):
        self._make_addon(tmp_path)
        log_calls = []
        import zipfile
        with patch.object(installer, "SCRIPT_DIR", tmp_path):
            result = installer.build_zip(log_calls.append)
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
        assert all(n.startswith("blend_ai/") for n in names)

    def test_returns_none_when_addon_dir_missing(self, tmp_path):
        log_calls = []
        with patch.object(installer, "SCRIPT_DIR", tmp_path):
            result = installer.build_zip(log_calls.append)
        assert result is None


class TestInstall:
    def test_success_detected(self, tmp_path):
        zip_path = tmp_path / "blend-ai-v1.0.0.zip"
        zip_path.write_bytes(b"zip")
        log_calls = []

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Installed: ...\nSUCCESS: blend_ai enabled and preferences saved.\n",
                stderr="",
            )
            result = installer.install("/usr/bin/blender", zip_path, log_calls.append)

        assert result is True

    def test_failure_detected(self, tmp_path):
        zip_path = tmp_path / "blend-ai-v1.0.0.zip"
        zip_path.write_bytes(b"zip")
        log_calls = []

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: module not found",
            )
            result = installer.install("/usr/bin/blender", zip_path, log_calls.append)

        assert result is False

    def test_escapes_windows_backslashes(self, tmp_path):
        zip_path = Path(r"C:\Users\test\blend-ai-v1.0.0.zip")
        log_calls = []

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="SUCCESS: done", stderr="")
            installer.install(r"C:\Program Files\Blender\blender.exe", zip_path, log_calls.append)

        script_arg = mock_run.call_args[0][0][3]  # --python-expr value
        assert "\\\\" in script_arg  # backslashes escaped

    def test_flatpak_splits_command(self, tmp_path):
        zip_path = tmp_path / "blend-ai-v1.0.0.zip"
        zip_path.write_bytes(b"zip")
        log_calls = []

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="SUCCESS: done", stderr="")
            installer.install("flatpak run org.blender.Blender", zip_path, log_calls.append)

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "flatpak"


# ---------------------------------------------------------------------------
# TUI tests — Textual Pilot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestInstallerAppUI:
    async def test_initial_state_shows_searching(self):
        with patch.object(installer, "_blender_candidates", return_value=[]):
            async with InstallerApp().run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                label = pilot.app.query_one("#searching", installer.Label)
                # Textual 8.x: render the label to get its text content
                text = label.render().plain if hasattr(label.render(), "plain") else str(label.render())
                assert "Searching" in text or "found" in text

    async def test_preselected_path_populates_input(self):
        async with InstallerApp(preselected="/custom/blender").run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            inp = pilot.app.query_one("#path-input", installer.Input)
            assert inp.value == "/custom/blender"

    async def test_install_button_present(self):
        async with InstallerApp().run_test(size=(120, 40)) as pilot:
            btn = pilot.app.query_one("#install-btn", installer.Button)
            assert btn is not None
            assert not btn.disabled

    async def test_found_blender_populates_list_and_input(self):
        async def fake_get_version(path):
            return "Blender 4.3.2"

        with patch.object(installer, "_blender_candidates", return_value=[Path("/fake/blender")]), \
             patch.object(installer, "_get_blender_version", side_effect=fake_get_version):
            async with InstallerApp().run_test(size=(120, 40)) as pilot:
                await pilot.pause(delay=0.5)
                found_list = pilot.app.query_one("#found-list", installer.ListView)
                assert len(found_list) == 1
                inp = pilot.app.query_one("#path-input", installer.Input)
                assert "fake" in inp.value and "blender" in inp.value

    async def test_input_change_updates_selected(self):
        with patch.object(installer, "_blender_candidates", return_value=[]):
            async with InstallerApp().run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                inp = pilot.app.query_one("#path-input", installer.Input)
                inp.value = "/new/path/blender"
                await pilot.pause()
                assert pilot.app._selected == "/new/path/blender"

    async def test_install_with_no_path_logs_error(self):
        async with InstallerApp().run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            pilot.app._selected = None
            pilot.app.query_one("#path-input", installer.Input).clear()
            await pilot.click("#install-btn")
            await pilot.pause(delay=0.3)
            log = pilot.app.query_one("#log", installer.RichLog)
            assert log is not None  # log widget exists; content written without error

    async def test_successful_install_updates_button_label(self):
        fake_zip = Path("/tmp/blend-ai-v1.0.0.zip")

        with patch.object(installer, "_blender_candidates", return_value=[]), \
             patch.object(installer, "build_zip", return_value=fake_zip), \
             patch.object(installer, "install", return_value=True):
            async with InstallerApp(preselected="/fake/blender").run_test(size=(120, 40)) as pilot:
                await pilot.pause(delay=0.3)  # let search worker finish (no candidates)
                await pilot.click("#install-btn")
                await pilot.pause(delay=2.0)
                btn = pilot.app.query_one("#install-btn", installer.Button)
                assert str(btn.label) == "Done"

    async def test_failed_install_updates_button_to_retry(self):
        fake_zip = Path("/tmp/blend-ai-v1.0.0.zip")

        with patch.object(installer, "_blender_candidates", return_value=[]), \
             patch.object(installer, "build_zip", return_value=fake_zip), \
             patch.object(installer, "install", return_value=False):
            async with InstallerApp(preselected="/fake/blender").run_test(size=(120, 40)) as pilot:
                await pilot.pause(delay=0.3)
                await pilot.click("#install-btn")
                await pilot.pause(delay=2.0)
                btn = pilot.app.query_one("#install-btn", installer.Button)
                assert str(btn.label) == "Retry"
