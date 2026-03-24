# Phase 03: Visual Feedback Loop - Research

**Researched:** 2026-03-24
**Domain:** Blender viewport capture (bpy.ops.render.opengl), MCP prompt-driven auto-feedback, base64 image encoding
**Confidence:** HIGH

## Summary

Phase 3 replaces the current slow `bpy.ops.render.render()` capture with a fast `bpy.ops.render.opengl()` viewport screenshot, and adds an MCP prompt that instructs the LLM to auto-critique its work after structural changes. The opengl render is ~10-100x faster than a full render because it captures the 3D viewport directly (whatever the user sees) without computing ray-traced lighting, volumetrics, or post-processing.

The current `capture_viewport` handler in `addon/handlers/camera.py` uses `bpy.ops.render.render(write_still=True)` which triggers a full render cycle and activates the render guard. The Phase 3 replacement uses `bpy.ops.render.opengl(write_still=True)` which renders using the viewport drawing engine (Solid/Material Preview/Wireframe mode) and completes in milliseconds. This does NOT trigger the render guard since it's not a "real" render.

The auto-critique is implemented purely as an MCP prompt — no server-side logic needed. The prompt tells the LLM: "After any structural change (add, delete, boolean, apply modifier, sculpt), call `get_viewport_screenshot()` and critique what you see before continuing."

**Primary recommendation:** Two plans: (1) fast viewport screenshot handler + MCP tool update, (2) auto-critique prompt + token-safety prompt.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FEED-01 | Fast viewport screenshot in under 500ms without triggering render guard | `bpy.ops.render.opengl(write_still=True)` — captures viewport in milliseconds, doesn't trigger render_pre/complete handlers |
| FEED-02 | After building/modifying an object, LLM auto-captures screenshot and reports what it sees | New `@mcp.prompt()` function instructing LLM to self-critique after structural operations |
| FEED-03 | Auto-screenshot prompt limits when screenshots fire to prevent token runaway | Prompt explicitly lists structural operations that trigger screenshots; excludes metadata-only changes |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| bpy.ops.render.opengl | Blender 4.0+ / 5.1 | Fast viewport capture | Official operator for viewport rendering; captures current 3D viewport state without full render cycle |
| base64 (stdlib) | Python 3.10+ | Image encoding | Already used in current capture_viewport handler |
| tempfile (stdlib) | Python 3.10+ | Temporary file for capture | Already used in current capture_viewport handler |
| mcp (FastMCP) | 1.26.0 | `@mcp.prompt()` for auto-critique guidance | Already in use |

### No New External Dependencies
All work uses APIs already present in the project stack.

## Architecture Patterns

### Recommended Project Structure (additions/modifications)

```
addon/
├── handlers/
│   └── camera.py              # MODIFY: add handle_fast_viewport_capture using render.opengl
src/blend_ai/
├── tools/
│   └── screenshot.py          # MODIFY: add mode parameter to get_viewport_screenshot
├── prompts/
│   └── workflows.py           # MODIFY: add auto_critique_workflow prompt
tests/
├── test_tools/
│   └── test_screenshot.py     # NEW: tests for screenshot tool with mode parameter
├── test_addon/test_handlers/
│   └── test_camera_handler.py # NEW: tests for fast_viewport_capture handler
├── test_tools/
│   └── test_auto_critique_prompt.py  # NEW: tests for auto-critique prompt content
```

### Pattern 1: Fast Viewport Capture (Handler)

**What:** A new handler `handle_fast_viewport_capture` that uses `bpy.ops.render.opengl()` instead of `bpy.ops.render.render()`.

**Key difference from current handler:**
- `bpy.ops.render.opengl(write_still=True)` captures the 3D viewport as-is (whatever shading mode is active)
- Does NOT go through the Cycles/EEVEE render pipeline
- Does NOT trigger `render_pre`/`render_complete` handlers (no render guard interaction)
- Result is stored in `bpy.data.images['Render Result']` just like a normal render
- Much faster: milliseconds vs seconds/minutes

