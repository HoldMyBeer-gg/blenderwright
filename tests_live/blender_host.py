"""Runs inside headless Blender for the live tests.

Loads the add-on from this repository, starts its server on a free port,
writes the port to a ready file, then drains the main-thread command queue
itself: headless Blender has no event loop to run the add-on's timer.

    blender -b --factory-startup --python tests_live/blender_host.py -- <ready_file> <pristine.blend>
"""

import os
import sys
import time

import bpy

ready_file, pristine = sys.argv[sys.argv.index("--") + 1:][:2]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import addon  # noqa: E402
from addon import server, thread_safety  # noqa: E402

addon.register()
bpy.ops.wm.save_as_mainfile(filepath=pristine)
server.start_server(port=0)

with open(ready_file + ".tmp", "w") as handle:
    handle.write(str(server._server._port))
os.replace(ready_file + ".tmp", ready_file)

while server._server is not None and server._server.is_running:
    thread_safety._process_queue()
    time.sleep(0.002)
