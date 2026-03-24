# Architecture

**Analysis Date:** 2026-03-23

## Pattern Overview

**Overall:** Layered MCP-to-TCP bridge architecture with thread-safe command dispatch

**Key Characteristics:**
- **Three-tier communication**: AI client → MCP server (stdio) → TCP socket → Blender addon (background thread)
- **Render-aware command queueing**: Automatically detects and retries when Blender is rendering
- **Main-thread execution guarantees**: Background TCP server delegates all Blender API calls to main thread via queue
- **Command allowlist**: Security-first design — only explicitly registered commands are executed
- **Zero telemetry**: All communication stays on localhost (127.0.0.1:9876)

## Layers

**MCP Server Layer (src/blend_ai/):**
- Purpose: Expose Blender operations as MCP tools, resources, and prompts; validate all client inputs before forwarding to Blender
- Location: `src/blend_ai/`
- Contains: Tool definitions, input validators, resource providers, prompt templates, connection manager
- Depends on: `mcp` SDK, `pydantic`, local `BlenderConnection` class
- Used by: Any MCP-compatible client (Claude Code, Claude Desktop, other AI assistants)

**Connection Bridge (src/blend_ai/connection.py):**
- Purpose: Implement TCP socket protocol to communicate with Blender addon; handle render-busy retries with exponential backoff
- Location: `src/blend_ai/connection.py`
- Contains: `BlenderConnection` class with length-prefixed JSON message protocol, automatic retry logic (150 retries at 2s intervals = ~5 minutes)
- Depends on: `socket`, `struct`, `json`, `threading`
- Used by: All tool implementations via `get_connection()`

**Blender Addon TCP Server Layer (addon/server.py):**
- Purpose: Accept TCP connections from MCP server; dispatch commands to handlers; manage render state awareness
- Location: `addon/server.py`
- Contains: `BlenderServer` class (TCP socket server, client connection handling, length-prefixed message protocol)
- Depends on: `socket`, `dispatcher`, `thread_safety`, `render_guard`
- Used by: N-panel UI (`ui_panel.py`), addon initialization (`__init__.py`)

**Command Dispatcher (addon/dispatcher.py):**
- Purpose: Route incoming commands to their handler functions; enforce command allowlist; catch exceptions
- Location: `addon/dispatcher.py`
- Contains: Handler registry, dispatch function, command validation
- Depends on: Handler modules in `addon/handlers/`
- Used by: TCP server's `_handle_client()` method

**Handler Layer (addon/handlers/):**
- Purpose: Implement each Blender operation (161 tools across 24 modules) using Blender's Python API (`bpy`)
- Location: `addon/handlers/` (24 handler modules mirror tool modules in `src/blend_ai/tools/`)
- Contains: Individual handler functions that manipulate Blender state (objects, materials, rendering, etc.)
- Depends on: `bpy` (Blender API), `dispatcher` for registration
- Used by: `dispatcher.dispatch()` on the main thread

**Thread Safety Bridge (addon/thread_safety.py):**
- Purpose: Guarantee that all `bpy` calls execute on Blender's single-threaded main thread
- Location: `addon/thread_safety.py`
- Contains: Command queue, response queues, `bpy.app.timers` callback registration
- Depends on: `bpy`, `queue`, `threading`
- Used by: TCP server's `_handle_client()` when executing dispatched commands

**Render Guard (addon/render_guard.py):**
- Purpose: Track render state via `bpy.app.handlers`; provide thread-safe visibility to TCP server
- Location: `addon/render_guard.py`
- Contains: `RenderGuard` class with `threading.Event` for thread-safe state tracking
- Depends on: `threading`, `bpy.app.handlers`
- Used by: TCP server to return "busy" status; addon init to register handlers

**Input Validation Layer (src/blend_ai/validators.py):**
- Purpose: Sanitize and range-check all inputs before forwarding to Blender
- Location: `src/blend_ai/validators.py`
- Contains: Validators for object names, file paths, numeric ranges, colors, vectors, enums, shader nodes
- Depends on: `pathlib`, `re`, `os`
- Used by: All tool implementations

## Data Flow

**Command Execution Flow:**

1. AI client sends tool call via MCP (stdio)
2. MCP server (FastMCP) deserializes and invokes tool function
3. Tool function calls `get_connection().send_command(command, params)`
4. `BlenderConnection.send_command()` validates, formats JSON, sends length-prefixed message over TCP socket
5. Blender addon's TCP server receives message in background thread
6. TCP server checks `render_guard.is_rendering` — if true, returns "busy" status (client auto-retries)
7. If not rendering, TCP server calls `thread_safety.execute_on_main_thread(dispatcher.dispatch, command, params)`
8. `thread_safety` puts request in queue, waits on response queue (blocking)
9. `bpy.app.timers` callback (`_process_queue`) runs on main thread every 10ms, dequeues request
10. Callback executes `dispatcher.dispatch(command, params)` on main thread
11. Dispatcher looks up handler in registry and invokes it
12. Handler manipulates Blender state via `bpy`
13. Handler returns result dict
14. Dispatcher wraps result in `{"status": "ok", "result": ...}`
15. `thread_safety` puts response in requesting thread's response queue
16. `BlenderConnection.send_command()` receives response, formats JSON, sends over TCP
17. MCP server receives response, returns to tool function
18. Tool function returns to FastMCP, which serializes response to stdio
19. AI client receives tool result

**Render Wait-Retry Cycle:**

