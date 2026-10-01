"""Blender N-panel UI for blenderwright server control."""

import bpy

from . import server as addon_server


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


def unregister():
    if hasattr(bpy.types.Scene, "blenderwright_port"):
        del bpy.types.Scene.blenderwright_port

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
