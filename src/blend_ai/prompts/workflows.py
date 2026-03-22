"""MCP prompt templates for common Blender workflows."""

from blend_ai.server import mcp


@mcp.prompt()
def product_shot_setup() -> str:
    """Set up a professional product shot with studio lighting and camera."""
    return (
        "Please help me set up a professional product shot in Blender. "
        "1. Create a backdrop plane scaled large enough for the product. "
        "2. Set up three-point studio lighting with appropriate energy levels. "
        "3. Position a camera at a 3/4 angle looking at the origin. "
        "4. Set render engine to Cycles with 256 samples. "
        "5. Set resolution to 1920x1080. "
        "Use the available Blender tools to accomplish each step."
    )


@mcp.prompt()
def character_base_mesh() -> str:
    """Create a base mesh for character modeling."""
    return (
        "Please help me create a base mesh for a character in Blender. "
        "1. Start with a cube, add a mirror modifier on X axis. "
        "2. Add a subdivision surface modifier at level 2. "
        "3. Shape the basic torso proportions. "
        "4. Create a simple armature with spine, arms, and legs. "
        "5. Parent the mesh to the armature with automatic weights. "
        "Use the available Blender tools to accomplish each step."
    )


@mcp.prompt()
def scene_cleanup() -> str:
    """Clean up and organize the current Blender scene."""
    return (
        "Please help me clean up the current Blender scene. "
        "1. First, get the scene info to understand what's in the scene. "
        "2. List all objects and their types. "
        "3. Organize objects into collections by type (meshes, lights, cameras, empties). "
        "4. Apply any unapplied transforms on mesh objects. "
        "5. Set smooth shading on all mesh objects. "
        "Use the available Blender tools to accomplish each step."
    )


@mcp.prompt()
def animation_turntable() -> str:
    """Create a turntable animation of the selected object."""
    return (
        "Please help me create a turntable animation in Blender. "
        "1. Get the scene info to find the target object. "
        "2. Set the frame range to 1-120 (5 seconds at 24fps). "
        "3. Insert a rotation Z keyframe at frame 1 with value 0. "
        "4. Insert a rotation Z keyframe at frame 120 with value 6.28318 (360 degrees). "
        "5. Set the interpolation to LINEAR for smooth rotation. "
        "6. Set up a camera pointing at the object. "
        "Use the available Blender tools to accomplish each step."
    )
