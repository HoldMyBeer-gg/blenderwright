# Pitfalls Research

**Domain:** Blender MCP Server — visual feedback loops, extension suggestions, API version upgrades, workflow intelligence
**Researched:** 2026-03-23
**Confidence:** HIGH (codebase analysis + official Blender release notes + community postmortems)

---

## Critical Pitfalls

### Pitfall 1: capture_viewport Uses bpy.ops.render.render — Blocks Main Thread During Full Render

**What goes wrong:**
The current `handle_capture_viewport` calls `bpy.ops.render.render(write_still=True)` to produce screenshots. This is a full Cycles/EEVEE render, not a viewport capture. It blocks the main thread for the full render duration (seconds to minutes), sets `render_guard.is_rendering = True`, and causes every subsequent MCP command to receive a `busy` response. When auto-screenshot is invoked as a feedback step after every build operation, this becomes a hard serialization point that makes multi-step workflows grind to a halt.

**Why it happens:**
`bpy.ops.render.opengl` (viewport capture via OpenGL/Vulkan, fast) and `bpy.ops.render.render` (full path-traced render, slow) look superficially similar. Using the full render is the easiest path to a PNG file, but is the wrong primitive for a feedback screenshot.

**How to avoid:**
Use `bpy.ops.render.opengl(write_still=True)` with a `temp_override` context pointing at the 3D viewport to capture what the artist actually sees in milliseconds. The render guard must NOT be set for OpenGL viewport captures — they do not block the main thread. Validate at test time that screenshot latency is under 500ms on a mid-range GPU.

**Warning signs:**
- Screenshot tool takes more than 1-2 seconds
- The `is_rendering` flag is `True` immediately after calling capture
- Any tool call immediately after `get_viewport_screenshot` returns `busy`
- Cycles noise visible in screenshots meant to show topology

**Phase to address:**
Auto-screenshot feedback loop phase (first milestone). The fix must land before the feedback loop is wired up, or every feedback cycle will deadlock.

---

### Pitfall 2: render_guard Stuck State Is Not Reset on Addon Reload or Blender Crash-Recovery

**What goes wrong:**
`RenderGuard` uses a `threading.Event`. The `on_render_complete` and `on_render_cancel` handlers clear it. If Blender crashes mid-render, if the addon is reloaded while rendering, or if a render is cancelled via the UI in a way that does not fire the registered handler (e.g., `SIGINT` during batch render), the event stays set permanently. Every subsequent MCP command returns `busy` until Blender is fully restarted.

**Why it happens:**
`bpy.app.handlers` callbacks are not called when Blender recovers from a crash or when the GIL is released during a hard kill. The handler registration in `__init__.py` is also cleared on addon disable/re-enable, but the global `render_guard` object (already imported by `server.py`) retains its state.

**How to avoid:**
Add a `force_clear()` method to `RenderGuard` and expose it as an MCP tool (`reset_render_guard`). Register a `bpy.app.handlers.load_post` handler that calls `render_guard.force_clear()` — this fires on every new file load including crash recovery. Add a timeout fallback in `BlenderConnection.send_command`: if `busy` continues for longer than `bpy.context.scene.render.resolution_x * scene.render.resolution_y / PIXEL_THROUGHPUT_ESTIMATE` seconds, log a warning and surface a human-readable error rather than silently retrying for 5 minutes.

**Warning signs:**
- All commands return `busy` after a render that appeared to finish
- `render_guard.is_rendering` is `True` in the N-panel status
- Blender was force-quit during a previous render session

**Phase to address:**
Bug fixes / hardening phase. Precondition for auto-screenshot (a broken render guard makes the feedback loop permanently stuck).

---

### Pitfall 3: Blender 5.0 Broke EEVEE Engine Identifier Used in Rendering Handler

**What goes wrong:**
The rendering handler checks `bpy.context.scene.render.engine == "CYCLES"` and falls back to EEVEE for samples via `bpy.context.scene.eevee.taa_render_samples`. In Blender 5.0, EEVEE's engine identifier changed from `BLENDER_EEVEE_NEXT` (Blender 4.2–4.x) to `BLENDER_EEVEE`. Any code with hard-coded `"BLENDER_EEVEE_NEXT"` silently sets the wrong engine or skips sample configuration entirely.

