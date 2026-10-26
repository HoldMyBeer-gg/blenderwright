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


class TestOneTokenPerPort:
    """Two Blenders on two ports must not overwrite each other's token. 9876
    keeps the plain name, so a default setup and older clients see no change."""

    @pytest.fixture
    def home(self, addon_auth, monkeypatch, tmp_path):
        monkeypatch.delenv("BLENDERWRIGHT_TOKEN_FILE", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(addon_auth.sys, "platform", "darwin")
        monkeypatch.setattr(client_auth.sys, "platform", "darwin")
        return tmp_path

    def test_default_port_keeps_the_plain_name(self, addon_auth, home):
        assert addon_auth.token_path(9876).endswith(os.path.join("blenderwright", "token"))
        assert addon_auth.token_path() == addon_auth.token_path(9876)

    def test_other_ports_get_their_own_file(self, addon_auth, home):
        assert addon_auth.token_path(9877).endswith(os.path.join("blenderwright", "token-9877"))
        assert client_auth.token_path(9877) == addon_auth.token_path(9877)

    def test_tokens_do_not_collide(self, addon_auth, home):
        addon_auth.write_token("first", 9876)
        addon_auth.write_token("second", 9877)
        assert client_auth.read_token(9876) == "first"
        assert client_auth.read_token(9877) == "second"
        addon_auth.clear_token(9877)
        assert client_auth.read_token(9876) == "first"

    def test_override_wins_for_any_port(self, addon_auth, monkeypatch, tmp_path):
        monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(tmp_path / "t"))
        assert addon_auth.token_path(9877) == client_auth.token_path(9877) == str(tmp_path / "t")


class TestClientPort:
    def test_default_port(self, monkeypatch):
        monkeypatch.delenv("BLENDERWRIGHT_PORT", raising=False)
        assert client_auth.configured_port() == 9876

    def test_env_picks_another_blender(self, monkeypatch):
        monkeypatch.setenv("BLENDERWRIGHT_PORT", "9877")
        assert client_auth.configured_port() == 9877

    @pytest.mark.parametrize("bad", ["80", "70000", "abc", "9876; rm"])
    def test_bad_port_fails_loud(self, monkeypatch, bad):
        monkeypatch.setenv("BLENDERWRIGHT_PORT", bad)
        with pytest.raises(client_auth.BlenderConnectionError, match="BLENDERWRIGHT_PORT"):
            client_auth.configured_port()


class TestWriteToken:
    def test_new_token_is_long_and_random(self, addon_auth):
        a, b = addon_auth.new_token(), addon_auth.new_token()
        assert a != b
        assert len(a) >= 64

    def test_file_is_private_to_the_user(self, addon_auth, tmp_path, monkeypatch):
        monkeypatch.delenv("BLENDERWRIGHT_TOKEN_FILE", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(addon_auth.sys, "platform", "linux")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        path = tmp_path / "cfg" / "blenderwright" / "token"
        addon_auth.write_token("secret")

        assert path.read_text() == "secret"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700

    def test_override_leaves_its_directory_alone(self, addon_auth, tmp_path, monkeypatch):
        """An override points into a shared folder (WSL, Docker): the token file
        is private, but the folder keeps its mode for whoever else uses it."""
        shared = tmp_path / "shared"
        shared.mkdir()
        shared.chmod(0o755)
        monkeypatch.setenv("BLENDERWRIGHT_TOKEN_FILE", str(shared / "token"))
        addon_auth.write_token("secret")

        assert stat.S_IMODE((shared / "token").stat().st_mode) == 0o600
        assert stat.S_IMODE(shared.stat().st_mode) == 0o755

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
