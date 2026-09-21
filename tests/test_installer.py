"""Tests for the blend-ai addon installer (install_addon.py)."""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_installer():
    """Import install_addon by path; it is a script, not a package module."""
    spec = importlib.util.spec_from_file_location(
        "install_addon",
        Path(__file__).parent.parent / "install_addon.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


installer = _import_installer()


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
        """Create a minimal addon/ structure matching a Blender extension layout."""
        addon = tmp_path / "addon"
        addon.mkdir()
        (addon / "blender_manifest.toml").write_text(
            'schema_version = "1.0.0"\n'
            'id = "blend_ai"\n'
            'version = "1.0.0"\n'
            'name = "blend-ai"\n'
            'type = "add-on"\n'
        )
        (addon / "__init__.py").write_text(
            'bl_info = {"name": "blend-ai", "version": (1, 0, 0), "blender": (4, 2, 0)}\n'
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

    def test_zip_is_flat_extension_layout(self, tmp_path):
        """Extension zips put blender_manifest.toml at the root, not nested."""
        self._make_addon(tmp_path)
        import zipfile
        with patch.object(installer, "SCRIPT_DIR", tmp_path):
            result = installer.build_zip(lambda m: None)
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
        assert "blender_manifest.toml" in names
        assert not any(n.startswith("blend_ai/") for n in names)
        assert not any(n.startswith("addon/") for n in names)

    def test_zip_excludes_pycache(self, tmp_path):
        addon = self._make_addon(tmp_path)
        cache = addon / "__pycache__"
        cache.mkdir()
        (cache / "server.cpython-313.pyc").write_bytes(b"\x00")
        import zipfile
        with patch.object(installer, "SCRIPT_DIR", tmp_path):
            result = installer.build_zip(lambda m: None)
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
        assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)

    def test_reads_version_from_manifest(self, tmp_path):
        addon = tmp_path / "addon"
        addon.mkdir()
        (addon / "blender_manifest.toml").write_text(
            'schema_version = "1.0.0"\n'
            'id = "blend_ai"\n'
            'version = "2.3.4"\n'
            'name = "blend-ai"\n'
            'type = "add-on"\n'
        )
        with patch.object(installer, "SCRIPT_DIR", tmp_path):
            result = installer.build_zip(lambda m: None)
        assert result.name == "blend-ai-v2.3.4.zip"

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

class TestBlenderUserConfigDirs:
    """blender_user_config_dirs() returns per-OS user config root(s)."""

    def test_macos_points_at_application_support(self):
        with patch("platform.system", return_value="Darwin"):
            dirs = installer.blender_user_config_dirs()
        # Check by path parts to be independent of OS separator
        assert any(
            "Application Support" in d.parts and "Blender" in d.parts for d in dirs
        )

    def test_linux_points_at_dot_config(self):
        with patch("platform.system", return_value="Linux"):
            dirs = installer.blender_user_config_dirs()
        assert any(".config" in d.parts and "blender" in d.parts for d in dirs)

    def test_windows_points_at_appdata(self):
        with patch("platform.system", return_value="Windows"), \
             patch.dict("os.environ", {"APPDATA": r"C:\Users\test\AppData\Roaming"}):
            dirs = installer.blender_user_config_dirs()
        assert any("Blender Foundation" in str(d) for d in dirs)


class TestBlenderVersionDirs:
    """blender_version_dirs(root) finds X.Y version subdirs."""

    def test_finds_version_subdirs(self, tmp_path):
        (tmp_path / "4.2").mkdir()
        (tmp_path / "5.1").mkdir()
        result = installer.blender_version_dirs(tmp_path)
        names = sorted(d.name for d in result)
        assert names == ["4.2", "5.1"]

    def test_ignores_non_version_names(self, tmp_path):
        (tmp_path / "4.2").mkdir()
        (tmp_path / "notes").mkdir()
        (tmp_path / "README.md").write_text("x")
        result = installer.blender_version_dirs(tmp_path)
        assert [d.name for d in result] == ["4.2"]

    def test_returns_empty_for_missing_root(self, tmp_path):
        result = installer.blender_version_dirs(tmp_path / "nope")
        assert result == []


class TestFindBlendAiInstalls:
    """find_blend_ai_installs(version_dir) returns leftover findings."""

    def _mk_version_dir(self, tmp_path):
        vdir = tmp_path / "5.1"
        (vdir / "scripts" / "addons").mkdir(parents=True)
        (vdir / "extensions" / "user_default").mkdir(parents=True)
        return vdir

    def test_clean_version_dir_returns_empty(self, tmp_path):
        vdir = self._mk_version_dir(tmp_path)
        assert installer.find_blend_ai_installs(vdir) == []

    def test_detects_legacy_blend_ai_directory(self, tmp_path):
        vdir = self._mk_version_dir(tmp_path)
        target = vdir / "scripts" / "addons" / "blend_ai"
        target.mkdir()
        (target / "__init__.py").write_text(
            'bl_info = {"name": "blend-ai", "version": (1, 0, 0)}\n'
        )
        found = installer.find_blend_ai_installs(vdir)
        assert len(found) == 1
        assert found[0]["kind"] == "legacy_dir"
        assert found[0]["path"] == target

    def test_detects_extension_user_default_directory(self, tmp_path):
        vdir = self._mk_version_dir(tmp_path)
        target = vdir / "extensions" / "user_default" / "blend_ai"
        target.mkdir()
        (target / "blender_manifest.toml").write_text('id = "blend_ai"\nname = "blend-ai"\n')
        found = installer.find_blend_ai_installs(vdir)
        assert len(found) == 1
        assert found[0]["kind"] == "extension_dir"
        assert found[0]["path"] == target

    @pytest.mark.skipif(
        __import__("sys").platform == "win32",
        reason="Windows requires admin/developer mode for symlinks",
    )
    def test_detects_legacy_symlink_without_following(self, tmp_path):
        vdir = self._mk_version_dir(tmp_path)
        real = tmp_path / "real_source"
        real.mkdir()
        (real / "__init__.py").write_text(
            'bl_info = {"name": "blend-ai", "version": (1, 0, 0)}\n'
        )
        link = vdir / "scripts" / "addons" / "blend_ai"
        link.symlink_to(real)
        found = installer.find_blend_ai_installs(vdir)
        assert len(found) == 1
        assert found[0]["kind"] == "symlink"
        assert found[0]["path"] == link

    def test_identifies_folder_by_manifest_id_regardless_of_name(self, tmp_path):
        vdir = self._mk_version_dir(tmp_path)
        target = vdir / "scripts" / "addons" / "addon"  # wrong name
        target.mkdir()
        (target / "__init__.py").write_text(
            'bl_info = {"name": "blend-ai", "version": (1, 0, 0)}\n'
        )
        found = installer.find_blend_ai_installs(vdir)
        assert len(found) == 1
        assert found[0]["kind"] == "legacy_dir"

    def test_ignores_unrelated_addon_dir(self, tmp_path):
        vdir = self._mk_version_dir(tmp_path)
        other = vdir / "scripts" / "addons" / "some_other_addon"
        other.mkdir()
        (other / "__init__.py").write_text('bl_info = {"name": "other"}\n')
        assert installer.find_blend_ai_installs(vdir) == []

    def test_detects_orphan_top_level_init(self, tmp_path):
        vdir = self._mk_version_dir(tmp_path)
        orphan = vdir / "scripts" / "addons" / "__init__.py"
        orphan.write_text('bl_info = {"name": "blend-ai"}\n')
        found = installer.find_blend_ai_installs(vdir)
        assert len(found) == 1
        assert found[0]["kind"] == "orphan_file"
        assert found[0]["path"] == orphan


class TestIsBlenderRunning:
    def test_returns_false_when_process_absent(self):
        with patch("platform.system", return_value="Darwin"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
            assert installer.is_blender_running() is False

    def test_returns_true_when_process_present_unix(self):
        with patch("platform.system", return_value="Darwin"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="12345\n", stderr="")
            assert installer.is_blender_running() is True

    def test_returns_true_when_process_present_windows(self):
        tasklist_out = (
            'Image Name                     PID\r\n'
            '========================= ========\r\n'
            'blender.exe                   1234\r\n'
        )
        with patch("platform.system", return_value="Windows"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=tasklist_out, stderr="")
            assert installer.is_blender_running() is True

    def test_returns_false_on_windows_when_absent(self):
        with patch("platform.system", return_value="Windows"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='INFO: No tasks are running which match the specified criteria.\r\n',
                stderr="",
            )
            assert installer.is_blender_running() is False


class TestDoctor:
    def test_returns_report_with_expected_keys(self, tmp_path):
        with patch.object(installer, "blender_user_config_dirs", return_value=[tmp_path]), \
             patch.object(installer, "is_blender_running", return_value=False):
            report = installer.doctor()
        assert "installs" in report
        assert "blender_running" in report
        assert report["blender_running"] is False
        assert report["installs"] == []

    def test_scans_every_version_dir(self, tmp_path):
        root = tmp_path / "Blender"
        (root / "4.2" / "scripts" / "addons" / "blend_ai").mkdir(parents=True)
        (root / "4.2" / "scripts" / "addons" / "blend_ai" / "__init__.py").write_text(
            'bl_info = {"name": "blend-ai"}\n'
        )
        (root / "5.1" / "extensions" / "user_default" / "blend_ai").mkdir(parents=True)
        (root / "5.1" / "extensions" / "user_default" / "blend_ai" / "blender_manifest.toml").write_text(
            'id = "blend_ai"\n'
        )
        with patch.object(installer, "blender_user_config_dirs", return_value=[root]), \
             patch.object(installer, "is_blender_running", return_value=False):
            report = installer.doctor()
        kinds = sorted(f["kind"] for f in report["installs"])
        assert kinds == ["extension_dir", "legacy_dir"]


class TestUninstall:
    def _seed_leftovers(self, tmp_path):
        root = tmp_path / "Blender"
        legacy = root / "5.1" / "scripts" / "addons" / "blend_ai"
        legacy.mkdir(parents=True)
        (legacy / "__init__.py").write_text('bl_info = {"name": "blend-ai"}\n')
        ext = root / "5.1" / "extensions" / "user_default" / "blend_ai"
        ext.mkdir(parents=True)
        (ext / "blender_manifest.toml").write_text('id = "blend_ai"\n')
        return root, legacy, ext

    def test_dry_run_leaves_files_in_place(self, tmp_path):
        root, legacy, ext = self._seed_leftovers(tmp_path)
        with patch.object(installer, "blender_user_config_dirs", return_value=[root]), \
             patch.object(installer, "is_blender_running", return_value=False):
            report = installer.uninstall(dry_run=True)
        assert legacy.exists()
        assert ext.exists()
        assert len(report) == 2

    def test_force_deletes_findings(self, tmp_path):
        root, legacy, ext = self._seed_leftovers(tmp_path)
        with patch.object(installer, "blender_user_config_dirs", return_value=[root]), \
             patch.object(installer, "is_blender_running", return_value=False):
            installer.uninstall(dry_run=False)
        assert not legacy.exists()
        assert not ext.exists()

    @pytest.mark.skipif(
        __import__("sys").platform == "win32",
        reason="Windows requires admin/developer mode for symlinks",
    )
    def test_unlinks_symlink_without_deleting_target(self, tmp_path):
        root = tmp_path / "Blender"
        addons = root / "5.1" / "scripts" / "addons"
        addons.mkdir(parents=True)
        real = tmp_path / "real_source"
        real.mkdir()
        (real / "__init__.py").write_text('bl_info = {"name": "blend-ai"}\n')
        link = addons / "blend_ai"
        link.symlink_to(real)

        with patch.object(installer, "blender_user_config_dirs", return_value=[root]), \
             patch.object(installer, "is_blender_running", return_value=False):
            installer.uninstall(dry_run=False)

        assert not link.exists()
        assert real.exists()
        assert (real / "__init__.py").exists()

    def test_refuses_when_blender_running(self, tmp_path):
        with patch.object(installer, "blender_user_config_dirs", return_value=[tmp_path]), \
             patch.object(installer, "is_blender_running", return_value=True):
            with pytest.raises(installer.BlenderRunningError):
                installer.uninstall(dry_run=False)


def _fake_blender(tmp_path):
    """A real executable file, so validate_blender_path accepts it."""
    exe = tmp_path / "blender"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    return exe


class TestUpgrade:
    def test_upgrade_calls_uninstall_then_install(self, tmp_path):
        zip_path = tmp_path / "blend-ai-v1.0.0.zip"
        zip_path.write_bytes(b"zip")
        calls = []
        with patch.object(installer, "is_blender_running", return_value=False), \
             patch.object(installer, "uninstall", side_effect=lambda dry_run=False: calls.append("uninstall") or []), \
             patch.object(installer, "install", side_effect=lambda *a, **kw: calls.append("install") or True):
            installer.upgrade(_fake_blender(tmp_path), zip_path, log_fn=lambda m: None)
        assert calls == ["uninstall", "install"]

    def test_upgrade_refuses_when_blender_running(self, tmp_path):
        zip_path = tmp_path / "blend-ai-v1.0.0.zip"
        zip_path.write_bytes(b"zip")
        with patch.object(installer, "is_blender_running", return_value=True):
            with pytest.raises(installer.BlenderRunningError):
                installer.upgrade("/usr/bin/blender", zip_path, log_fn=lambda m: None)


class TestExtensionsInstallTarget:
    """Install script must target the 4.2+ Extensions system, not legacy addons."""

    def test_install_script_uses_package_install_files(self):
        assert "bpy.ops.extensions.package_install_files" in installer.INSTALL_SCRIPT

    def test_install_script_uses_user_default_repo(self):
        assert "user_default" in installer.INSTALL_SCRIPT


class TestCliSubcommands:
    """install_addon.py must expose doctor/install/uninstall/upgrade on the CLI."""

    def test_doctor_subcommand_prints_report(self, capsys):
        with patch.object(installer, "doctor", return_value={"installs": [], "blender_running": False}):
            installer.main(["doctor"])
        out = capsys.readouterr().out
        assert "blend-ai" in out.lower() or "clean" in out.lower() or "no " in out.lower()

    def test_uninstall_subcommand_calls_uninstall(self):
        with patch.object(installer, "uninstall", return_value=[]) as mock_u, \
             patch.object(installer, "is_blender_running", return_value=False):
            installer.main(["uninstall", "--yes"])
        mock_u.assert_called_once()
        assert mock_u.call_args.kwargs.get("dry_run") is False

    def test_uninstall_without_yes_uses_dry_run(self):
        with patch.object(installer, "uninstall", return_value=[]) as mock_u, \
             patch.object(installer, "is_blender_running", return_value=False):
            installer.main(["uninstall"])
        assert mock_u.call_args.kwargs.get("dry_run") is True


# ---------------------------------------------------------------------------
# Plain-text Blender picker (replaces the former textual TUI)
# ---------------------------------------------------------------------------

class TestChooseBlender:
    def test_preselected_path_short_circuits_discovery(self):
        with patch.object(installer, "_discover_blender") as discover:
            assert installer._choose_blender("/given/blender") == "/given/blender"
        discover.assert_not_called()

    def test_numeric_choice_selects_from_the_list(self):
        found = [(Path("/a/blender"), "Blender 4.2.0"), (Path("/b/blender"), "Blender 5.1.0")]
        with patch.object(installer, "_discover_blender", return_value=found), \
             patch("builtins.input", return_value="2"):
            assert installer._choose_blender() == Path("/b/blender")

    def test_pasted_path_is_accepted_over_the_list(self):
        found = [(Path("/a/blender"), "Blender 4.2.0")]
        with patch.object(installer, "_discover_blender", return_value=found), \
             patch("builtins.input", return_value="/elsewhere/blender"):
            assert installer._choose_blender() == "/elsewhere/blender"

    def test_blank_answer_cancels(self):
        found = [(Path("/a/blender"), "Blender 4.2.0")]
        with patch.object(installer, "_discover_blender", return_value=found), \
             patch("builtins.input", return_value=""):
            assert installer._choose_blender() is None

    def test_out_of_range_number_is_treated_as_a_path(self):
        """9 with one result is not a selection; don't silently install the wrong one."""
        found = [(Path("/a/blender"), "Blender 4.2.0")]
        with patch.object(installer, "_discover_blender", return_value=found), \
             patch("builtins.input", return_value="9"):
            assert installer._choose_blender() == "9"

    def test_no_blender_found_prompts_for_a_path(self):
        with patch.object(installer, "_discover_blender", return_value=[]), \
             patch("builtins.input", return_value="/typed/blender"):
            assert installer._choose_blender() == "/typed/blender"

    def test_no_blender_found_and_blank_cancels(self):
        with patch.object(installer, "_discover_blender", return_value=[]), \
             patch("builtins.input", return_value=""):
            assert installer._choose_blender() is None


class TestCmdInstall:
    def test_cancelled_choice_does_not_install(self):
        args = MagicMock(blender=None)
        with patch.object(installer, "_choose_blender", return_value=None), \
             patch.object(installer, "install") as inst:
            assert installer._cmd_install(args) == 1
        inst.assert_not_called()

    def test_missing_zip_is_reported(self, tmp_path):
        exe = _fake_blender(tmp_path)
        args = MagicMock(blender=str(exe))
        with patch.object(installer, "_choose_blender", return_value=exe), \
             patch.object(installer, "build_zip", return_value=None), \
             patch.object(installer, "find_zip", return_value=None), \
             patch.object(installer, "install") as inst:
            assert installer._cmd_install(args) == 1
        inst.assert_not_called()

    def test_successful_install_returns_zero(self, tmp_path):
        exe = _fake_blender(tmp_path)
        args = MagicMock(blender=str(exe))
        with patch.object(installer, "_choose_blender", return_value=exe), \
             patch.object(installer, "build_zip", return_value=Path("/tmp/x.zip")), \
             patch.object(installer, "install", return_value=True):
            assert installer._cmd_install(args) == 0

    def test_failed_install_returns_nonzero(self, tmp_path):
        exe = _fake_blender(tmp_path)
        args = MagicMock(blender=str(exe))
        with patch.object(installer, "_choose_blender", return_value=exe), \
             patch.object(installer, "build_zip", return_value=Path("/tmp/x.zip")), \
             patch.object(installer, "install", return_value=False):
            assert installer._cmd_install(args) == 1


class TestNoThirdPartyDependencies:
    def test_installer_imports_only_stdlib(self):
        """The installer must run on a bare interpreter."""
        import ast
        source = (Path(__file__).parent.parent / "install_addon.py").read_text()
        roots = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
        assert "textual" not in roots
        assert roots <= set(sys.stdlib_module_names), (
            f"non-stdlib imports in install_addon.py: "
            f"{sorted(roots - set(sys.stdlib_module_names))}"
        )


# ---------------------------------------------------------------------------
# Blender path validation
# ---------------------------------------------------------------------------

class TestValidateBlenderPath:
    def test_accepts_an_executable_file(self, tmp_path):
        exe = tmp_path / "blender"
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        assert installer.validate_blender_path(exe) == exe

    def test_app_bundle_gets_a_macos_hint(self, tmp_path):
        """The natural thing to type on macOS is the .app, which is a directory."""
        app = tmp_path / "Blender.app"
        app.mkdir()
        with pytest.raises(installer.BlenderPathError) as exc:
            installer.validate_blender_path(app)
        assert "Contents/MacOS/Blender" in str(exc.value)

    def test_plain_directory_is_rejected(self, tmp_path):
        with pytest.raises(installer.BlenderPathError):
            installer.validate_blender_path(tmp_path)

    def test_missing_path_is_rejected(self, tmp_path):
        with pytest.raises(installer.BlenderPathError) as exc:
            installer.validate_blender_path(tmp_path / "nope")
        assert "not found" in str(exc.value).lower()

    @pytest.mark.skipif(os.name == "nt", reason="Windows has no executable bit")
    def test_non_executable_file_is_rejected(self, tmp_path):
        f = tmp_path / "blender"
        f.write_text("")
        f.chmod(0o644)
        with pytest.raises(installer.BlenderPathError):
            installer.validate_blender_path(f)

    def test_flatpak_invocation_is_passed_through(self):
        """install() special-cases flatpak; validation must not block it."""
        cmd = "flatpak run org.blender.Blender"
        assert installer.validate_blender_path(cmd) == cmd


class TestUpgradeDoesNotDestroyOnBadPath:
    def test_bad_path_aborts_before_uninstalling(self, tmp_path):
        """The addon must survive a typo; uninstall runs before install."""
        bad = tmp_path / "Blender.app"
        bad.mkdir()
        with patch.object(installer, "is_blender_running", return_value=False), \
             patch.object(installer, "uninstall") as uninst, \
             patch.object(installer, "install") as inst:
            with pytest.raises(installer.BlenderPathError):
                installer.upgrade(bad)
        uninst.assert_not_called()
        inst.assert_not_called()

    def test_good_path_still_uninstalls_then_installs(self, tmp_path):
        exe = tmp_path / "blender"
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        with patch.object(installer, "is_blender_running", return_value=False), \
             patch.object(installer, "uninstall") as uninst, \
             patch.object(installer, "build_zip", return_value=tmp_path / "x.zip"), \
             patch.object(installer, "install", return_value=True) as inst:
            assert installer.upgrade(exe) is True
        uninst.assert_called_once()
        inst.assert_called_once()


class TestUpgradeWithoutAPath:
    def test_no_path_falls_back_to_the_picker(self, tmp_path):
        exe = tmp_path / "blender"
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        args = MagicMock(blender=None)
        with patch.object(installer, "_choose_blender", return_value=exe) as choose, \
             patch.object(installer, "upgrade", return_value=True):
            assert installer._cmd_upgrade(args) == 0
        choose.assert_called_once()

    def test_cancelled_picker_does_not_uninstall(self):
        args = MagicMock(blender=None)
        with patch.object(installer, "_choose_blender", return_value=None), \
             patch.object(installer, "uninstall") as uninst:
            assert installer._cmd_upgrade(args) != 0
        uninst.assert_not_called()