**Why it happens:**
The identifier was renamed when EEVEE-Legacy was removed and EEVEE-Next became the only EEVEE variant. Code written for Blender 4.2–4.x used `BLENDER_EEVEE_NEXT`; code written before 4.2 used `BLENDER_EEVEE`. The rename in 5.0 invalidates both old spellings.

**How to avoid:**
Use `bpy.app.version` to branch at runtime, or better: read the engine identifier from `bpy.context.scene.render.engine` directly and compare without hard-coding. Add a compatibility shim that normalizes engine names. Add a Blender-version-specific test suite that asserts the identifier is correct for the installed version.

**Warning signs:**
- `set_render_engine` with value `"BLENDER_EEVEE"` raises an enum validation error on Blender 4.x
- `set_render_samples` silently has no effect (wrong branch taken)
- Render outputs look different than expected (wrong engine active)

**Phase to address:**
Blender 5.1 compatibility phase. Must audit all hard-coded engine/property string literals.

---

### Pitfall 4: Blender 5.0 Renamed GreasePencil Types — gpencil Handler Will Crash on 5.x

**What goes wrong:**
In Blender 5.0, `bpy.types.GreasePencil` was renamed to `bpy.types.Annotation` and `bpy.data.grease_pencils` became `bpy.types.annotations`. The `gpencil.py` handler and any code referencing the old type names will raise `AttributeError` on Blender 5.x.

**Why it happens:**
Blender separated "Grease Pencil objects" (for 3D drawing/animation) from "Annotations" (viewport overlay notes). The rename reflects that split. The old names existed through 4.x but were removed in 5.0.

**How to avoid:**
Audit `addon/handlers/gpencil.py` and `src/blend_ai/tools/gpencil.py` against the 5.0 API. Use `bpy.app.version >= (5, 0, 0)` guards around any type-name-sensitive code. Consider whether the gpencil handler should target Grease Pencil v3 objects (`bpy.types.GreasePencilv3`) or annotation objects — they are separate data-blocks in 5.x.

**Warning signs:**
- `AttributeError: module 'bpy.types' has no attribute 'GreasePencil'` at import time on 5.x
- gpencil tools all fail immediately on Blender 5.x installs

**Phase to address:**
Blender 5.1 compatibility phase. The gpencil handler needs a full audit.

---

### Pitfall 5: bpy.ops.render.opengl Requires a Valid OpenGL/Vulkan Context — Fails in Headless Blender

**What goes wrong:**
`bpy.ops.render.opengl` reads from the GPU framebuffer. If Blender is launched headless (`--background`), there is no display, no GPU context, and the operator will either silently produce a black image or raise `RuntimeError: poll() context error`. The auto-screenshot feedback loop becomes useless or broken in CI environments.

**Why it happens:**
Viewport screenshots inherently require a rendered frame in the GPU buffer. This is an architectural constraint of Blender's GPU pipeline, not a bug. It is also affected by Blender 4.5's migration from OpenGL to Vulkan as the primary backend — viewport capture that worked on OpenGL may behave differently under Vulkan on some platforms.

**How to avoid:**
Document that the MCP server requires Blender running with a display. Add a pre-flight check in `handle_capture_viewport` that tests `bpy.context.screen` is not None before attempting capture, and returns a structured error (not a crash) if headless. For CI test purposes, mock the capture handler to return a known PNG fixture rather than calling `bpy.ops`.

**Warning signs:**
- Screenshot returns a pure black image
- `poll() context error` in the Blender console during capture attempts
- Test failures that only appear in CI (headless) but not locally

**Phase to address:**
Auto-screenshot feedback loop phase. Add the pre-flight check as part of the implementation, and add the CI mock fixture at the same time.

---

### Pitfall 6: Auto-Screenshot Feedback Loop Creates Runaway Token Consumption

**What goes wrong:**
If the LLM is prompted to "always take a screenshot after every tool call" without a token budget, a single 10-step modeling session can easily accumulate 5–10 images × 3–6 retry cycles = 30–60 base64-encoded PNG frames in context. At 1000px resolution, each frame encodes to ~200KB base64 = ~267K characters. This can exhaust context windows and billing budgets mid-session.

