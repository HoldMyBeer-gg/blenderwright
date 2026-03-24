# Codebase Concerns

**Analysis Date:** 2026-03-23

## Tech Debt

**Arbitrary Code Execution (Code Injection Risk):**
- Issue: `execute_blender_code()` tool allows unrestricted Python code execution in Blender with `exec()`. The addon handler at `addon/handlers/code_exec.py` uses `exec(code, {"__builtins__": __builtins__})` which is unsafe — `__builtins__` contains full module access, including `os`, `subprocess`, file access, etc.
- Files: `src/blend_ai/tools/code_exec.py`, `addon/handlers/code_exec.py` (lines 20, 26)
- Impact: Any untrusted prompt/agent can execute arbitrary Python code, read files, modify filesystem, run commands. Major security vulnerability if used with adversarial prompts.
- Fix approach: Either (1) remove the tool entirely (safest), (2) implement a restricted sandbox with limited builtins and blocked modules, or (3) require explicit user confirmation before code execution.

**Global State Management - Race Conditions:**
- Issue: Multiple global singletons without proper synchronization. `addon/server.py` has `_server` global and `addon/thread_safety.py` has `_next_id` counter incremented without locks. Thread-safe for Blender's single-threaded constraint, but fragile to future changes.
- Files: `addon/server.py` (lines 171-180), `addon/thread_safety.py` (lines 23-25)
- Impact: If future code paths increment `_next_id` from multiple threads or if Blender callback execution changes, request IDs could collide, causing response queue mismatches and hung requests.
- Fix approach: Add explicit locks around `_next_id` access, document the single-threaded assumption clearly, or use a thread-safe counter (e.g., `threading.Lock` + int, or `queue.Queue` for ID generation).

**Parameter Validation Inconsistency:**
- Issue: Some handlers skip parameter validation. E.g., `addon/handlers/rendering.py` lines 9-11, 35, 49 directly access `params[]` without `.get()` or type checks. If a parameter is missing, it throws unhandled KeyError instead of returning a proper error response.
- Files: `addon/handlers/rendering.py` (lines 9, 35, 49, 83), `addon/handlers/objects.py` (lines 74, 92)
- Impact: Clients sending incomplete requests cause handler crashes rather than graceful error messages. Dispatcher catches the exception (line 44 of `addon/dispatcher.py`), so user sees error, but no validation prevents bad data propagation.
- Fix approach: Consistently use `params.get()` with defaults or raise `ValueError` early. Create a validation helper to unpack params safely.

**Timeout Handling Incomplete:**
- Issue: Connection timeout is 30 seconds globally (`src/blend_ai/connection.py` line 28), but thread-safety timeout is 60 seconds (`addon/thread_safety.py` line 51). If a main-thread function takes >30s, the connection layer times out while the handler is still executing, causing orphaned queue responses and resource leaks.
- Files: `src/blend_ai/connection.py` (line 28), `addon/thread_safety.py` (line 51)
- Impact: Long operations (renders, complex modifiers) timeout on the client even if the addon completes them. Potential orphaned queue entries in `_response_queues` dict.
- Fix approach: Make timeouts configurable per-command. Sync connection timeout ≥ thread-safety timeout. Add cleanup for orphaned queue entries after timeout.

**Missing Bounds Validation on Numeric Inputs:**
- Issue: Some tools validate ranges (e.g., `src/blend_ai/tools/materials.py` lines 162-172 check metallic/roughness 0.0-1.0), but others don't. E.g., `src/blend_ai/tools/rendering.py` (via MCP) lacks validation for render resolution — could be set to 32768x32768 pixels, crashing Blender or consuming gigabytes of memory.
- Files: `src/blend_ai/tools/rendering.py`, `addon/handlers/rendering.py`
- Impact: Malicious or misconfigured AI prompts can trigger out-of-memory crashes or extremely long render times (Blender becomes unresponsive).
- Fix approach: Add uniform validator helpers with MAX constants. Apply them to all numeric inputs (resolution, samples, frame counts, etc.). Validate upstream in `src/blend_ai/tools/` before sending to addon.

