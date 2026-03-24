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


@mcp.prompt()
def topology_best_practices() -> str:
    """Expert guide on quad topology, edge flow, and modeling best practices."""
    return (
        "## Topology Best Practices for 3D Modeling\n\n"
        "### Quad Topology\n"
        "- Always prefer quads (4-sided polygons) over triangles or n-gons.\n"
        "- Quads deform predictably during animation and subdivide cleanly.\n"
        "- Avoid triangles in areas of high curvature or deformation (joints, face).\n"
        "- N-gons (5+ sided faces) cause unpredictable shading artifacts — always clean up.\n\n"
        "### Edge Loops and Edge Flow\n"
        "- Edge loops should follow the natural contours and muscle lines of the subject.\n"
        "- For characters: edge loops around eyes, mouth, and joints are critical for deformation.\n"
        "- Edge flow determines how the mesh deforms during animation — plan it before modeling.\n"
        "- Use Ctrl+R (Loop Cut) to insert edge loops; Alt+click to select entire loops.\n\n"
        "### Poles\n"
        "- A pole is a vertex where more or fewer than 4 edges meet.\n"
        "- 3-poles and 5-poles are sometimes necessary but should be placed in low-curvature areas.\n"
        "- Avoid 5+ edge poles in areas that will deform (joints, face muscles).\n"
        "- Use poles to redirect edge flow when transitioning between areas of different density.\n\n"
        "### Modifiers vs Direct Editing\n"
        "- Use the Mirror modifier (X axis) for symmetric modeling — apply only when done.\n"
        "- Use Subdivision Surface modifier to smooth mesh — keep base mesh low-poly and clean.\n"
        "- Use Bevel modifier for rounded edges instead of manually loop-cutting bevels.\n"
        "- Apply modifiers only when the mesh is finalized; keep them live for flexibility.\n\n"
        "### N-gon Cleanup\n"
        "- Use Grid Fill (F after selecting border edge loop) to fill holes with clean quads.\n"
        "- Use Triangulate modifier only as a last resort for export (games, rendering).\n"
        "- F3 → 'Tris to Quads' (Alt+J) can auto-convert many triangles back to quads.\n\n"
        "### Face Density\n"
        "- Keep face density even across the mesh — avoid sudden concentration of faces.\n"
        "- Higher density is acceptable near detail areas (face, hands) but transition gradually.\n"
        "- Use the Checker Deselect tool to verify density distribution visually.\n"
    )


@mcp.prompt()
def scale_reference_guide() -> str:
    """Real-world scale references for common objects in Blender."""
    return (
        "## Real-World Scale Reference Guide\n\n"
        "### Blender Units\n"
        "- By default, 1 Blender unit = 1 meter.\n"
        "- Set unit system to METRIC: Scene Properties → Units → Unit System → Metric.\n"
        "- Set Length to Meters or Centimeters depending on your subject scale.\n\n"
        "### Common Object Dimensions\n\n"
        "| Object         | Height / Length | Notes |\n"
        "|----------------|-----------------|-------|\n"
        "| Person (adult) | 1.75 m          | Eye level ~1.6 m |\n"
        "| Door           | 2.1 m tall, 0.9 m wide | Standard interior door |\n"
        "| Table          | 0.75 m height   | Dining table |\n"
        "| Chair          | 0.45 m seat height, 0.9 m total | Standard chair |\n"
        "| Car            | 4.5 m length, 1.5 m height | Average sedan |\n"
        "| Coffee cup     | 0.09 m (9 cm) height | Standard mug |\n"
        "| Smartphone     | 0.15 m (15 cm) length | Modern phone |\n"
        "| Room ceiling   | 2.4 m height    | Standard residential |\n\n"
        "### Working with Scale in Blender\n"
        "- Use the Measure tool (Shift+Space → Measure) to verify object dimensions.\n"
        "- Import reference images as Image Empties and scale them to known measurements.\n"
        "- Use N-panel (press N) → Item tab to view and set exact object dimensions.\n"
        "- Apply scale (Ctrl+A → Scale) before boolean operations or sculpting.\n"
        "- The default cube is 2 m × 2 m × 2 m — scale it down for most real objects.\n"
    )


