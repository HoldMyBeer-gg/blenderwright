"""Add-on behaviour across file loads, in its own headless Blender.

The shared Blender in conftest serves every other test, so anything that has
to register the add-on and then load a file runs in a fresh process here.
"""

import os
import subprocess
import textwrap

from tests_live.conftest import BLENDER, HERE

REPO = os.path.dirname(HERE)

RENDER_AFTER_LOAD = textwrap.dedent(f"""
    import sys
    import bpy
    sys.path.insert(0, {REPO!r})
    import addon
    from addon.render_guard import render_guard

    addon.register()
    bpy.ops.wm.read_homefile(use_factory_startup=True)

    seen = []
    bpy.app.handlers.render_post.append(lambda *_: seen.append(render_guard.is_rendering))
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"  # CPU: CI runners have no GPU
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    scene.render.resolution_x = scene.render.resolution_y = 8
    bpy.ops.render.render()
    print("GUARD", seen, render_guard.is_rendering)
""")


def test_render_guard_still_tracks_renders_after_a_file_load(tmp_path):
    """Blender drops non-persistent handlers on every load, which silently
    turned the render-busy guard off after the first file was opened."""
    env = dict(os.environ, BLENDERWRIGHT_TOKEN_FILE=str(tmp_path / "token"))
    out = subprocess.run(
        [BLENDER, "-b", "--factory-startup", "--python-expr", RENDER_AFTER_LOAD],
        capture_output=True, text=True, timeout=120, env=env,
    ).stdout
    assert "GUARD [True] False" in out, out[-2000:]


AUTORUN = textwrap.dedent(f"""
    import os
    import sys
    import bpy
    sys.path.insert(0, {REPO!r})
    import addon
    from addon.handlers import file_ops

    addon.register()
    blend = os.path.join(sys.argv[-1], "rigged.blend")
    text = bpy.data.texts.new("rig_ui.py")
    text.write("import bpy")
    text.use_module = True
    bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)

    prefs = bpy.context.preferences
    prefs.filepaths.use_scripts_auto_execute = True
    prefs.is_dirty = False

    def report(step):
        print("AUTORUN", step, prefs.filepaths.use_scripts_auto_execute, prefs.is_dirty,
              bpy.app.autoexec_fail)

    file_ops.handle_list_blend_contents({{"filepath": blend}})
    report("list")
    file_ops.handle_import_file({{"filepath": os.path.join({HERE!r}, "assets", "tri.obj")}})
    report("import")
    prefs.filepaths.use_scripts_auto_execute = True
    prefs.is_dirty = False
    file_ops.handle_open_file({{"filepath": blend}})
    report("open")
""")


def test_auto_run_is_off_for_the_session_but_never_saved(tmp_path):
    """Files the model picks never run their scripts, and the user's own
    Auto Run Python Scripts preference is not changed on disk."""
    env = dict(os.environ, BLENDERWRIGHT_TOKEN_FILE=str(tmp_path / "token"))
    out = subprocess.run(
        [BLENDER, "-b", "--factory-startup", "--python-expr", AUTORUN, "--", str(tmp_path)],
        capture_output=True, text=True, timeout=120, env=env,
    ).stdout
    # Off for this session, and the preferences are not marked for saving
    assert "AUTORUN list False False False" in out, out[-2000:]
    assert "AUTORUN import False False False" in out, out[-2000:]
    # Opening loads with scripts blocked, and the preference keeps its value
    assert "AUTORUN open True False True" in out, out[-2000:]
