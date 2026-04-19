"""Tests for the addon's sys.modules purge helper.

The purge runs at unregister() time so that disable → edit → enable picks up
edited handler code instead of returning stale cached bytecode.
"""

import os
import sys
import importlib.util


def _load_addon_init():
    """Load addon/__init__.py in isolation — we only want the pure helper.

    The real __init__ imports bpy in register()/unregister(), but
    _purge_submodules_from_cache has no bpy dependency, so module load
    itself is safe.
    """
    init_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "addon", "__init__.py",
    )
    spec = importlib.util.spec_from_file_location("addon_init_under_test", init_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPurgeSubmodulesFromCache:
    def test_removes_submodule_entries(self):
        addon_init = _load_addon_init()
        fake = {
            "addon": object(),
            "addon.handlers": object(),
            "addon.handlers.objects": object(),
            "addon.server": object(),
        }
        removed = addon_init._purge_submodules_from_cache("addon", modules=fake)
        assert "addon.handlers" not in fake
        assert "addon.handlers.objects" not in fake
        assert "addon.server" not in fake
        assert set(removed) == {
            "addon.handlers", "addon.handlers.objects", "addon.server",
        }

    def test_leaves_package_itself(self):
        """Purging must not delete the package __init__ entry — that's the
        currently-executing module during unregister()."""
        addon_init = _load_addon_init()
        fake = {
            "addon": object(),
            "addon.handlers": object(),
        }
        addon_init._purge_submodules_from_cache("addon", modules=fake)
        assert "addon" in fake

    def test_ignores_unrelated_modules(self):
        addon_init = _load_addon_init()
        unrelated = object()
        fake = {
            "addon": object(),
            "addon.handlers": object(),
            "other_package": unrelated,
            "other_package.sub": object(),
            "addonlike": object(),  # same prefix as addon, but no dot — keep it
        }
        addon_init._purge_submodules_from_cache("addon", modules=fake)
        assert fake["other_package"] is unrelated
        assert "other_package.sub" in fake
        assert "addonlike" in fake

    def test_empty_cache_is_a_noop(self):
        addon_init = _load_addon_init()
        fake = {}
        removed = addon_init._purge_submodules_from_cache("addon", modules=fake)
        assert removed == []
        assert fake == {}

    def test_no_submodules_returns_empty(self):
        addon_init = _load_addon_init()
        fake = {"addon": object()}
        removed = addon_init._purge_submodules_from_cache("addon", modules=fake)
        assert removed == []
        assert "addon" in fake

    def test_strips_submodule_attrs_from_parent(self):
        """After first import, submodules live both in sys.modules AND as
        attributes on the parent package. `from . import X` prefers the
        parent's attribute over a fresh sys.modules lookup, so the purge
        must clear BOTH or reloads keep returning cached bytecode."""
        addon_init = _load_addon_init()

        class FakeParent:
            pass
        parent = FakeParent()
        fake_handlers = object()
        fake_ui = object()
        parent.handlers = fake_handlers
        parent.ui_panel = fake_ui

        fake_modules = {
            "addon": parent,
            "addon.handlers": fake_handlers,
            "addon.handlers.objects": object(),
            "addon.ui_panel": fake_ui,
        }
        addon_init._purge_submodules_from_cache("addon", modules=fake_modules)
        assert not hasattr(parent, "handlers"), (
            "handlers attribute must be stripped from parent or "
            "`from . import handlers` returns the cached module object"
        )
        assert not hasattr(parent, "ui_panel")

    def test_parent_missing_attr_does_not_crash(self):
        """If a parent package lacks the submodule attribute (e.g. purged
        earlier), the function must not raise AttributeError."""
        addon_init = _load_addon_init()

        class FakeParent:
            pass
        parent = FakeParent()  # no `handlers` attribute

        fake_modules = {
            "addon": parent,
            "addon.handlers": object(),
        }
        addon_init._purge_submodules_from_cache("addon", modules=fake_modules)
        assert "addon.handlers" not in fake_modules

    def test_works_with_extension_style_prefix(self):
        """When installed as a Blender extension, the package name is
        something like 'bl_ext.user_default.blend_ai' — purge must follow
        whatever __name__ resolves to, not a hardcoded string."""
        addon_init = _load_addon_init()
        pkg = "bl_ext.user_default.blend_ai"
        fake = {
            pkg: object(),
            f"{pkg}.handlers": object(),
            f"{pkg}.handlers.objects": object(),
            "bl_ext.user_default.other_addon": object(),
        }
        removed = addon_init._purge_submodules_from_cache(pkg, modules=fake)
        assert pkg in fake
        assert f"{pkg}.handlers" not in fake
        assert f"{pkg}.handlers.objects" not in fake
        assert "bl_ext.user_default.other_addon" in fake
        assert set(removed) == {f"{pkg}.handlers", f"{pkg}.handlers.objects"}

    def test_defaults_to_real_sys_modules(self):
        """No modules arg → uses sys.modules. Sanity check: function doesn't
        crash and returns a list without needing a custom dict."""
        addon_init = _load_addon_init()
        # Pick a prefix guaranteed not to exist so we don't disturb real state
        removed = addon_init._purge_submodules_from_cache(
            "__definitely_not_a_real_package_9f8a7b"
        )
        assert removed == []
        assert sys.modules  # didn't nuke anything real