1. While rendering, TCP server returns `{"status": "busy", "result": "..."}`
2. Client's `BlenderConnection.send_command()` detects "busy" status
3. Enters retry loop: waits 2 seconds, reconnects, resends command
4. Repeats up to 150 times (max ~5 minutes)
5. When render completes, `render_guard` clears its event
6. Next command execution succeeds

**State Management:**

- **Global connection**: `src/blend_ai/server.py` maintains singleton `_connection: BlenderConnection`
- **Global server**: `addon/server.py` maintains singleton `_server: BlenderServer`
- **Global command queue**: `addon/thread_safety.py` maintains `_command_queue: queue.Queue` and `_response_queues: dict`
- **Global render state**: `addon/render_guard.py` maintains singleton `render_guard: RenderGuard`

All singletons are instantiated lazily and safely (no thread race conditions thanks to GIL and explicit threading primitives).

## Key Abstractions

**BlenderConnection:**
- Purpose: Encapsulates TCP socket communication and render-aware retry logic
- Location: `src/blend_ai/connection.py`
- Pattern: Length-prefixed JSON over TCP with automatic reconnection and exponential backoff
- Implements: Socket connect/disconnect, message send/receive, busy-state polling

**BlenderServer:**
- Purpose: Encapsulates TCP server lifecycle and client connection handling
- Location: `addon/server.py`
- Pattern: Singleton server with background accept loop and per-client handler threads
- Implements: Server start/stop, accept loop, client handler, message framing

**RenderGuard:**
- Purpose: Thread-safe render state tracking
- Location: `addon/render_guard.py`
- Pattern: Wraps `threading.Event` for visibility across thread boundaries
- Implements: Set on pre-render, clear on complete/cancel

**ValidationError:**
- Purpose: Explicit validation failure signaling
- Location: `src/blend_ai/validators.py`
- Pattern: Custom exception raised by validators, caught by tool implementations
- Implements: Clear error messages for invalid inputs

## Entry Points

**MCP Server Entry (main):**
- Location: `src/blend_ai/server.py:main()`
- Triggers: `uv run --directory /path/to/blend-ai blend-ai` or `python -m blend_ai.server`
- Responsibilities: Create FastMCP instance, load all tool/resource/prompt modules, run stdio transport

**Blender Addon Entry (register):**
- Location: `addon/__init__.py:register()`
- Triggers: User enables addon in Blender preferences
- Responsibilities: Register UI classes, register handler modules, attach render event handlers

**Server Start (UI):**
- Location: `addon/ui_panel.py` operator `BLENDAI_OT_StartServer`
- Triggers: User clicks "Start Server" in N-panel
- Responsibilities: Call `addon_server.start_server()`, which creates and starts TCP server in background thread

**Tool Invocation:**
- Location: Each tool in `src/blend_ai/tools/` (e.g., `tools/scene.py:get_scene_info()`)
- Triggers: MCP client calls tool via MCP protocol
- Responsibilities: Validate inputs, call `get_connection().send_command()`, handle response, return to client

## Error Handling

**Strategy:** Layered validation → early rejection before Blender execution

**Patterns:**

- **Input validation (client-side)**: Tool functions call validators (in `src/blend_ai/validators.py`) on parameters before sending command. Raises `ValidationError` which propagates to MCP client as error response.

- **Handler exceptions (server-side)**: Handler functions raise exceptions (ValueError, RuntimeError, etc.). Dispatcher wraps in `{"status": "error", "result": "ExceptionType: message"}`.

- **Connection errors**: `BlenderConnection` raises `BlenderConnectionError` on socket failures, lost connections, or timeout. Attempts automatic reconnection once; if fails, raises to tool function.

- **Render timeouts**: If Blender renders for too long (150 retries), `BlenderConnection` raises `BlenderConnectionError` with clear message.

- **Message framing errors**: TCP server catches `json.JSONDecodeError` and returns error response without closing connection.

**Example error flow:**
```
Tool calls validator → ValidationError raised
→ Tool catches and raises RuntimeError with user-friendly message
→ MCP server logs and returns error to client
```

## Cross-Cutting Concerns

**Logging:**
- Implementation: Python `logging` module with logger per module (e.g., `logger = logging.getLogger(__name__)`)
- Location: Used in `src/blend_ai/connection.py` for retry logging
- Client can configure via standard `logging.basicConfig()`

**Validation:**
- Implementation: Centralized validators in `src/blend_ai/validators.py`
- Checks: Object names (length, charset), file paths (extension, existence, no traversal), numeric ranges, color values, vectors, enum allowlists
- Applied: Every tool validates inputs before sending commands

**Authentication:**
- Implementation: Localhost-only (127.0.0.1:9876) — no explicit auth needed
- Rationale: Blender addon only listens on loopback; no network exposure

**Thread Safety:**
- Render state: `threading.Event` in `render_guard`
- Command execution: Queue-based deferred execution in `thread_safety`
- Socket operations: `threading.Lock` in `BlenderConnection`

**Security (Input):**
- Object name allowlist: Alphanumeric, underscore, hyphen, space, dot only (prevents injection)
- File path validation: Absolute paths, no null bytes, extension allowlists
- Numeric limits: Capped at MAX_RENDER_RESOLUTION (8192), MAX_RENDER_SAMPLES (10000), etc.
- Enum validation: Only preset values allowed (e.g., ALLOWED_RENDER_ENGINES)

**Security (Command):**
- Command allowlist: Only registered handlers in `addon/handlers/` can be invoked
- Unknown commands rejected by dispatcher
- Shader node allowlist: Only ~65 known node types can be created

---

*Architecture analysis: 2026-03-23*
