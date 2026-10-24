"""Socket auth token: where it lives, who can read it, and that both ends agree.

The addon writes a fresh random token when its server starts; the MCP server
reads it and sends it with every command. Any local process can reach the
port, but only the user can read the file.
"""

import importlib.util
import os
import stat
import sys

import pytest

from blenderwright import connection as client_auth

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")


def _load_addon_auth():
    path = os.path.join(os.path.dirname(__file__), "..", "addon", "auth.py")
    spec = importlib.util.spec_from_file_location("addon_auth_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def addon_auth():
    return _load_addon_auth()


class TestTokenPath:
    def test_env_override_wins(self, addon_auth, tmp_path, monkeypatch):
        monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(tmp_path / "t"))
        assert addon_auth.token_path() == str(tmp_path / "t")
        assert client_auth.token_path() == str(tmp_path / "t")

    @pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
    def test_both_ends_agree_without_override(self, addon_auth, monkeypatch, tmp_path, platform):
        monkeypatch.delenv("BLENDERWRIGHT_TOKEN_FILE", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(addon_auth.sys, "platform", platform)
        monkeypatch.setattr(client_auth.sys, "platform", platform)
        assert addon_auth.token_path() == client_auth.token_path()
        assert addon_auth.token_path().endswith(os.path.join("blenderwright", "token"))


class TestWriteToken:
    def test_new_token_is_long_and_random(self, addon_auth):
        a, b = addon_auth.new_token(), addon_auth.new_token()
        assert a != b
        assert len(a) >= 64

    def test_file_is_private_to_the_user(self, addon_auth, tmp_path, monkeypatch):
        path = tmp_path / "cfg" / "blenderwright" / "token"
        monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(path))
        addon_auth.write_token("secret")

        assert path.read_text() == "secret"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700

    def test_replaces_a_world_readable_file(self, addon_auth, tmp_path, monkeypatch):
        path = tmp_path / "token"
        path.write_text("old")
        path.chmod(0o644)
        monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(path))

        addon_auth.write_token("new")

        assert path.read_text() == "new"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_clear_removes_the_file(self, addon_auth, tmp_path, monkeypatch):
        path = tmp_path / "token"
        monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(path))
        addon_auth.write_token("secret")
        addon_auth.clear_token()
        assert not path.exists()
        addon_auth.clear_token()  # already gone is fine


class TestReadToken:
    def test_reads_what_the_addon_wrote(self, addon_auth):
        addon_auth.write_token("shared")
        assert client_auth.read_token() == "shared"

    def test_missing_file_fails_loud_with_the_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(tmp_path / "nope"))
        with pytest.raises(client_auth.BlenderAuthError, match="nope"):
            client_auth.read_token()