**Why it happens:**
Prompt templates that say "verify your work visually" without specifying frequency create unbounded screenshot calls. The feedback loop is only valuable when something has visibly changed — calling it after metadata-only changes (e.g., renaming an object) wastes tokens with identical images.

**How to avoid:**
The `blender_best_practices` prompt should specify: take a screenshot only after structural changes (add/delete/boolean/apply), not after parameter or metadata changes. Implement a `max_size` default of 800 (not 1000) for feedback screenshots. Consider returning image dimensions in the tool response so the LLM can decide whether to screenshot again. Document a "screenshot budget" concept in the prompt.

**Warning signs:**
- Session context fills in fewer than 20 tool calls
- LLM calls `get_viewport_screenshot` after `rename_object` or `set_render_samples`
- Response latency grows across a session (growing context)

**Phase to address:**
Expert-quality MCP prompts phase. The prompt must constrain screenshot frequency before the feedback loop is shipped.

---

### Pitfall 7: code_exec Handler Exposes Full Python Environment With No Sandboxing

**What goes wrong:**
`handle_execute_code` calls `exec(code, {"__builtins__": __builtins__})`. Passing the real `__builtins__` gives the executed code access to `open()`, `os`, `subprocess`, `importlib`, and everything else in the Python stdlib. An LLM that generates code to "list available textures" could accidentally (or via prompt injection) exfiltrate files, make network calls, or fork processes. The fact that this runs inside Blender's Python on the user's local machine makes the blast radius larger, not smaller — `bpy.utils.extension_path_user()` etc. give access to user data paths.

**Why it happens:**
`exec` is the simplest way to run arbitrary code. Restricting builtins requires more effort and breaks legitimate uses. The `code_exec` handler was likely added as an escape hatch for operations not yet covered by the tool set.

**How to avoid:**
Restrict builtins to a safe allowlist: `{"__builtins__": {"print": print, "range": range, "len": len, ...}}`. Block `import`, `open`, `os`, `subprocess`, `sys`, and `socket` via the restricted namespace. Alternatively, add a user-facing "unsafe mode" toggle in the N-panel that defaults to OFF, with the handler refusing to execute unless the toggle is enabled. The roadmap requirement says "harden security" — this is the highest-severity item in the codebase.

**Warning signs:**
- Code snippets sent to `execute_code` that `import os` or `import subprocess`
- Any MCP session that sends code using `open()` for file I/O
- LLM using `execute_code` to work around unavailable tools rather than structured tool calls