**Example:**
```python
def handle_fast_viewport_capture(params: dict) -> dict:
    """Capture viewport using OpenGL render (fast, no render cycle)."""
    width = params.get("width", 1920)
    height = params.get("height", 1080)

    scene = bpy.context.scene
    
    # Store and set resolution
    orig_x = scene.render.resolution_x
    orig_y = scene.render.resolution_y
    orig_pct = scene.render.resolution_percentage
    
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100

    try:
        # OpenGL render — captures viewport directly, no render guard triggered
        bpy.ops.render.opengl(write_still=True)
        
        # Result is in the Render Result image
        img = bpy.data.images.get("Render Result")
        if img is None:
            raise RuntimeError("No render result after opengl capture")
        
        # Save to temp file and encode
        temp_dir = tempfile.mkdtemp()
        filepath = os.path.join(temp_dir, "viewport_fast.png")
        
        img.save_render(filepath)
        
        with open(filepath, "rb") as f:
            image_data = f.read()
        
        result = {
            "base64": base64.b64encode(image_data).decode("ascii"),
            "format": "png",
            "width": width,
            "height": height,
            "mode": "fast",
        }
        
        # Cleanup
        try:
            os.remove(filepath)
            os.rmdir(temp_dir)
        except OSError:
            pass
        
        return result
    finally:
        scene.render.resolution_x = orig_x
        scene.render.resolution_y = orig_y
        scene.render.resolution_percentage = orig_pct
```

**Context requirement:** `bpy.ops.render.opengl()` requires a valid 3D viewport context. In Blender's addon thread context, this may need an explicit context override. The existing capture handler uses `bpy.ops.render.render()` which works without context override. For `opengl`, we may need:
```python
# Find a 3D viewport area for context
for window in bpy.context.window_manager.windows:
    for area in window.screen.areas:
        if area.type == 'VIEW_3D':
            with bpy.context.temp_override(window=window, area=area):
                bpy.ops.render.opengl(write_still=True)
            break
```

### Pattern 2: MCP Tool Update (mode parameter)

**What:** Add a `mode` parameter to the existing `get_viewport_screenshot` tool. Default to `"fast"` (opengl), with `"full"` as fallback for high-quality renders.

```python
@mcp.tool()
def get_viewport_screenshot(
    max_size: int = 1000,
    mode: str = "fast",
) -> dict[str, Any]:
    """Capture a screenshot of the current Blender 3D viewport.

    Args:
        max_size: Maximum size in pixels for the largest dimension (default: 1000).
        mode: Capture mode - 'fast' for instant viewport capture (default), 
              'full' for a complete render through the active render engine.

    Returns:
        Dict with base64-encoded PNG image data, width, height, and mode.
    """
```

### Pattern 3: Auto-Critique Prompt

**What:** An MCP prompt that instructs the LLM to capture and self-critique after structural changes.

```python
@mcp.prompt()
def auto_critique_workflow() -> str:
    """Guide the LLM to automatically capture and critique its work."""
    return (
        "## Auto-Critique Visual Feedback Workflow\n\n"
        "After performing any of these structural operations, ALWAYS capture a viewport "
        "screenshot using `get_viewport_screenshot(mode='fast')` and critique what you see:\n\n"
        "### Operations that require auto-critique:\n"
        "- Adding objects (mesh, light, camera, curve, etc.)\n"
        "- Deleting objects or geometry\n"
        "- Boolean operations (union, difference, intersect, slice)\n"
        "- Applying modifiers\n"
        "- Sculpting operations\n"
        "- Material/shader changes\n"
        "- Lighting changes\n"
        "- Camera positioning\n\n"
        "### Operations that do NOT need auto-critique:\n"
        "- Renaming objects\n"
        "- Setting properties (without visual impact)\n"
        "- Querying scene info\n"
        "- Collection organization\n"
        "- File save/export\n"
        "- Keyframe insertion (unless previewing animation)\n\n"
        "### When critiquing, check:\n"
        "1. Does the object look correct from this angle?\n"
        "2. Are proportions realistic? (Refer to scale_reference_guide)\n"
        "3. Is the topology clean? (No obvious artifacts, floating geometry)\n"
        "4. Is lighting adequate to see the result?\n"
        "5. What should be improved next?\n\n"
        "### Token Budget\n"
        "- Limit critique to 2-3 sentences.\n"
        "- Only capture ONE screenshot per structural operation.\n"
        "- Do NOT capture screenshots during multi-step sequences; capture ONCE at the end.\n"
    )
```

### Anti-Patterns to Avoid

- **Calling `bpy.ops.render.opengl()` without a 3D viewport context**: The operator needs a VIEW_3D area. Always use `temp_override` to provide proper context.
- **Using full render as default**: The old `bpy.ops.render.render()` is too slow for feedback loops. Default to fast mode.
- **Auto-screenshot on every single tool call**: This wastes tokens. The prompt must explicitly limit screenshots to structural changes only.
- **Not restoring render settings**: Always restore resolution_x, resolution_y, resolution_percentage in a finally block.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Viewport pixel capture | Custom offscreen buffer (gpu module) | `bpy.ops.render.opengl(write_still=True)` | Official operator, handles all viewport states and overlays correctly |
| Image to base64 | Custom pixel array → PNG encoding | `img.save_render(filepath)` + `base64.b64encode()` | Blender handles PNG encoding; we just read the file |
| Auto-critique logic | Server-side screenshot trigger system | MCP prompt (client-side LLM behavior) | MCP is stateless; server can't drive multi-step loops |

