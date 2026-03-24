"""Blender N-panel UI for blend-ai server control."""

import bpy

from . import server as addon_server


class BLENDAI_PT_MainPanel(bpy.types.Panel):
    """blend-ai MCP Server Control Panel"""
    bl_label = "blend-ai"
    bl_idname = "BLENDAI_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "blend-ai"

    def draw(self, context):
        layout = self.layout
        srv = addon_server.get_server()

        if srv.is_running:
            port = srv._port
            layout.label(text=f"Server: Running (port {port})", icon="CHECKMARK")
            layout.operator("blendai.stop_server", text="Stop Server", icon="CANCEL")
        else:
            layout.label(text="Server: Stopped", icon="X")
            layout.prop(context.scene, "blendai_port", text="Port")
            layout.operator("blendai.start_server", text="Start Server", icon="PLAY")


class BLENDAI_OT_StartServer(bpy.types.Operator):
    """Start the blend-ai MCP server"""
    bl_idname = "blendai.start_server"
    bl_label = "Start blend-ai Server"

    def execute(self, context):
        port = context.scene.blendai_port
        addon_server.start_server(port=port)
        self.report({"INFO"}, f"blend-ai server started on 127.0.0.1:{port}")
        return {"FINISHED"}


class BLENDAI_OT_StopServer(bpy.types.Operator):
    """Stop the blend-ai MCP server"""
    bl_idname = "blendai.stop_server"
    bl_label = "Stop blend-ai Server"

    def execute(self, context):
        addon_server.stop_server()
        self.report({"INFO"}, "blend-ai server stopped")
        return {"FINISHED"}


classes = (
    BLENDAI_PT_MainPanel,
    BLENDAI_OT_StartServer,
    BLENDAI_OT_StopServer,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.blendai_port = bpy.props.IntProperty(
        name="Port",
        description="TCP port for the blend-ai server",
        default=9876,
        min=1024,
        max=65535,
    )


def unregister():
    if hasattr(bpy.types.Scene, "blendai_port"):
        del bpy.types.Scene.blendai_port

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