## Known Bugs

**Render Guard Flag Not Cleared on Exception:**
- Issue: `addon/render_guard.py` registers handlers for `render_pre`, `render_complete`, `render_cancel`. If render crashes internally (e.g., out of memory), only `render_cancel` fires; if that handler fails, the flag stays set. Commands will be rejected as "busy" forever.
- Files: `addon/render_guard.py` (lines 25-35), `addon/__init__.py` (lines 29-31)
- Trigger: Start a render with insufficient memory, Blender crashes/recovers, `render_cancel` fails silently.
- Workaround: Restart Blender or call a manual "reset render state" tool (none exists).

**Stale Connection Handling Doesn't Fully Reconnect:**
- Issue: `src/blend_ai/connection.py` line 129 calls `disconnect()` and retries once, but the retry uses the same stale socket reference if reconnect fails partway. The `_socket` may be None but not all cleanup paths set it to None atomically.
- Files: `src/blend_ai/connection.py` (lines 127-136)
- Impact: Connection can deadlock if socket EOF occurs mid-retry.
- Workaround: Multiple retries from MCP level eventually work, but slow.

**Screenshot Tool May Block Indefinitely:**
- Issue: `src/blend_ai/tools/screenshot.py` calls `conn.send_command()` without documenting whether it works during renders. If called while rendering (and render guard is working), the response will timeout as "busy," but the tool doesn't retry.
- Files: `src/blend_ai/tools/screenshot.py`
- Impact: Screenshots requested during render timeout with no fallback.

## Security Considerations

**File Path Traversal Prevention - Incomplete:**
- Risk: `src/blend_ai/validators.py` line 56 resolves paths with `.resolve()`, but doesn't enforce a safe directory root. An AI could request `/etc/passwd` (invalid extension stops it), but could request `/private/var/db/`. Relative paths like `../../../../secrets.blend` get resolved but aren't blocked.
- Files: `src/blend_ai/validators.py` (lines 44-73)
- Current mitigation: File extension whitelist (`.blend`, `.fbx`, `.obj`, etc.) + null byte check.
- Recommendations: (1) Optionally enforce a safe root directory via config, (2) Add explicit path prefix check if root is defined, (3) Document that absolute paths are required and any file on the system can be accessed if valid extension.

**Arbitrary Blender Python API Access:**
- Risk: `execute_blender_code()` is unrestricted. Even if `__builtins__` were restricted, an AI could call `bpy.ops.wm.open_mainfile()` to load any file, or `bpy.context.window.workspace.name = ...` to modify Blender state maliciously.
- Files: `src/blend_ai/tools/code_exec.py`, `addon/handlers/code_exec.py`
- Current mitigation: None (operator-level allowlist exists only in `addon/dispatcher.py` for structured tools).
- Recommendations: Remove `execute_blender_code()` or add explicit allowlist of safe `bpy` calls. Treat as an internal/debugging tool only.

**No Command Auditing/Logging:**
- Risk: All commands execute silently. No log of what was run, when, by whom (if exposed over network).
- Files: `addon/dispatcher.py`, `addon/server.py`
- Impact: If an AI makes destructive changes (delete all objects), there's no audit trail.
- Recommendations: Add optional command logging to `dispatcher.dispatch()`. Log command name, params (excluding code), result, timestamp.

**Local Network Only - But Documented:**
- Risk: Server listens on `127.0.0.1:9876` (localhost only), which is safe. But if someone accidentally exposes it (port forward, network alias), arbitrary remote code execution is possible.
- Files: `addon/server.py` (line 21), `src/blend_ai/connection.py` (line 26)
- Current mitigation: Hardcoded to localhost.
- Recommendations: Document in README that this MUST NOT be exposed. Consider adding a warning on startup if listening on non-localhost.

## Performance Bottlenecks

