# External Integrations

**Analysis Date:** 2026-03-23

## APIs & External Services

**Not Applicable:**
- blend-ai is a zero-telemetry, fully local application
- No external APIs are integrated
- No third-party services are called
- All communication stays on `127.0.0.1`

## Data Storage

**Databases:**
- None - blend-ai is stateless with respect to external storage
- All 3D scene data is managed by Blender directly via bpy

**File Storage:**
- Local filesystem only - File I/O tools (`src/blend_ai/tools/file_ops.py`) handle:
  - Import: FBX, OBJ, glTF, USD, STL, PLY, ABC, DAE, SVG, X3D
  - Export: Same formats
  - File validation: Path traversal prevention, extension allowlists
  - Security: `use_scripts_auto_execute` disabled during imports

**Caching:**
- None - No external caching layer used

## Authentication & Identity

**Auth Provider:**
- None - No external authentication
- Localhost binding only (`127.0.0.1:9876`)
- Single connection per Blender instance

**Security Model:**
- Network isolation: TCP socket binds to loopback interface only
- Input validation: All parameters validated before Blender execution
- Command allowlist: Only registered commands accepted
- Shader node allowlist: ~65 known shader node types only
- File extension allowlists: Import/export restricted to safe formats

## Monitoring & Observability

**Error Tracking:**
- None - No external error reporting
- Errors logged locally via Python `logging` module
- Test coverage: 882 unit tests (no external observability)

**Logs:**
- Local Python logging only
- No remote log aggregation

## CI/CD & Deployment

**Hosting:**
- None - blend-ai is self-hosted
- Runs on user's local machine inside Blender
- Deployable via `uv pip install -e .`

**CI Pipeline:**
- GitHub Actions workflows (`.github/` directory)
- Pylint workflow: `a2c5eeb Add Pylint workflow for Python code analysis`
- Build scripts: `build.sh` (macOS/Linux), `build.ps1` (Windows)
- Release distribution: Packaged as `.zip` addon for Blender

## Environment Configuration

**Required env vars:**
- None - blend-ai is configuration-free
- No environment variables required for operation
- Hardcoded defaults: host=`127.0.0.1`, port=`9876`

**Secrets location:**
- Not applicable - No secrets stored or managed

## Webhooks & Callbacks

**Incoming:**
- None - MCP server is request/response only
- No webhook support

**Outgoing:**
- None - No external callbacks
- Blender's render handlers tracked locally (render_guard.py) for internal state management

## Communication Protocol

**MCP Server to Blender Addon:**
- Transport: TCP socket on `127.0.0.1:9876`
- Protocol: Length-prefixed JSON (4-byte big-endian length header + UTF-8 JSON payload)
- Implementation: `src/blend_ai/connection.py` (client), `addon/server.py` (server)

**AI Assistant to MCP Server:**
- Transport: Standard MCP protocol (stdio)
- Format: JSON-RPC over stdin/stdout
- Client: Claude, Claude Code, or any MCP-compatible client

## Render State Management

**Render Guard** (`addon/render_guard.py`):
- Tracks Blender render state via `bpy.app.handlers`
- Returns "busy" status during active renders
- Prevents command timeouts during long renders
- Auto-retry with backoff in MCP client

**Handlers:**
- `bpy.app.handlers.render_pre` - Track render start
- `bpy.app.handlers.render_complete` - Track render completion
- `bpy.app.handlers.render_cancel` - Track render cancellation

## Security & Validation

**Input Validation** (`src/blend_ai/validators.py`):
- Object name sanitization: alphanumeric + `_` `-` `.` space only
- File path validation: No path traversal (`../`), null bytes checked
- Extension allowlists: 14 safe formats only (FBX, OBJ, glTF, USD, STL, PLY, ABC, DAE, SVG, X3D)
- Numeric ranges: Max subdivision level 6, max render resolution 8192px, max samples 10000
- Name length limits: Max 63 chars (Blender's limit)
- Vector validation: Bounds checking for 3D coordinates

**Command Allowlist:**
- `addon/dispatcher.py` - Only explicitly registered commands accepted
- Unknown commands rejected with error

**Shader Node Safety:**
- `src/blend_ai/tools/materials.py` - Restricted to ~65 known node types
- Prevents arbitrary shader node type injection

---

*Integration audit: 2026-03-23*
