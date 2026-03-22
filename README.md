# blend-ai

The most intuitive and efficient MCP Server for Blender. Control Blender entirely through AI assistants like Claude — create 3D models, set up scenes, animate, render, and more, all through natural language.

## Key Features

- **108 tools** covering every major Blender domain: modeling, materials, lighting, camera, animation, rendering, sculpting, UV mapping, physics, geometry nodes, rigging, curves, collections, file I/O, and viewport control
- **No arbitrary code execution** — every operation is an explicit, validated, parameterized tool. No `exec()`, no `eval()`, no script injection vectors.
- **Zero-dependency Blender addon** — the addon uses only Python stdlib + `bpy`. Nothing to pip install inside Blender's bundled Python.
- **Thread-safe architecture** — background TCP server with queue-based main-thread execution, respecting Blender's single-threaded API constraint.
- **MCP resources** — browse scene objects, materials, and scene info as structured context.
- **Workflow prompts** — pre-built prompt templates for common tasks (product shots, character base meshes, scene cleanup, turntable animations).

## Quickstart

### 1. Install the MCP server

```bash
# Using uv (recommended)
uv pip install blend-ai

# Or from source
git clone https://github.com/your-org/blend-ai.git
cd blend-ai
uv pip install -e .
```

### 2. Install the Blender addon

1. Open Blender (5.0+)
2. Go to **Edit > Preferences > Add-ons > Install...**
3. Select the `addon/` folder from this repo (or zip it first)
4. Enable **"blend-ai"** in the addon list

Alternatively, symlink for development:

```bash
# macOS
ln -s "$(pwd)/addon" ~/Library/Application\ Support/Blender/5.0/scripts/addons/blend_ai

# Linux
ln -s "$(pwd)/addon" ~/.config/blender/5.0/scripts/addons/blend_ai

# Windows (run as admin)
mklink /D "%APPDATA%\Blender Foundation\Blender\5.0\scripts\addons\blend_ai" "%cd%\addon"
```

Then enable the addon in Blender preferences.

### 3. Start the server in Blender

In Blender's 3D Viewport, open the **N-panel** (press `N`), find the **blend-ai** tab, and click **Start Server**. The addon listens on `127.0.0.1:9876`.

### 4. Connect your AI assistant

This repo includes an [`mcp.json`](mcp.json) config file you can use directly or copy into your client's configuration.

## Claude Code Integration

```bash
claude mcp add blend-ai -- uvx blend-ai
```

That's it. Claude Code will now have access to all 108 Blender tools. Make sure Blender is running with the addon server started before using the tools.

### Usage

```
$ claude

> Create a red metallic sphere on a white plane with three-point lighting

> Add a subdivision surface modifier to the sphere and set it to level 3

> Set up a turntable animation and render it to /tmp/turntable/
```

## Claude Desktop Integration

