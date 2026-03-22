"""MCP prompt templates for common Blender workflows."""

from blend_ai.server import mcp


@mcp.prompt()
def blender_best_practices() -> str:
    """Best practices for using Blender MCP tools effectively."""
    return (
        "When working with Blender through these MCP tools, follow these best practices:\n\n"
        "## Boolean Operations\n"
        "- PREFER `booltool_auto_union` over manually adding a BOOLEAN modifier + apply. "
        "The Bool Tool auto operations handle selection, cleanup, and cutter removal automatically.\n"
        "- Use `booltool_auto_union` to permanently merge meshes (e.g., joining a head to a body "
        "so parts don't float apart).\n"
        "- Use `booltool_auto_difference` for cutting holes or subtracting shapes.\n"
        "- Use `booltool_auto_intersect` to keep only overlapping geometry.\n"
        "- Use `booltool_auto_slice` to split an object along another shape.\n"
        "- Only use the lower-level `boolean_operation` or `add_modifier(type='BOOLEAN')` when "
        "you need non-destructive (unapplied) boolean modifiers.\n\n"
        "## Mesh Editing\n"
        "- Use `bridge_edge_loops` to connect two edge loops with faces — great for "
        "connecting limbs, creating tubes, or joining mesh islands.\n"
        "- Use `merge_vertices` to clean up overlapping vertices after boolean or join operations.\n"
        "- Use `set_smooth_shading` after modeling to improve visual quality.\n"
        "- Apply `subdivide_mesh` before detailed sculpting for more geometry.\n\n"
        "## Modifiers\n"
        "- Add modifiers with `add_modifier`, configure with `set_modifier_property`, "
        "and finalize with `apply_modifier`.\n"
        "- Common workflow: MIRROR modifier for symmetric modeling, then SUBSURF for smoothing.\n"
        "- Use `remove_modifier` to discard unwanted modifiers without applying.\n\n"
        "## General Workflow\n"
        "- Always check the scene state with the blender://scene resource before making assumptions.\n"
        "- Use `apply_transform` before boolean operations to avoid unexpected results from "
        "unapplied scale/rotation.\n"
        "- Organize objects into collections for complex scenes.\n"
        "- Name objects descriptively — many tools reference objects by name.\n"
    )


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