## Common Pitfalls

### Pitfall 1: OpenGL render without VIEW_3D context
**What goes wrong:** `bpy.ops.render.opengl()` raises `RuntimeError: Operator bpy.ops.render.opengl.poll() failed` when called from a context without a 3D viewport.
**Why it happens:** The operator's poll function checks for a VIEW_3D area in the current context. The addon's TCP handler thread doesn't have one.
**How to avoid:** Use `bpy.context.temp_override()` with a window and VIEW_3D area.
**Warning signs:** `poll() failed` or `context is incorrect` errors.

### Pitfall 2: Render Result image not available
**What goes wrong:** `bpy.data.images.get("Render Result")` returns None after `render.opengl()`.
**Why it happens:** This can happen if Blender hasn't completed the write. Unlikely but possible on first call.
**How to avoid:** Check for None and raise a clear error. Alternatively, use `write_still=True` and read the written file directly.

### Pitfall 3: Resolution settings leak
**What goes wrong:** Screenshot changes `resolution_x`/`resolution_y` and doesn't restore them, affecting subsequent renders.
**Why it happens:** Exception before restore code.
**How to avoid:** Always restore in a `finally` block (existing handler pattern).

### Pitfall 4: Token explosion from auto-critique
**What goes wrong:** LLM captures screenshots after every single operation, consuming huge amounts of tokens on base64 image data.
**Why it happens:** Prompt doesn't clearly delineate which operations warrant screenshots.
**How to avoid:** Prompt explicitly lists structural operations (add/delete/boolean/apply) vs non-structural (rename/query/organize). Also instructs to batch: capture ONCE at end of multi-step sequence.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4.4 |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_tools/test_screenshot.py tests/test_tools/test_auto_critique_prompt.py -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | File |
|--------|----------|-----------|------|
| FEED-01 | get_viewport_screenshot(mode="fast") sends fast_viewport_capture command | unit | tests/test_tools/test_screenshot.py |
| FEED-01 | get_viewport_screenshot(mode="full") sends capture_viewport command (existing) | unit | tests/test_tools/test_screenshot.py |
| FEED-01 | fast_viewport_capture handler uses bpy.ops.render.opengl (not render.render) | unit | tests/test_addon/test_handlers/test_camera_handler.py |
| FEED-01 | fast_viewport_capture restores resolution settings in finally block | unit | tests/test_addon/test_handlers/test_camera_handler.py |
| FEED-01 | fast_viewport_capture returns base64, format, width, height, mode keys | unit | tests/test_addon/test_handlers/test_camera_handler.py |
| FEED-02 | auto_critique_workflow prompt returns non-empty string | unit | tests/test_tools/test_auto_critique_prompt.py |
| FEED-02 | auto_critique_workflow mentions get_viewport_screenshot | unit | tests/test_tools/test_auto_critique_prompt.py |
| FEED-02 | auto_critique_workflow lists structural operations that require screenshots | unit | tests/test_tools/test_auto_critique_prompt.py |
| FEED-03 | auto_critique_workflow explicitly lists operations that do NOT need screenshots | unit | tests/test_tools/test_auto_critique_prompt.py |
| FEED-03 | auto_critique_workflow mentions token budget or limiting screenshots | unit | tests/test_tools/test_auto_critique_prompt.py |

## Sources

### Primary (HIGH confidence)
- `docs.blender.org/api/current/bpy.ops.render.html` — `bpy.ops.render.opengl(write_still=True, view_context=True)` API confirmed in current Blender docs
- Existing codebase (`addon/handlers/camera.py`, `src/blend_ai/tools/screenshot.py`) — current implementation patterns
- `docs.blender.org/api/current/bpy.context.html` — `temp_override()` context manager for operator context

### Secondary (MEDIUM confidence)
- Blender community patterns for `render.opengl` usage in addons — common pattern uses `temp_override` for background thread contexts

## Metadata

**Confidence breakdown:**
- Fast viewport capture (FEED-01): HIGH — `render.opengl` is a well-documented, stable Blender operator
- Auto-critique prompt (FEED-02): HIGH — static content, no technical unknowns
- Token safety prompt (FEED-03): HIGH — static content in same prompt, clear guidelines
- Context override for opengl: MEDIUM — `temp_override()` is the documented approach but specific behavior from addon TCP thread needs runtime verification

**Research date:** 2026-03-24
**Valid until:** 2026-09-24
