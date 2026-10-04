# blenderwright

<small>Formerly blend-ai. Same project, new name, nothing else changed.</small>

The most intuitive and efficient MCP Server for Blender. Control Blender entirely through AI assistants like Claude: create 3D models, set up scenes, animate, render, and more, all through natural language.

**blenderwright goes beyond tool exposure: it guides the LLM to produce professional 3D results** through expert prompts, proven workflows, visual feedback, and mesh quality analysis.

<small>A shuttle launch from two questions: "do you want to have a go at the space shuttle launch?" and then "could you animate the launch?" Claude Code (Fable 5.1) modelled the orbiter, tank, boosters and service tower, lit the plumes as emissive volumes and grew the exhaust cloud from metaballs. Keyframes lift the stack and tilt the camera after it, drivers stream the plumes and boil the smoke, and all 60 Cycles frames come back from a single `render_animation` call, all through blenderwright with no manual modelling:</small>

![blenderwright space shuttle launch, animated](https://raw.githubusercontent.com/HoldMyBeer-gg/blenderwright/main/shuttle-launch.gif)

<small>[Watch it with sound](https://blenderwright.holdmybeer.gg/shuttle-launch.mp4). Launch audio courtesy of NASA: STS-131, "Sound of Launch."</small>

<small>The still it grew from, modelled and rendered in under twenty minutes:</small>

![blenderwright space shuttle launch built from one prompt](https://raw.githubusercontent.com/HoldMyBeer-gg/blenderwright/main/shuttle-launch.png)

<small>A two-storey Western saloon from a single sentence: "create a Western style 2-story saloon, the outside is more important than any inside detail." Claude Code (Fable 5.1) built the false front, plank siding, balcony, batwing doors and street dressing, then relit it for dusk, all through blenderwright, in about twenty minutes with no manual modelling:</small>

![blenderwright saloon built from one prompt](https://raw.githubusercontent.com/HoldMyBeer-gg/blenderwright/main/saloon.png)

<small>Fifteen procedural materials, each built by a single `create_procedural_material` call. The selected ball's node graph below was generated entirely by that one call: coordinates, mapping, noise, height mask, colour ramp, and Principled BSDF, laid out and wired:</small>

![blenderwright procedural shader preview](https://raw.githubusercontent.com/HoldMyBeer-gg/blenderwright/main/shader-preview.png)

## Key Features

- **[191 tools](https://blenderwright.holdmybeer.gg/)** across 28 modules covering every major Blender domain: modeling, mesh editing, materials, shader nodes, lighting, camera, animation, rendering, sculpting, UV mapping, physics, geometry nodes, rigging, curves, sweeps along a path, 3D-print checking, annotations, collections, file I/O, Bool Tool, viewport control, mesh quality analysis, and extension suggestions
- **12 expert prompts**: topology best practices, real-world scale references, lighting principles, studio setup, character basemesh workflow, PBR material guide, auto-critique feedback loop, and more
- **Visual feedback loop**: fast viewport screenshots via OpenGL render (~ms, not seconds) with auto-critique prompts that guide the LLM to check its own work
- **Mesh quality analysis**: structured reports covering non-manifold edges, loose vertices, zero-area faces, duplicate vertices, and wire edges
- **Extension suggestions**: proactively recommends Bool Tool, LoopTools, and Node Wrangler when a task would benefit from them (skips already-installed extensions)
- **Sandboxed code execution**: `execute_blender_code` blocks dangerous imports (`os`, `subprocess`, `socket`, etc.) and dangerous builtins (`exec`, `eval`, `open`) while allowing safe Blender operations
- **Render-aware**: automatically detects when Blender is rendering and queues commands. Recovers from stuck render guards via `load_post` handler and reset command
- **Blender 4.2+ compatible**: ships as a Blender Extension; tested against Blender 5.1 with EEVEE identifier, Annotation API, sculpt stroke_method, SLIM UV unwrap, Raycast shader node, and EEVEE light path intensity controls
- **Custom port**: configure the server port from the N-panel UI (default: 9876, range: 1024–65535)
- **Zero telemetry**: no usage tracking, no analytics, no data collection. Everything runs locally on `127.0.0.1`
- **Zero-dependency addon**: the Blender addon uses only Python stdlib + `bpy`. Nothing to pip install inside Blender
- **Thread-safe architecture**: background TCP server with queue-based main-thread execution, TCP keepalive for stale connection detection
- **1190 tests**: coverage across tools, handlers, validators, prompts, and the cross-platform installer (ubuntu/macos/windows × py3.11/3.13 in CI)

## Quickstart

### 1. Install the MCP server

Nothing to install. With [uv](https://docs.astral.sh/uv/) on your machine, `uvx blenderwright` fetches the server from PyPI and runs it; every client config below uses that one command. Prefer pip? `pip install blenderwright` gives you a `blenderwright` command instead.

<details>
<summary><strong>Working on blenderwright itself</strong></summary>

```bash
git clone https://github.com/HoldMyBeer-gg/blenderwright.git
cd blenderwright
uv pip install -e .
```

Then point your client at `uv run --directory /path/to/blenderwright blenderwright` instead of `uvx blenderwright`.

</details>

### 2. Install the Blender addon

1. Download the latest addon zip from [GitHub Releases](https://github.com/HoldMyBeer-gg/blenderwright/releases)
2. Open Blender 4.2 or later
3. Go to **Edit > Preferences > Get Extensions**, click the dropdown (▾) top-right, and choose **Install from Disk...**
4. Select the downloaded `.zip` file
5. Enable **"blenderwright"** in the extensions list

> **Blender 4.0 / 4.1 users:** Not supported. blenderwright ships as a Blender Extension, which requires Blender 4.2 (LTS) or later. Please upgrade Blender from [blender.org/download](https://www.blender.org/download/).

<details>
<summary><strong>Developer install (symlink)</strong></summary>

If you're developing on blenderwright, symlink the addon folder into Blender's user extensions directory instead. Replace `<ver>` with your Blender version (e.g. `4.2`, `5.1`).

```bash
# macOS
ln -s "$(pwd)/addon" ~/Library/Application\ Support/Blender/<ver>/extensions/user_default/blenderwright

# Linux
ln -s "$(pwd)/addon" ~/.config/blender/<ver>/extensions/user_default/blenderwright

# Windows (run as admin)
mklink /D "%APPDATA%\Blender Foundation\Blender\<ver>\extensions\user_default\blenderwright" "%cd%\addon"
```

Then enable the extension in Blender preferences under **Get Extensions > User**.

</details>

### 3. Start the server in Blender

In Blender's 3D Viewport, open the **N-panel** (press `N`), find the **blenderwright** tab. Set your preferred port (default: 9876), then click **Start Server**.

### 4. Connect your AI assistant

<details>
<summary><strong>Claude Code</strong></summary>

```bash
claude mcp add blenderwright -- uvx blenderwright
```

Make sure Blender is running with the addon server started before using the tools.

**Usage:**

```
$ claude

> Create a red metallic sphere on a white plane with three-point lighting

> Add a subdivision surface modifier to the sphere and set it to level 3

> Analyze the mesh quality of the sphere and fix any issues

> Set up a turntable animation and render it to /tmp/turntable/
```

</details>

<details>
<summary><strong>Claude Desktop</strong></summary>

Add blenderwright to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "blenderwright": {
      "command": "uvx",
      "args": ["blenderwright"]
    }
  }
}
```

Restart Claude Desktop. The Blender tools will appear in the tool list.

</details>

<details>
<summary><strong>Other MCP Clients</strong></summary>

blenderwright is a standard MCP server using stdio transport. Any MCP-compatible client can connect by running the server directly:

```bash
uvx blenderwright
# or, after pip install blenderwright: blenderwright
```

The exact config location and format vary by client (typically JSON or TOML under `~/.<client>/`). The `command` is `uvx` and the `args` are `["blenderwright"]`.

The server communicates over stdin/stdout using the MCP protocol. It connects to Blender's addon over TCP on `127.0.0.1:9876` (or your configured port).

</details>

## Updating

Whichever way you installed, **Blender must be fully restarted**, not "Reload Scripts".
The addon runs a background TCP server thread that survives a script reload, so reloading
leaves a stale handler registered and the old socket still bound.

### One command (zip installs)

```bash
python install_addon.py upgrade
```

With no argument it finds your Blender installations and offers them as a numbered
list, so there is no path to get wrong. You can still pass one explicitly:

```bash
# macOS - the binary inside the bundle, not the .app itself
python install_addon.py upgrade /Applications/Blender.app/Contents/MacOS/Blender

# Linux
python install_addon.py upgrade /usr/local/bin/blender

# Windows
python install_addon.py upgrade "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
```

It refuses to run while Blender is open, checks the path before touching anything,
removes every blenderwright install across *all* Blender version directories, rebuilds the
zip from `addon/`, and installs it through Blender's own extension machinery. It also
handles the case that bites people most: an older copy left behind under a previous
Blender version.

Two companion commands:

```bash
python install_addon.py doctor          # list every blenderwright install found, and where
python install_addon.py uninstall --yes # remove them all (omit --yes for a dry run)
```

Start with `doctor` if the addon is behaving strangely: a duplicate install under an
old Blender version is the usual cause.

### Developer symlink installs

If you symlinked `addon/` into Blender's extensions directory, there is nothing to
install. `git pull` and restart Blender. Use `doctor` to confirm which kind of install
you have; it reports symlinks distinctly.

### By hand, through the GUI

<details>
<summary><strong>Manual steps, if you would rather not run the script</strong></summary>

1. If the server is running, open the N-panel **blenderwright** tab and click **Stop Server**.
2. In Blender, open **Edit > Preferences > Get Extensions**, find **blenderwright**, and click **Uninstall**.
3. Quit and restart Blender (this clears cached `blenderwright` modules).
4. Install the new `.zip` via the **▾ > Install from Disk...** menu and enable it.

</details>

## Expert Guidance

blenderwright includes 12 MCP prompts that guide the LLM toward professional-quality results:

| Prompt | What It Teaches |
|--------|----------------|
| `blender_best_practices` | Bool Tool preference, mesh editing patterns, modifier workflow |
| `topology_best_practices` | Quad topology, edge flow, poles, n-gon cleanup, face density |
| `scale_reference_guide` | Real-world dimensions for 8 common objects, unit system setup |
| `lighting_principles` | Three-point lighting, HDRI, EEVEE vs Cycles, color temperature |
| `studio_lighting_setup` | 6-step studio lighting workflow with specific energy values |
| `character_basemesh_workflow` | 7-step character base mesh from cube with mirror + subdivision |
| `material_workflow_guide` | PBR materials, Principled BSDF recipes, texture color spaces |
| `auto_critique_workflow` | Visual feedback loop: when to screenshot, what to check, token budget |
| `product_shot_setup` | Professional product shot setup guide |
| `character_base_mesh` | Character modeling guide |
| `scene_cleanup` | Scene organization workflow |
| `animation_turntable` | Turntable animation setup |

## Tool Domains

<details>
<summary><strong>All 191 tools across 28 modules</strong></summary>

Full reference with every parameter: **[blenderwright.holdmybeer.gg](https://blenderwright.holdmybeer.gg/)**

| Domain | Tools | Highlights |
|--------|-------|-----------|
| Scene | 6 | Get scene info, set frame range, manage scenes, suggest helpful extensions |
| Objects | 15 | Create primitives, duplicate, parent, join, visibility, origin, convert, auto-smooth |
| Transforms | 6 | Position, rotation (euler/quat), scale, apply, snap |
| Modeling | 13 | Modifiers, booleans, subdivide, extrude, bevel, loop cut, bridge edge loops |
| Mesh Editing | 16 | Inset, fill, grid fill, mark seam/sharp, normals, dissolve, knife project, spin, crease |
| Selection | 6 | Select by index, by axis, by face sides, by similarity; invert; report what is selected |
| Mesh Quality | 3 | Analyze mesh defects: non-manifold, loose verts, zero-area faces, duplicates and repair them; decimate to reduce polycount |
| Bool Tool | 4 | Auto union, difference, intersect, slice (via Blender's Bool Tool addon) |
| Materials | 25 | Principled BSDF, procedural and raster textures, textures, blend modes, shader node graph (add/connect/remove nodes, including 5.1 Raycast node) |
| Lighting | 7 | Point/sun/spot/area lights, HDRIs, light rigs, shadows |
| Camera | 6 | Create, aim, DOF, viewport capture, active camera |
| Animation | 8 | Keyframes, interpolation, frame range, follow path |
| Rendering | 7 | Engine, resolution, samples, output format, render, EEVEE light path intensity |
| Curves | 10 | Bezier/NURBS/path, 3D text, convert, reverse, handle types, cyclic, subdivide |
| Sweep | 2 | Sweep a profile along a 3D path for tubes, hoses, cables and rails, with flip-free framing; check a path for bends too tight for the profile |
| 3D Printing | 1 | Reversed normals, self-intersection, thin walls, shells and overhangs via Blender's 3D Print Toolbox |
| Sequencer | 5 | Image-sequence strips, sound strips, list and remove strips, render to MP4, MKV or WebM with audio |
| Sculpting | 8 | Brushes, remesh, multires, symmetry, dynamic topology, stroke_method |
| UV Mapping | 4 | Smart project, unwrap (ANGLE_BASED, CONFORMAL, SLIM), projection, pack islands |
| Physics | 9 | Rigid body, cloth, fluid, particles (velocity, rendering, delete), bake |
| Geometry Nodes | 5 | Create node trees, add/connect nodes, set inputs |
| Armature | 6 | Bones, constraints, auto weights, pose |
| Annotations | 5 | Annotation layers and strokes (5.1 Annotation API) |
| Collections | 4 | Create, move objects, visibility, delete |
| File I/O | 5 | Import/export (FBX, OBJ, glTF, USD, STL...), save/open |
| Viewport | 3 | Shading mode, overlays, focus on object |
| Screenshot | 1 | Fast viewport capture (OpenGL) or full render, base64 output |
| Code Exec | 1 | Sandboxed Python execution in Blender (dangerous imports blocked) |

</details>

### Toolsets

Every tool is loaded by default, and that is the setting the featured renders were made with. The full set of schemas costs roughly 48k tokens per request, which is fine for Claude-class clients and too much for a local model on a 32k window. `BLENDERWRIGHT_TOOLSETS` (or `--toolsets`) trims it:

| Value | Loads |
|-------|-------|
| unset or `all` | everything (default) |
| `auto` | the core toolsets plus `list_toolsets` and `enable_toolset`; the model loads other groups as a task needs them |
| `core` | scene, objects, transforms, modeling, mesh quality, lighting, camera, rendering, screenshot, viewport, collections |
| `core,physics,animation` | any comma-separated list of toolset names; a toolset is one row of the table above |

```json
{
  "mcpServers": {
    "blenderwright": {
      "command": "uvx",
      "args": ["blenderwright"],
      "env": { "BLENDERWRIGHT_TOOLSETS": "auto" }
    }
  }
}
```

`auto` relies on the client honouring the MCP `tools/list_changed` notification. The bundled Ollama chat client picks `auto` on its own when the full set would take more than half of `--num-ctx`, and says so at startup.

## Architecture

```
AI Assistant <--stdio/MCP--> blenderwright server <--TCP socket--> Blender addon <--bpy--> Blender
```

<details>
<summary><strong>How it works</strong></summary>

- **MCP Server** (`src/blenderwright/`): Python process using the `mcp` SDK. Exposes tools, resources, and prompts over stdio. Validates all inputs before forwarding to Blender.
- **Blender Addon** (`addon/`): Runs a TCP socket server inside Blender on a background thread. Commands are queued and executed on the main thread via `bpy.app.timers` to respect Blender's threading model.
- **Render Guard**: Tracks render state via `bpy.app.handlers`. During renders, the server immediately returns a "busy" status. Automatically recovers from crashed renders via `load_post` handler. Can be force-reset via MCP command.
- **Protocol**: Length-prefixed JSON messages over TCP with SO_KEEPALIVE for stale connection detection. Each message is a 4-byte big-endian length header followed by a UTF-8 JSON payload.

</details>

## Privacy & Security

<details>
<summary><strong>Privacy</strong></summary>

- **Zero telemetry**: blenderwright collects no usage data, sends no analytics, and makes no network requests beyond the local TCP connection to Blender.
- **Fully local**: all communication stays on your machine. No cloud services, no external APIs, no phone-home behavior.
- **Open source**: the entire codebase is auditable. What you see is what runs.

</details>

<details>
<summary><strong>Security</strong></summary>

- **Localhost only**: The TCP socket binds to `127.0.0.1`, never exposed to the network.
- **Sandboxed code execution**: `execute_blender_code` blocks 25 dangerous imports (`os`, `subprocess`, `socket`, `shutil`, `sys`, `ctypes`, `importlib`, `pathlib`, `signal`, `multiprocessing`, `pickle`, `shelve`, `tempfile`, `http`, `urllib`, `ftplib`, `smtplib`, `xmlrpc`, `code`, `codeop`, `compileall`, `webbrowser`, `antigravity`, `turtle`, `tkinter`) and removes dangerous builtins (`__import__`, `exec`, `eval`, `compile`, `open`, `globals`, `locals`, `vars`, `input`, `breakpoint`, `exit`, `quit`, `help`, `memoryview`). Safe Blender imports (`bpy`, `bmesh`, `mathutils`, `math`, `json`) are allowed.
- **Input validation**: All inputs pass through validators before reaching Blender: name sanitization, path traversal prevention, numeric range checks, enum allowlists.
- **File safety**: Import operations disable `use_scripts_auto_execute` to prevent script injection from imported files. File extensions are checked against allowlists.
- **Command allowlist**: The addon dispatcher only processes explicitly registered commands. Unknown commands are rejected.
- **Shader node allowlist**: Only 64 known shader node types can be created, which prevents arbitrary type injection.

</details>

## Limitations

<details>
<summary><strong>Known limitations</strong></summary>

- **Blender must be running**: The MCP server communicates with Blender over TCP. Blender must be open with the addon enabled and server started.
- **Single connection**: The addon accepts one client connection at a time. Multiple AI assistants cannot control the same Blender instance simultaneously.
- **Selection is persistent, not per-call**: Selection lives on the mesh in Blender, so it stays set between calls. Choose geometry with the `select_*` tools, then pass `selection="CURRENT"` to a mesh tool. The default is still `"ALL"`. Because the selection is shared state, two assistants working on the same mesh would step on each other.
- **Sculpt strokes cannot be simulated**: You can configure brushes, symmetry, dyntopo, and remeshing, but actual brush strokes are not yet exposed.
- **Node graphs require sequential calls**: Both shader node trees and geometry node trees must be built one node/connection at a time.
- **No undo integration**: Operations appear in Blender's undo history individually but there's no MCP-level undo/redo or transaction grouping.
- **Viewport capture requires a visible 3D viewport**: Headless Blender may not support viewport screenshots.
- **No real-time feedback**: The MCP protocol is request/response. There's no streaming of viewport updates or render progress.

</details>

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests (1190 tests)
uv run --extra dev pytest

# Run tests with coverage
uv run --extra dev pytest --cov=blenderwright

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

<details>
<summary><strong>Project structure</strong></summary>

```
blenderwright/
├── src/blenderwright/          # MCP server
│   ├── server.py           # FastMCP entry point
│   ├── connection.py       # TCP client to Blender (with busy-retry)
│   ├── validators.py       # Input validation
│   ├── tools/              # 28 tool modules (191 tools)
│   ├── resources/          # MCP resources (scene, objects, materials)
│   └── prompts/            # 12 expert prompt templates
├── addon/                  # Blender addon (zero external deps)
│   ├── blender_manifest.toml  # Blender 4.2+ Extension manifest
│   ├── __init__.py         # bl_info (legacy fallback) + register/unregister
│   ├── server.py           # TCP socket server (SO_KEEPALIVE)
│   ├── dispatcher.py       # Command routing + allowlist
│   ├── thread_safety.py    # Main-thread execution queue
│   ├── render_guard.py     # Render state tracking + crash recovery
│   ├── ui_panel.py         # N-panel UI (start/stop + port config)
│   └── handlers/           # 23 handler modules
└── tests/                  # 1186 unit tests
```

</details>

## License

MIT. See [LICENSE.md](https://github.com/HoldMyBeer-gg/blenderwright/blob/main/LICENSE.md).

Copyright © 2026 jabberwock.