**Phase to address:**
Security hardening phase. This should be addressed early — ideally before any new features are shipped — because each new tool added reduces the motivation to use `code_exec` and makes a stricter sandbox easier to justify.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `bpy.ops.render.render` for screenshots | Simple, reuses existing infrastructure | Blocking render for every screenshot; activates render guard; wrong semantic | Never — use `render.opengl` |
| Hard-coded engine string `"BLENDER_EEVEE_NEXT"` | Works on 4.2–4.x | Silently broken on 5.0+ | Never — read from `bpy.context.scene.render.engine` |
| `exec(code, {"__builtins__": __builtins__})` | Full API access | Full RCE on user machine | Only with explicit user consent toggle |
| Version checks via `bpy.app.version` inline per handler | Quick fix | Scattered; hard to audit | Acceptable for one-off renames; use compat shim for systemic changes |
| Prompt strings as plain Python string literals | Simple to edit | No testing, no LLM evaluation, drift undetected | Acceptable only if there is a prompt quality regression test |
| Empty `test_addon/test_handlers/` directory | Faster to ship handlers | Any handler regression goes undetected until it crashes in production | Never — handlers are the critical path |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `bpy.ops.*` from timer callback | Calling operators that need a specific context (e.g., `EDIT` mode) without `temp_override` | Always use `bpy.context.temp_override(area=area, region=region)` and call `.poll()` first |
| `bpy.app.timers` queue at 10ms | Timer fires every 10ms while Blender is idle, causing viewport redraws and performance hit on complex scenes | Keep `_process_queue` fast (no bpy calls if queue empty); return `0.1` (100ms) when queue is empty, `0.01` when actively draining |
| `render_pre` / `render_complete` handlers | Handlers registered with `persistent=False` are cleared on file load, causing the render guard to never clear | Register with `persistent=True` or re-register in `load_post` |
| MCP tool return type | Returning raw dicts without encoding image data as `image/png` MCP content type | Use FastMCP's `Image` return type or the correct MIME content block so the LLM client can display images |
| Extension/addon suggestion | Checking if an extension is "installed" by testing `import addon_name` | Use `bpy.context.preferences.addons` or the `extensions` API; import test can produce false positives from unregistered modules |
| Blender Extensions platform API | Hard-coding extension search against `extensions.blender.org` URL structure | Use the official JSON API endpoint; document the API contract and version-pin it |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| 10ms timer polling in `thread_safety._process_queue` with a complex scene | Blender UI becomes sluggish; viewport frame rate drops below 24fps | Return higher interval (`0.1s`) when queue is empty; only drop to `0.01s` when a command is queued | Scenes with >100k polygons or many objects |
| Large base64 PNG in every MCP response | MCP context grows; LLM responses slow down; token costs spike | Use `max_size=800` default; allow client to request smaller thumbnails; strip screenshots from tool history | After 5–10 sequential screenshot calls |
| `send_command` with `BUSY_MAX_RETRIES=150` and `BUSY_RETRY_DELAY=2.0` | 5-minute silent hang when render guard is stuck | Add a cap at 60s for non-render commands; expose progress to the LLM via intermediate responses | Any time render guard gets stuck |
| N-panel polling every viewport redraw | UI freezes if `is_running` check involves socket I/O | Keep status checks to local state only — no socket I/O in panel `poll()` or `draw()` | Whenever Blender redraws the UI heavily |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `exec(code, {"__builtins__": __builtins__})` with real builtins | Full RCE: filesystem access, subprocess execution, network calls, bpy data exfiltration | Restricted builtins allowlist + user-facing "unsafe mode" toggle defaulting to OFF |
| Listing available commands in error response (`sorted(_handlers.keys())`) | Enumeration: attacker can discover all registered command names | Return generic "unknown command" without the full list in production; reserve for debug mode |
| Path parameters without canonicalization | Path traversal: `filepath=../../.ssh/id_rsa` passes `validate_path` if only extension is checked | Canonicalize with `os.path.realpath`; verify path is under an allowed base directory |
| `render.filepath` set from untrusted params then not sanitized | Blender writes render output to arbitrary filesystem locations | Validate filepath is within a user-approved output directory before setting |
| TCP socket listens on `0.0.0.0` if host override is passed | Remote network access: MCP commands executable from any machine on the network | Enforce `127.0.0.1` in code, not just as default; reject any non-loopback host at bind time |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Auto-screenshot returns camera render, not viewport view | User sees a different view than they expect; confusing if camera is not positioned at scene | Use `bpy.ops.render.opengl` in viewport context, not `bpy.ops.render.render` |
| Extension suggestion fires on every tool call | Noise; users ignore suggestions | Suggest once per session per capability gap; cache suggestions; suppress if addon is already installed |
| Expert prompt guidance is static text | LLM applies advice uniformly regardless of scene state | Include scene-state-aware conditionals in prompts (e.g., "if mesh has N-gons, run tris_to_quads first") |
| Workflow tools that chain 10 operations silently | If step 3 fails, user sees no partial progress and no recovery path | Return per-step status from workflow tools; stop on first error and report which step failed and why |
| `busy` response during screenshot | User sees no feedback during 30-second render | If screenshot is requested during a render, return the in-progress render image if available, or a clear message with estimated time |

---

## "Looks Done But Isn't" Checklist