@mcp.prompt()
def lighting_principles() -> str:
    """Lighting principles for professional 3D rendering."""
    return (
        "## Lighting Principles for Professional 3D Rendering\n\n"
        "### Three-Point Lighting\n"
        "The classic three-point lighting setup provides dimensional, professional results:\n"
        "- **Key light**: Main light source, placed 45° above and to one side of subject. "
        "Highest energy (~1000W). Defines primary shadows and form.\n"
        "- **Fill light**: Opposite side from key, lower energy (~300W). "
        "Softens key light shadows without eliminating them.\n"
        "- **Rim light** (back light): Behind subject, aimed back toward camera (~500W). "
        "Creates separation from background and adds depth.\n"
        "- Energy ratio guideline: Key : Fill : Rim = 3 : 1 : 1.5\n\n"
        "### HDRI Environment Lighting\n"
        "- HDRI (High Dynamic Range Image) provides realistic ambient lighting and reflections.\n"
        "- Set up via: World Properties → Surface → Use Nodes → Add Environment Texture.\n"
        "- Use HDRI for product shots, architectural renders, and any outdoor/realistic scene.\n"
        "- Combine HDRI with a key light for dramatic results (HDRI fills shadows naturally).\n"
        "- Rotate HDRI using the Mapping node connected between Texture Coordinate and Env Texture.\n\n"
        "### EEVEE vs Cycles\n"
        "- **EEVEE**: Real-time rasterization renderer. Fast (seconds per frame). "
        "Great for previews, stylized renders, game-ready assets, and motion graphics.\n"
        "- **Cycles**: Path-tracing renderer. Physically accurate light simulation. "
        "Slower (minutes per frame) but produces photorealistic results.\n"
        "- Use EEVEE when speed matters or for stylized/non-photorealistic output.\n"
        "- Use Cycles for product visualization, architectural renders, and photorealism.\n\n"
        "### Color Temperature\n"
        "- Warm light (orange/yellow, 2700-4000K): Feels inviting, natural sunsets, interior lamps.\n"
        "- Cool light (blue/white, 5000-7000K): Clinical, daylight, outdoor overcast.\n"
        "- Mix warm key light with cool fill light for cinematic contrast.\n\n"
        "### Shadow Settings\n"
        "- Increase light source size for softer shadows (more realistic for large area lights).\n"
        "- In Cycles: use Portal lights for windows, IES textures for realistic lamp shapes.\n"
        "- In EEVEE: enable Soft Shadows in Render Properties → Shadows for smoother edges.\n"
    )


@mcp.prompt()
def studio_lighting_setup() -> str:
    """Step-by-step guide for professional studio lighting setup."""
    return (
        "## Professional Studio Lighting Setup\n\n"
        "Follow these numbered steps to create a professional studio lighting setup in Blender:\n\n"
        "1. **Create a backdrop plane**: Add a large plane (10 m × 10 m) behind and below the "
        "subject. Curve it upward at the back (like an infinity cove) for seamless background.\n\n"
        "2. **Add key light**: Add an Area light, position it 45° above and to the right of the "
        "subject at ~3 m distance. Set energy to 1000W. This is your key light — the primary "
        "light defining form and shadows.\n\n"
        "3. **Add fill light**: Add a second Area light on the opposite side (~2 m distance). "
        "Set energy to 300W and increase size for softer quality. The fill light reduces "
        "harsh shadows from the key light without eliminating depth.\n\n"
        "4. **Add rim light**: Place a third light behind the subject, pointing toward the camera "
        "at ~2 m distance. Set energy to 500W. The rim light separates the subject from the "
        "background and adds professional depth.\n\n"
        "5. **Set world background**: Open World Properties → Surface → Background Color. "
        "Set to black (0, 0, 0) or very dark grey (0.02, 0.02, 0.02) to isolate the subject.\n\n"
        "6. **Configure render settings**: For photorealistic results, use Cycles with 256 samples "
        "(or 512 for final render). For faster iteration, use EEVEE with Soft Shadows enabled. "
        "Set resolution to 1920×1080 (or 2:1 ratio for product shots).\n"
    )


@mcp.prompt()
def character_basemesh_workflow() -> str:
    """Step-by-step workflow for creating a character base mesh."""
    return (
        "## Character Base Mesh Workflow\n\n"
        "Follow these numbered steps to create a clean character base mesh in Blender:\n\n"
        "1. **Start with a cube**: Delete the default cube and add a new cube (Shift+A → Mesh → "
        "Cube). This will become the torso. Scale to approximately 0.3 m wide × 0.5 m tall.\n\n"
        "2. **Add mirror modifier on X axis**: With the cube selected, add a Mirror modifier "
        "(Properties → Modifiers → Add Modifier → Mirror). Enable Clipping to prevent vertices "
        "from crossing the center. Delete the right half of the cube in Edit mode — the mirror "
        "modifier handles symmetry automatically.\n\n"
        "3. **Work in edit mode to shape torso proportions**: Enter Edit mode (Tab). Add edge "
        "loops (Ctrl+R) for the chest, waist, and hip regions. Move vertices to create realistic "
        "torso proportions — wider at shoulders, narrow at waist, medium at hips.\n\n"
        "4. **Extrude limbs from torso**: Select the shoulder faces and extrude (E) downward to "
        "create arms. Select hip-side faces and extrude downward for legs. Add edge loops at "
        "joints (elbows, knees, wrists, ankles) for deformation quality.\n\n"
        "5. **Shape head from top vertices**: Select the top face of the torso mesh or add a "
        "separate UV sphere for the head. Scale and position it proportionally — head is roughly "
        "1/7 to 1/8 of total body height.\n\n"
        "6. **Add subdivision surface modifier**: Add a Subdivision Surface modifier at level 2 "
        "for viewport and level 3 for render. This smooths the low-poly base mesh into organic "
        "shapes. Keep the base mesh clean — subdivision magnifies any topology errors.\n\n"
        "7. **Refine edge loops for joints**: In Edit mode, add supporting edge loops near joints "
        "(elbows, knees, knuckles) to preserve shape when subdivision is applied. Edge loops "
        "should follow the natural crease lines of the joint anatomy.\n"
    )