**Blocking Main Thread on Large Operations:**
- Problem: `addon/thread_safety.py` uses 10ms timer interval (`_process_queue` line 79). Large operations (mesh sculpting, physics sim) block the main thread. During that time, queued commands accumulate, and the render guard is bypassed because the check happens before queue processing.
- Files: `addon/thread_safety.py` (line 79), `addon/server.py` (lines 108-119)
- Cause: Blender's single-threaded API constraint + simple queue polling.
- Improvement path: Document that long operations will appear to hang MCP. Consider adding operation progress/cancellation tokens (not in scope for v0.2.0).

**Connection Pool Not Reused:**
- Problem: Each `mcp.tool()` call creates a fresh connection via `get_connection()` which reuses a global singleton, good. But all socket I/O is synchronous and blocking. If 50 AI agents connect, only one can be served at a time (Blender's main thread serializes all handlers).
- Files: `src/blend_ai/server.py` (lines 18-23)
- Cause: Architectural constraint, not a bug.
- Improvement path: Blender limitation — cannot parallelize. Queue-based architecture already mitigates by processing all pending commands before returning "busy."

**Large Message Sanity Limits:**
- Problem: 100MB limit (`src/blend_ai/connection.py` line 80, `addon/server.py` line 154). Exporting a detailed scene could hit this. No streaming or chunking.
- Files: `src/blend_ai/connection.py` (line 80), `addon/server.py` (line 154)
- Cause: Simple implementation assumes messages fit in memory.
- Improvement path: Document 100MB limit. For huge exports, use file system directly (already possible with `export_file()`).

## Fragile Areas

**Materials Handler - Complex Validation Chain:**
- Files: `src/blend_ai/tools/materials.py` (463 lines), `addon/handlers/materials.py` (443 lines)
- Why fragile: 76 allowed shader node types (lines 45-76 of `src/blend_ai/tools/materials.py`), socket name validation (line 332-335), node connection graph logic. If a new Blender version adds node types or changes socket names, connections fail silently.
- Safe modification: (1) Add unit tests for all 76 node types, (2) Document which Blender versions are tested, (3) Add introspection to query available node types from Blender instead of hardcoding.
- Test coverage: Gaps in node tree connection tests (`test_tools/test_materials.py` focuses on socket validation but not graph connectivity).

**Code Execution Handler - No Sandbox:**
- Files: `addon/handlers/code_exec.py` (36 lines)
- Why fragile: Single `exec()` call with minimal guards. Any refactoring of `__builtins__` restriction will break.
- Safe modification: Either remove entirely or implement a proper AST-based sandbox (complex, fragile).
- Test coverage: No tests for code_exec handler. No tests for restricted builtins enforcement.

**Thread Safety Module - Undocumented Timer Dependency:**
- Files: `addon/thread_safety.py` (92 lines), `addon/server.py` (calls `register_timer()` at line 46)
- Why fragile: Queue processing depends on `bpy.app.timers` callback firing reliably. If Blender blocks rendering or modal dialogs block the main thread, timers stop. If `register_timer()` is called twice, addon crashes (no idempotency check, though `is_registered()` prevents it).
- Safe modification: (1) Add explicit re-registration guard with retry, (2) Document that timers only fire when Blender is idle/responsive, (3) Add diagnostic logging when queue backlog exceeds threshold.
- Test coverage: Addon code not unit tested (requires Blender context). No mock tests for timer behavior.

**Socket Handling - Incomplete Error Recovery:**
- Files: `addon/server.py` (197 lines)
- Why fragile: `_recv_exactly()` (lines 158-168) returns `None` on disconnect, but some callers don't distinguish between `None` and empty bytes. `_handle_client()` catches `OSError` broadly (line 132) without logging context.
- Safe modification: (1) Raise a specific exception instead of returning `None`, (2) Log context (client address, command name) on error, (3) Add explicit client list cleanup with timeout (clients stuck in read).
- Test coverage: No unit tests for socket layer (requires mocking `socket.socket`).

## Scaling Limits

**Single MCP Connection:**
- Current capacity: One concurrent MCP client (e.g., Claude Desktop).
- Limit: `src/blend_ai/server.py` line 18-23 creates a single global `BlenderConnection`. If multiple MCP processes try to use blend-ai simultaneously (unlikely but possible in multi-agent setups), they all share one connection and queue serialization happens at the addon level anyway.
- Scaling path: Not applicable — Blender itself is single-threaded. Multiple agents would bottleneck at Blender's main thread, not at MCP. Document this limitation.

**Command Queue Size:**
- Current: Unbounded `queue.Queue` (`addon/thread_safety.py` line 15).
- Limit: If 1000 commands queue up, all stay in memory. Each command captures closure args — large scenes could balloon memory.
- Scaling path: (1) Add a max queue depth with rejection, (2) Warn when queue depth > 100, (3) Consider async result streaming instead of blocking on each command.

**Render Safety Timeout:**
- Current: 5 minutes max wait for render (`src/blend_ai/connection.py` lines 142-170). After 150 retries of 2s each, command is rejected.
- Limit: Cannot render scenes taking >5 minutes from MCP. User must render directly in Blender.
- Scaling path: Make timeout configurable per-tool via prompt engineering or tool parameters. Document render time limits.

## Dependencies at Risk

**None Explicitly Identified:**
- The project has minimal dependencies (MCP SDK, bpy which is Blender-bundled).
- Risk: MCP SDK updates could break protocol compatibility. Blender API changes (4.0+ only) could make old Blender versions incompatible.
- Migration plan: Monitor MCP SDK releases. Version-gate supported Blender versions (4.0+).

## Missing Critical Features

**No Operation Cancellation:**
- Problem: Long renders or physics sims block all other commands. User cannot cancel a stuck operation from MCP.
- Blocks: Interactive workflows where user wants to interrupt a render and adjust settings.

**No Command Timeout Customization:**
- Problem: Hardcoded 30s timeout in connection, 60s in thread safety. Some operations need more, some need less.
- Blocks: Rendering animations >30s, or batch operations that should fail fast.

**No Persistent Session State:**
- Problem: Each MCP connection is fresh. Blender state (scene, objects, materials) persists in Blender, but MCP has no "context" — every tool call is stateless. An AI must query scene info repeatedly.
- Blocks: Complex multi-step workflows with intermediate checks.
- Note: This is architectural (MCP is stateless), not a bug.

## Test Coverage Gaps

**Addon Handler Code - No Unit Tests:**
- What's not tested: All 23 handler modules (`addon/handlers/`) are integration-level only. No unit tests for parameter unpacking, error handling, edge cases.
- Files: `addon/handlers/*.py` (5500+ lines of untested code)
- Risk: Parameter validation bugs, missing `.get()` calls, unhandled exceptions go undetected. Example: `addon/handlers/rendering.py` line 9 accesses `params["engine"]` without a key check.
- Priority: **High** — 50% of the codebase is untested at unit level.

**Code Execution Sandbox Validation:**
- What's not tested: The `__builtins__` restriction in `addon/handlers/code_exec.py` line 20 is not validated. No test checks that `os.system()` or `open()` is actually blocked.
- Files: `addon/handlers/code_exec.py`
- Risk: False sense of security. If refactored, sandbox could be accidentally removed.
- Priority: **Critical** — security feature without coverage.

**Socket Error Paths:**
- What's not tested: Partial message reads, connection drops mid-message, oversized messages, invalid JSON in `addon/server.py` and `src/blend_ai/connection.py`.
- Files: `addon/server.py`, `src/blend_ai/connection.py`
- Risk: Undetected hangs, memory leaks on dropped connections.
- Priority: **High** — resilience.

**Render Guard Edge Cases:**
- What's not tested: Render that crashes Blender (does `render_cancel` fire?), nested render calls, multiple handlers for same event.
- Files: `addon/render_guard.py`
- Risk: Render flag stuck in "busy" state.
- Priority: **Medium** — observable in testing, but no automation.

**Timeout Boundaries:**
- What's not tested: Operations that take exactly 30s, 60s, edge of BUSY_MAX_RETRIES (150 retries = 5min).
- Files: `src/blend_ai/connection.py`
- Risk: Off-by-one errors at timeout boundaries.
- Priority: **Low** — rare in practice, but flaky tests possible.

---

*Concerns audit: 2026-03-23*
