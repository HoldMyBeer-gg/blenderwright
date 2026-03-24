# Technology Stack

**Analysis Date:** 2026-03-23

## Languages

**Primary:**
- Python 3.10+ - MCP server, Blender addon, and all tools
- Blender Python API (bpy) 4.0+ - Direct Blender integration

## Runtime

**Environment:**
- Python 3.13.2 (specified in `.python-version`)
- Requires Python >= 3.10 (per `pyproject.toml`)

**Package Manager:**
- UV - Fast Python package manager
- Lockfile: `uv.lock` present (version 1, revision 3)

## Frameworks

**Core:**
- mcp 1.26.0 - Model Context Protocol server framework (FastMCP)
- pydantic 2.12.5 - Data validation and serialization

**HTTP/Networking:**
- httpx 0.28.1 - HTTP client (dependency of mcp)
- anyio 4.12.1 - Async I/O support
- starlette 0.45.2 - ASGI web framework (via mcp)

**Testing:**
- pytest 7.4.4 - Test runner (dev dependency)
- pytest-asyncio 0.21.1 - Async test support (dev dependency)
- pytest-cov 4.0.0 - Coverage measurement (dev dependency)

**Build/Dev:**
- ruff 0.1.0+ - Linting and formatting (dev dependency)

## Key Dependencies

**Critical:**
- mcp (>=1.26.0) - MCP server framework with FastMCP, stdio transport, resource/tool/prompt support
- pydantic (>=2.0) - Input validation, type checking, serialization
- bpy (embedded in Blender 4.0+) - Blender Python API, not pip-installed

**Infrastructure:**
- httpx - HTTP client for mcp
- anyio - Async I/O foundation
- jsonschema - JSON schema validation (via pydantic)
- cryptography - TLS/crypto support (via httpx)
- typing-extensions - Type annotation backports

**Development:**
- pytest - Unit test framework (882 tests across codebase)
- pytest-asyncio - Async test support
- pytest-cov - Code coverage reporting
- ruff - Code linting and formatting

## Configuration

**Environment:**
- Configured via environment variables (implicit in connection string: `127.0.0.1:9876`)
- No .env file in use (zero telemetry, fully local operation)

**Build:**
- `pyproject.toml` - Project metadata, dependencies, tool config
- Build backend: hatchling
- Entry point: `blend_ai.server:main` → `blend-ai` command

**Testing Config:**
- pytest configured in `pyproject.toml`:
  - testpaths: `["tests"]`
  - asyncio_mode: `"auto"`

**Linting Config:**
- ruff configured in `pyproject.toml`:
  - target-version: `py310`
  - line-length: 100

**Addon Config:**
- `mcp.json` - MCP server config for Claude Desktop/Code
- Specifies: `uvx blend-ai` as command or `uv run --directory [path] blend-ai`

## Platform Requirements

**Development:**
- Python 3.10+ interpreter
- UV package manager for dependency management
- Git for version control

**Production:**
- Blender 4.0+ (addon compatibility)
- Python 3.10+ (server runtime)
- Local machine with TCP socket support (127.0.0.1:9876)
- Access to Blender's bpy module (requires Blender running)

**Deployment:**
- Installable via `uv pip install -e .` (editable install)
- Addon distributed as `.zip` file (zero external dependencies inside Blender)
- Runs as background TCP server inside Blender on port 9876
- MCP server can be invoked via:
  - `blend-ai` command (after install)
  - `uv run --directory [path] blend-ai`
  - `python -m blend_ai.server`

## Architecture Highlights

- **Zero external dependencies in addon** - Addon uses only Python stdlib + bpy
- **No telemetry** - All communication local (127.0.0.1 TCP socket)
- **MCP protocol** - Stdio-based Model Context Protocol for AI assistant integration
- **Length-prefixed JSON over TCP** - Custom protocol between MCP server and Blender addon
- **Thread-safe** - Background TCP server with queue-based main-thread execution

---

*Stack analysis: 2026-03-23*