@mcp.prompt()
def material_workflow_guide() -> str:
    """Expert guide on PBR material setup using Principled BSDF."""
    return (
        "## PBR Material Workflow Guide\n\n"
        "### Principled BSDF — The Standard Shader\n"
        "The Principled BSDF shader combines all common material properties into a single node. "
        "It is the recommended shader for physically-based rendering (PBR) in Blender.\n\n"
        "### Key Parameters\n"
        "- **Base Color**: Albedo / diffuse color of the surface. For metals, this becomes "
        "the specular tint color.\n"
        "- **Metallic**: 0.0 = dielectric (plastic, wood, skin); 1.0 = metal (gold, steel). "
        "Use binary values — surfaces are either metal or not.\n"
        "- **Roughness**: 0.0 = perfectly smooth (mirror); 1.0 = fully rough (matte). "
        "Controls the spread of specular reflections.\n"
        "- **Normal**: Connect a Normal Map node here for surface detail without extra geometry.\n"
        "- **Transmission**: 1.0 enables glass/transparency mode (use with IOR ~1.45 for glass).\n\n"
        "### Common Material Recipes\n\n"
        "| Material | Metallic | Roughness | Notes |\n"
        "|----------|----------|-----------|-------|\n"
        "| Polished metal | 1.0 | 0.05–0.2 | Chrome, mirror |\n"
        "| Brushed metal | 1.0 | 0.3–0.5 | Steel, aluminum |\n"
        "| Plastic (shiny) | 0.0 | 0.1–0.3 | Hard plastic |\n"
        "| Plastic (matte) | 0.0 | 0.5–0.8 | Rubber, matte plastic |\n"
        "| Glass | 0.0 | 0.0 | Set Transmission=1.0, IOR=1.45 |\n"
        "| Skin | 0.0 | 0.4–0.6 | Add Subsurface ~0.1 for translucency |\n\n"
        "### Texture Workflow\n"
        "- Connect Image Texture nodes for diffuse (Base Color), roughness (Roughness), "
        "and normal maps (Normal Map node → Normal input).\n"
        "- Set color space: Base Color texture → sRGB; Roughness/Normal textures → Non-Color.\n"
        "- Use UV Unwrap (U in Edit mode) before assigning textures.\n\n"
        "### Productivity Tip\n"
        "- Enable the Node Wrangler extension (Edit → Preferences → Add-ons → Node Wrangler). "
        "Use Ctrl+Shift+T to import a full PBR texture set automatically from a folder.\n"
    )


@mcp.prompt()
def auto_critique_workflow() -> str:
    """Guide the LLM to automatically capture and critique its work after structural changes."""
    return (
        "## Auto-Critique Visual Feedback Workflow\n\n"
        "After performing any of these structural operations, ALWAYS capture a viewport "
        "screenshot using `get_viewport_screenshot(mode='fast')` and critique what you see "
        "before continuing with the next step.\n\n"
        "### Operations that REQUIRE auto-critique:\n"
        "- Adding objects (mesh, light, camera, curve, empty)\n"
        "- Deleting objects or geometry\n"
        "- Boolean operations (union, difference, intersect, slice)\n"
        "- Applying or adding a modifier (Subdivision Surface, Mirror, Bevel, etc.)\n"
        "- Sculpting operations that change shape\n"
        "- Material and shader changes (new materials, texture assignments)\n"
        "- Lighting changes (add/move/change lights, HDRI setup)\n"
        "- Camera positioning or framing changes\n"
        "- Mesh editing (extrude, inset, bridge, loop cut, merge)\n\n"
        "### Operations that do NOT need auto-critique:\n"
        "- Renaming objects or collections\n"
        "- Querying scene info or object properties\n"
        "- Collection organization (moving objects between collections)\n"
        "- File save or export operations\n"
        "- Keyframe insertion (unless previewing the result)\n"
        "- Setting non-visual properties (physics settings, constraints)\n\n"
        "### When critiquing, check:\n"
        "1. Does the object look correct from this angle? Any obvious geometry errors?\n"
        "2. Are proportions realistic? (Refer to scale_reference_guide for reference)\n"
        "3. Is the topology clean? No floating vertices, holes, or inverted normals visible?\n"
        "4. Is lighting adequate to evaluate the result?\n"
        "5. What should be improved or done next?\n\n"
        "### Token Budget Rules\n"
        "- Limit your critique to 2-3 sentences. Be specific and actionable.\n"
        "- Capture only ONE screenshot per structural operation or batch.\n"
        "- During multi-step sequences (e.g., building a character), capture once at the "
        "end of the sequence — not after every individual step.\n"
        "- If the user asks you to skip screenshots, respect that preference.\n"
    )