- [ ] **Auto-screenshot:** Often implemented with `render.render` (slow) instead of `render.opengl` (fast) — verify screenshot latency is under 500ms and render guard is not set during capture
- [ ] **Blender 5.x compat:** Often tested only on the development machine's Blender version — verify against Blender 5.1 specifically by running the test suite under that binary
- [ ] **EEVEE samples:** `handle_set_render_samples` branches on `"CYCLES"` — verify the EEVEE branch uses the correct 5.x property name (`eevee.taa_render_samples` may have moved)
- [ ] **Render guard reset:** `render_complete` and `render_cancel` handlers registered — verify they are registered with `persistent=True` so they survive file loads
- [ ] **code_exec security:** Handler exists and is registered — verify it actually enforces a restricted builtins set, not the real `__builtins__`
- [ ] **Extension suggestions:** Suggestion list is populated — verify each suggested extension is checked against `bpy.context.preferences.addons` before suggesting (no false "install X" advice when X is already installed)
- [ ] **Workflow prompts:** Prompt text exists — verify the prompt specifically addresses screenshot frequency budget, otherwise the feedback loop will be invoked on every single tool call
- [ ] **Addon handler tests:** `test_addon/test_handlers/` directory exists — verify it contains actual test files, not just `__init__.py`

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Screenshot uses full render instead of opengl | LOW | Replace `bpy.ops.render.render` with `bpy.ops.render.opengl` in `handle_capture_viewport`; update render guard to not set during opengl capture |
| Render guard permanently stuck | LOW | Add `reset_render_guard` MCP tool; add `load_post` handler to auto-clear on file load |
| EEVEE identifier broken on 5.x | LOW | Audit all engine string comparisons; add compat constant; fix takes < 1 hour |
| gpencil handler crashes on 5.x | MEDIUM | Full audit of gpencil handler against 5.0 API; may need to split into grease-pencil-v3 vs. annotation tools |
| code_exec RCE exploited | HIGH | Immediately disable the tool via the allowlist; audit for any data exfiltration; add restricted builtins and user consent toggle before re-enabling |
| Token runaway from screenshot loop | MEDIUM | Add screenshot frequency guard to prompt; add a session-level screenshot count cap in `get_viewport_screenshot` tool |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Screenshot uses full render (blocks main thread) | Auto-screenshot feedback loop phase | Screenshot tool latency test: must complete in under 500ms |
| Render guard stuck state | Bug fixes / hardening phase | Test: call `render_image`, kill render mid-way, verify guard clears automatically |
| EEVEE identifier broken on 5.x | Blender 5.1 compatibility phase | Full test suite run under Blender 5.1 binary; `set_render_engine("BLENDER_EEVEE")` succeeds |
| GreasePencil types renamed | Blender 5.1 compatibility phase | `gpencil.*` tools execute without AttributeError on 5.x |
| opengl capture fails headless | Auto-screenshot feedback loop phase | CI mocks capture handler; local tests use real capture with display |
| Token runaway from screenshots | Expert prompts phase | Prompt review: screenshot budget guidance is explicit; integration test with simulated LLM session |
| code_exec unsandboxed | Security hardening phase | Test: `execute_code` with `import os` raises `ImportError` or returns structured error |
| Handler tests missing | Test coverage improvement phase | All files in `addon/handlers/` have a corresponding test in `test_addon/test_handlers/` |

---

## Sources

- Blender 5.1 Python API release notes: https://developer.blender.org/docs/release_notes/5.1/python_api/
- Blender 5.0 Python API release notes: https://developer.blender.org/docs/release_notes/5.0/python_api/
- Blender compatibility index: https://developer.blender.org/docs/release_notes/compatibility/
- Blender bpy.ops documentation: https://docs.blender.org/api/current/bpy.ops.html
- Blender application timers: https://docs.blender.org/api/current/bpy.app.timers.html
- MCP security breach timeline: https://authzed.com/blog/timeline-mcp-breaches
- Blender scripting security: https://docs.blender.org/manual/en/latest/advanced/scripting/security.html
- Codebase analysis: `/Users/michael/code/blend-ai/addon/handlers/camera.py` (capture_viewport implementation), `/Users/michael/code/blend-ai/addon/render_guard.py`, `/Users/michael/code/blend-ai/addon/thread_safety.py`, `/Users/michael/code/blend-ai/addon/handlers/code_exec.py`

---
*Pitfalls research for: Blender MCP Server — visual feedback, extension suggestions, API upgrade, workflow intelligence*
*Researched: 2026-03-23*
