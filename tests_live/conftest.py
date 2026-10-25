"""Live tests: the real MCP tools against a real headless Blender.

Nothing is mocked. One Blender runs per session (see blender_host.py); every
test starts from a fresh factory scene. Set BLENDER to the Blender executable;
without it the live tests are skipped.
"""

import os
import shutil
import subprocess
import sys
import time

import pytest

BLENDER = os.environ.get("BLENDER")
HERE = os.path.dirname(os.path.abspath(__file__))
STARTUP_TIMEOUT = 120.0


def pytest_collection_modifyitems(config, items):
    if not BLENDER:
        skip = pytest.mark.skip(reason="set BLENDER to a Blender 5.2 executable")
        for item in items:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def blender(tmp_path_factory):
    root = tmp_path_factory.mktemp("blender")
    ready, pristine = root / "port", root / "pristine.blend"
    env = dict(os.environ, BLENDERWRIGHT_TOKEN_FILE=str(root / "token"))
    os.environ["BLENDERWRIGHT_TOKEN_FILE"] = env["BLENDERWRIGHT_TOKEN_FILE"]
    log = open(root / "blender.log", "w")
    proc = subprocess.Popen(
        [BLENDER, "-b", "--factory-startup", "--python",
         os.path.join(HERE, "blender_host.py"), "--", str(ready), str(pristine)],
        stdout=log, stderr=subprocess.STDOUT, env=env)
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while not ready.exists():
        if proc.poll() is not None or time.monotonic() > deadline:
            proc.kill()
            log.close()
            sys.stderr.write((root / "blender.log").read_text())
            pytest.fail("Blender did not start the blenderwright server")
        time.sleep(0.1)

    from blenderwright import server
    from blenderwright.connection import BlenderConnection

    server._connection = BlenderConnection(port=int(ready.read_text()))
    yield {"root": root, "pristine": pristine, "process": proc}
    server._connection.disconnect()
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()


@pytest.fixture
def scene(blender, tmp_path):
    """A fresh factory scene (Cube, Camera, Light) for this test."""
    from blenderwright.tools.file_ops import open_file

    work = tmp_path / "scene.blend"
    shutil.copy(blender["pristine"], work)
    open_file(str(work))
    return tmp_path
