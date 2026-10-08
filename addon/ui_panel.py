"""Blender N-panel UI for blenderwright server control."""

import bpy

from . import server as addon_server
from .handlers import code_exec


class BLENDERWRIGHT_PT_MainPanel(bpy.types.Panel):
    """blenderwright MCP Server Control Panel"""
    bl_label = "blenderwright"
    bl_idname = "BLENDERWRIGHT_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "blenderwright"

    def draw(self, context):
        layout = self.layout
        srv = addon_server.get_server()

        if srv.is_running:
            port = srv._port
            layout.label(text=f"Server: Running (port {port})", icon="CHECKMARK")
            layout.operator("blenderwright.stop_server", text="Stop Server", icon="CANCEL")
        else:
            layout.label(text="Server: Stopped", icon="X")
            layout.prop(context.scene, "blenderwright_port", text="Port")
            layout.operator("blenderwright.start_server", text="Start Server", icon="PLAY")

        # Raw Python switch: per session, never saved into the .blend.
        box = layout.box()
        wm = context.window_manager
        box.prop(wm, code_exec.SWITCH_PROP, text="Allow raw Python")
        if getattr(wm, code_exec.SWITCH_PROP, False):
            box.label(text="Model may run Python in this session", icon="ERROR")
            log = code_exec.get_exec_log()
            if log:
                last = log[-1]
                status = "ok" if last["ok"] else "failed"
                box.label(text=f"{len(log)} run(s), last {last['time']} ({status}):")
                box.label(text=f"  {last['first_line'][:48]}")
            else:
                box.label(text="No runs yet this session")
        else:
            box.label(text="execute_blender_code is off", icon="LOCKED")


class BLENDERWRIGHT_OT_StartServer(bpy.types.Operator):
    """Start the blenderwright MCP server"""
    bl_idname = "blenderwright.start_server"
    bl_label = "Start blenderwright Server"

    def execute(self, context):
        port = context.scene.blenderwright_port
        addon_server.start_server(port=port)
        self.report({"INFO"}, f"blenderwright server started on 127.0.0.1:{port}")
        return {"FINISHED"}


class BLENDERWRIGHT_OT_StopServer(bpy.types.Operator):
    """Stop the blenderwright MCP server"""
    bl_idname = "blenderwright.stop_server"
    bl_label = "Stop blenderwright Server"

    def execute(self, context):
        addon_server.stop_server()
        self.report({"INFO"}, "blenderwright server stopped")
        return {"FINISHED"}


classes = (
    BLENDERWRIGHT_PT_MainPanel,
    BLENDERWRIGHT_OT_StartServer,
    BLENDERWRIGHT_OT_StopServer,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.blenderwright_port = bpy.props.IntProperty(
        name="Port",
        description="TCP port for the blenderwright server",
        default=9876,
        min=1024,
        max=65535,
    )

    # WindowManager, not Scene: WindowManager properties are not written
    # into the .blend, so the switch cannot travel with a file and is
    # always off when Blender starts.
    setattr(bpy.types.WindowManager, code_exec.SWITCH_PROP, bpy.props.BoolProperty(
        name="Allow raw Python",
        description=(
            "Let execute_blender_code run model-written Python in this Blender "
            "session. Off by default. The restricted namespace blocks obvious "
            "mistakes but is not a security boundary: bpy itself can write files "
            "and run any operator. Every run is echoed to the system console"
        ),
        default=False,
    ))


def unregister():
    if hasattr(bpy.types.Scene, "blenderwright_port"):
        del bpy.types.Scene.blenderwright_port
    if hasattr(bpy.types.WindowManager, code_exec.SWITCH_PROP):
        delattr(bpy.types.WindowManager, code_exec.SWITCH_PROP)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