Add blend-ai to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "blend-ai": {
      "command": "uvx",
      "args": ["blend-ai"]
    }
  }
}
```

Or copy the contents of the bundled [`mcp.json`](mcp.json) into your config file.

Restart Claude Desktop. The Blender tools will appear in the tool list.

## Other MCP Clients

blend-ai is a standard MCP server using stdio transport. Any MCP-compatible client can connect using the [`mcp.json`](mcp.json) config or by running the server directly:

```bash
uvx blend-ai
# or: python -m blend_ai.server
```

The server communicates over stdin/stdout using the MCP protocol. It connects to Blender's addon over TCP on `127.0.0.1:9876`.

## Architecture

```
AI Assistant <--stdio/MCP--> blend-ai server <--TCP socket--> Blender addon <--bpy--> Blender
```

- **MCP Server** (`src/blend_ai/`): Python process using the `mcp` SDK. Exposes tools, resources, and prompts over stdio. Validates all inputs before forwarding to Blender.
- **Blender Addon** (`addon/`): Runs a TCP socket server inside Blender on a background thread. Commands are queued and executed on the main thread via `bpy.app.timers` to respect Blender's threading model.
- **Protocol**: Length-prefixed JSON messages over TCP. Each message is a 4-byte big-endian length header followed by a UTF-8 JSON payload.

## Tool Domains

| Domain | Tools | Examples |
|--------|-------|---------|
| Scene | 5 | Get scene info, set frame range, manage scenes |
| Objects | 10 | Create primitives, duplicate, parent, join, visibility |
| Transforms | 6 | Position, rotation (euler/quat), scale, apply, snap |
| Modeling | 12 | Modifiers, booleans, subdivide, extrude, bevel, loop cut |
| Materials | 10 | Principled BSDF, textures, blend modes, color, properties |
| Lighting | 7 | Point/sun/spot/area lights, HDRIs, light rigs, shadows |
| Camera | 6 | Create, aim, DOF, viewport capture, active camera |
| Animation | 8 | Keyframes, interpolation, frame range, follow path |
| Rendering | 6 | Engine, resolution, samples, output format, render |
| Curves | 5 | Bezier/NURBS/path, 3D text, convert to mesh |
| Sculpting | 6 | Brushes, remesh, multires, mode switching |
| UV Mapping | 4 | Smart project, unwrap, projection, pack islands |
| Physics | 6 | Rigid body, cloth, fluid, particles, bake |
| Geometry Nodes | 5 | Create node trees, add/connect nodes, set inputs |
| Armature | 6 | Bones, constraints, auto weights, pose |
| Collections | 4 | Create, move objects, visibility, delete |
| File I/O | 5 | Import/export (FBX, OBJ, glTF, USD, STL...), save/open |
| Viewport | 3 | Shading mode, overlays, focus on object |

## Security

- **Localhost only**: The TCP socket binds to `127.0.0.1` — never exposed to the network.
- **No arbitrary code execution**: Every tool is a parameterized operation. There is no "run Python code" tool.
- **Input validation**: All inputs pass through validators before reaching Blender — name sanitization, path traversal prevention, numeric range checks, enum allowlists.
- **File safety**: Import operations disable `use_scripts_auto_execute` to prevent script injection from imported files. File extensions are checked against allowlists.
- **Command allowlist**: The addon dispatcher only processes explicitly registered commands. Unknown commands are rejected.

## Limitations

- **Blender must be running**: The MCP server communicates with Blender over TCP. Blender must be open with the addon enabled and server started.
- **Single connection**: The addon accepts one client connection at a time. Multiple AI assistants cannot control the same Blender instance simultaneously.
- **Edit mode operations are coarse**: Tools like extrude, bevel, and loop cut operate on all geometry (all faces/edges). Fine-grained vertex/face selection is not yet exposed.
- **No undo integration**: Operations are executed directly via `bpy`. They appear in Blender's undo history individually but there's no MCP-level undo/redo.
- **Geometry Nodes**: Creating complex node trees requires multiple sequential tool calls. There's no "create full node tree from description" tool.
- **Sculpting**: Sculpt brush strokes cannot be simulated programmatically. Sculpt tools are limited to mode switching, brush settings, and remeshing.
- **Viewport capture**: Requires a 3D viewport to be visible. Headless Blender may not support viewport screenshots.
- **No real-time feedback**: The MCP protocol is request/response. There's no streaming of viewport updates or progress bars.

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests (654 tests)
pytest

# Run tests with coverage
pytest --cov=blend_ai

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

### Project Structure

```
blend-ai/
├── src/blend_ai/          # MCP server
│   ├── server.py           # FastMCP entry point
│   ├── connection.py       # TCP client to Blender
│   ├── validators.py       # Input validation
│   ├── tools/              # 18 tool modules (~108 tools)
│   ├── resources/          # MCP resources (scene, objects, materials)
│   └── prompts/            # Workflow prompt templates
├── addon/                  # Blender addon (zero external deps)
│   ├── __init__.py         # bl_info + register/unregister
│   ├── server.py           # TCP socket server
│   ├── dispatcher.py       # Command routing + allowlist
│   ├── thread_safety.py    # Main-thread execution queue
│   ├── ui_panel.py         # N-panel UI (start/stop)
│   └── handlers/           # 18 handler modules
└── tests/                  # 654 unit tests
```

## License

MIT
