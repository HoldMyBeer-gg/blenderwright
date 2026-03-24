# Codebase Structure

**Analysis Date:** 2026-03-23

## Directory Layout

```
blend-ai/
├── src/blend_ai/                     # MCP server (161 tools, 24 modules)
│   ├── __init__.py                   # Module init, version, server init
│   ├── server.py                     # FastMCP entry point, tool/resource registration
│   ├── connection.py                 # TCP socket client, render-aware retry logic
│   ├── validators.py                 # Input validation (names, paths, ranges, etc.)
│   ├── tools/                        # 24 tool modules (161 total tools)
│   │   ├── __init__.py               # Module marker
│   │   ├── scene.py                  # Scene management (5 tools)
│   │   ├── objects.py                # Object creation/manipulation (14 tools)
│   │   ├── transforms.py             # Position/rotation/scale (6 tools)
│   │   ├── modeling.py               # Modifiers, booleans, subdivision (13 tools)
│   │   ├── mesh_editing.py           # Inset, fill, seams, dissolve, etc. (16 tools)
│   │   ├── materials.py              # BSDF, textures, shader nodes (15 tools)
│   │   ├── lighting.py               # Lights, HDRI, shadow setup (7 tools)
│   │   ├── camera.py                 # Create, aim, DOF, viewport capture (6 tools)
│   │   ├── animation.py              # Keyframes, interpolation, paths (8 tools)
│   │   ├── rendering.py              # Engine, resolution, samples, output (6 tools)
│   │   ├── curves.py                 # Bezier, NURBS, 3D text, convert (10 tools)
│   │   ├── sculpting.py              # Brushes, remesh, symmetry (8 tools)
│   │   ├── uv.py                     # Smart project, unwrap, pack (4 tools)
│   │   ├── physics.py                # Rigid body, cloth, particles (9 tools)
│   │   ├── geometry_nodes.py         # Node tree creation, connections (5 tools)
│   │   ├── armature.py               # Bones, constraints, auto-weight (6 tools)
│   │   ├── collections.py            # Create, move, visibility, delete (4 tools)
│   │   ├── file_ops.py               # Import/export (FBX, OBJ, glTF, etc.) (5 tools)
│   │   ├── viewport.py               # Shading mode, overlays, focus (3 tools)
│   │   ├── code_exec.py              # Execute Python code in Blender (1 tool)
│   │   ├── booltool.py               # Bool Tool addon integration (4 tools)
│   │   ├── gpencil.py                # Grease Pencil objects/layers (5 tools)
│   │   └── screenshot.py             # Viewport screenshot (1 tool)
│   ├── resources/                    # MCP resources (scene context)
│   │   ├── __init__.py               # Module marker
│   │   └── scene_info.py             # Scene objects/materials as browsable context
│   └── prompts/                      # MCP prompt templates
│       ├── __init__.py               # Module marker
│       └── workflows.py              # Pre-built prompts for common tasks
│
├── addon/                            # Blender addon (TCP server, handlers)
│   ├── __init__.py                   # bl_info, register/unregister, handlers init
│   ├── server.py                     # TCP socket server, client management
│   ├── dispatcher.py                 # Command routing, allowlist enforcement
│   ├── thread_safety.py              # Queue-based main-thread execution
│   ├── render_guard.py               # Render state tracking (threading.Event)
│   ├── ui_panel.py                   # N-panel UI (Start/Stop buttons)
│   └── handlers/                     # 24 handler modules (mirrors tools/)
│       ├── __init__.py               # Handler module registration
│       ├── scene.py                  # Handle scene commands
│       ├── objects.py                # Handle object commands
│       ├── transforms.py             # Handle transform commands
│       ├── modeling.py               # Handle modeling commands
│       ├── mesh_editing.py           # Handle mesh editing commands
│       ├── materials.py              # Handle material commands
│       ├── lighting.py               # Handle lighting commands
│       ├── camera.py                 # Handle camera commands
│       ├── animation.py              # Handle animation commands
│       ├── rendering.py              # Handle rendering commands
│       ├── curves.py                 # Handle curve commands
│       ├── sculpting.py              # Handle sculpting commands
│       ├── uv.py                     # Handle UV commands
│       ├── physics.py                # Handle physics commands
│       ├── geometry_nodes.py         # Handle geometry node commands
│       ├── armature.py               # Handle armature commands
│       ├── collections.py            # Handle collection commands
│       ├── file_ops.py               # Handle file I/O commands
│       ├── viewport.py               # Handle viewport commands
│       ├── code_exec.py              # Handle code execution
│       ├── booltool.py               # Handle Bool Tool commands
│       └── gpencil.py                # Handle grease pencil commands
│
├── tests/                            # Unit tests (882 total)
│   ├── __init__.py                   # Test package marker
│   ├── conftest.py                   # Pytest fixtures
│   ├── test_connection.py            # BlenderConnection tests
│   ├── test_validators.py            # Input validation tests
│   ├── test_tools/                   # Tool implementation tests
│   │   ├── __init__.py               # Marker
│   │   ├── conftest.py               # Tool test fixtures
│   │   ├── test_scene.py             # Scene tool tests
│   │   ├── test_objects.py           # Object tool tests
│   │   ├── test_transforms.py        # Transform tool tests
│   │   ├── test_modeling.py          # Modeling tool tests
│   │   ├── test_mesh_editing.py      # Mesh editing tool tests
│   │   ├── test_materials.py         # Material tool tests
│   │   ├── test_lighting.py          # Lighting tool tests
│   │   ├── test_camera.py            # Camera tool tests
│   │   ├── test_animation.py         # Animation tool tests
│   │   ├── test_rendering.py         # Rendering tool tests
│   │   ├── test_curves.py            # Curve tool tests
│   │   ├── test_sculpting.py         # Sculpting tool tests
│   │   ├── test_uv.py                # UV tool tests
│   │   ├── test_physics.py           # Physics tool tests
│   │   ├── test_geometry_nodes.py    # Geometry node tool tests
│   │   ├── test_armature.py          # Armature tool tests
│   │   ├── test_collections.py       # Collection tool tests
│   │   ├── test_file_ops.py          # File I/O tool tests
│   │   ├── test_viewport.py          # Viewport tool tests
│   │   ├── test_code_exec.py         # Code execution tool tests
│   │   ├── test_booltool.py          # Bool Tool tool tests
│   │   ├── test_gpencil.py           # Grease pencil tool tests
│   │   └── test_screenshot.py        # Screenshot tool tests
│   └── test_addon/                   # Addon (handler) tests
│       ├── __init__.py               # Marker
│       └── test_handlers/            # Handler implementation tests
│           ├── test_scene.py         # Scene handler tests
│           └── [other handler tests]
│
├── .planning/                        # GSD documentation (generated)
│   └── codebase/                     # Architecture/structure docs
│
├── .github/                          # GitHub workflows
│   └── workflows/                    # CI/CD (pylint, etc.)
│
├── scripts/                          # Build and utility scripts
│
├── pyproject.toml                    # Project metadata, dependencies, tool config
├── README.md                         # Main documentation
├── CLAUDE.md                         # Project constraints (Blender API, TDD, security)
├── mcp.json                          # MCP server config for Claude Desktop
├── build.sh                          # Unix build script for addon .zip
└── build.ps1                         # Windows build script for addon .zip
```

## Directory Purposes

**src/blend_ai/:**
- Purpose: MCP server implementation — exposes all Blender operations as tools and resources
- Contains: Tool definitions, connection management, input validators, resource/prompt templates
- Key files: `server.py` (entry point), `connection.py` (TCP client), `validators.py` (input checks)

**addon/:**
- Purpose: Blender addon — runs TCP server inside Blender and implements all operations
- Contains: TCP server, command dispatcher, handlers for each tool, UI panel, thread safety bridge
- Key files: `server.py` (TCP server), `dispatcher.py` (command routing), `handlers/` (operation implementations)

**addon/handlers/:**
- Purpose: Implement actual Blender operations using `bpy` API
- Contains: Handler functions that manipulate Blender state (execute on main thread)
- Key files: 24 handler modules (one per tool module), each with `register()` and `unregister()` to register handlers with dispatcher

**tests/:**
- Purpose: Unit test coverage (882 tests across all modules)
- Contains: Mocks for connection/context, parametrized tests for validators, tool/handler tests
- Key files: `conftest.py` (shared fixtures), `test_validators.py` (input validation coverage)

## Key File Locations

**Entry Points:**

- `src/blend_ai/server.py` — MCP server main entry point (`main()` function)
- `addon/__init__.py` — Blender addon registration (`register()` / `unregister()`)
- `addon/ui_panel.py` — N-panel UI (Start/Stop server buttons)

**Configuration:**

- `pyproject.toml` — Python project metadata, dependency specs, pytest/ruff config
- `mcp.json` — MCP server config (command, args, transport type)
- `.python-version` — Required Python version (3.13)

**Core Logic:**

- `src/blend_ai/connection.py` — TCP socket communication, render-aware retry
- `addon/server.py` — TCP server accept loop, client handling
- `addon/dispatcher.py` — Command routing, handler lookup
- `addon/thread_safety.py` — Queue-based main-thread execution
- `addon/render_guard.py` — Render state tracking

**Validation & Security:**

- `src/blend_ai/validators.py` — Input validation functions (names, paths, ranges, enums, etc.)

**Tool Implementations (src/blend_ai/tools/):**

- 24 tool modules, each defining MCP tools and calling `get_connection().send_command()`
- Example: `src/blend_ai/tools/scene.py` — Scene management tools (get_scene_info, set_scene_property, etc.)

**Handler Implementations (addon/handlers/):**

- 24 handler modules, each implementing operations via `bpy`
- Example: `addon/handlers/scene.py` — Scene handlers (handle_get_scene_info, handle_set_scene_property, etc.)
- Each handler registers itself with `dispatcher.register_handler(command_name, handler_func)`

**Testing:**

- `tests/test_validators.py` — Input validation test coverage
- `tests/test_connection.py` — TCP connection and retry logic tests
- `tests/test_tools/` — Tool implementation tests (mocked connection)
- `tests/test_addon/test_handlers/` — Handler tests (mocked Blender context)

## Naming Conventions

**Files:**

- Python modules: `snake_case.py` (e.g., `thread_safety.py`, `render_guard.py`)
- Tool/handler pairs: Same name in `src/blend_ai/tools/X.py` and `addon/handlers/X.py`
- Test files: `test_*.py` or `*_test.py` (e.g., `test_scene.py`, `test_validators.py`)

**Directories:**

- Package directories: `snake_case` (e.g., `blend_ai`, `test_tools`)
- Grouped functionality: `handlers/`, `tools/`, `resources/`, `prompts/`

**Functions:**

- Tool functions: `verb_noun` (e.g., `get_scene_info`, `set_scene_property`, `create_object`)
- Handler functions: `handle_verb_noun` (e.g., `handle_get_scene_info`, `handle_set_scene_property`)
- Validators: `validate_noun` (e.g., `validate_object_name`, `validate_file_path`)
- Private functions: `_prefix_verb_noun` (e.g., `_send_raw`, `_recv_exactly`)

**Classes:**

- Public classes: `PascalCase` (e.g., `BlenderConnection`, `BlenderServer`, `RenderGuard`)
- Blender UI classes: `UPPERCASE_PT_suffix` or `UPPERCASE_OT_suffix` per Blender conventions
  - Example: `BLENDAI_PT_MainPanel`, `BLENDAI_OT_StartServer`

**Variables:**

- Module-level: `lowercase_with_underscore` or CONSTANT_CASE
- Class/function-level: `lowercase_with_underscore`
- Private/internal: `_leading_underscore`

## Where to Add New Code

**New Tool (step-by-step):**

1. Create tool definition in `src/blend_ai/tools/DOMAIN.py`
   - Use `@mcp.tool()` decorator
   - Call validators on inputs
   - Call `get_connection().send_command(command_name, params)`
   - Raise `RuntimeError` if response is error
   - Return result

2. Create handler in `addon/handlers/DOMAIN.py`
   - Write `handle_COMMAND_NAME(params: dict) -> dict` function
   - Use `bpy` API to implement operation
   - Call `dispatcher.register_handler(command_name, handle_COMMAND_NAME)` in module-level `register()` function

3. Add tests
   - Tool test: `tests/test_tools/test_DOMAIN.py` (mock connection)
   - Handler test: `tests/test_addon/test_handlers/test_DOMAIN.py` (mock bpy context)

4. Import in respective `__init__.py` files
   - Add to `src/blend_ai/server.py` (if new module)
   - Add to `addon/handlers/__init__.py` (if new module)

**New Validation:**

- Add function to `src/blend_ai/validators.py`
- Call from tool implementations before sending command
- Example: `validate_enum(value, ALLOWED_VALUES, name="param_name")`

**New Error Class:**

- If needed, define in respective module (e.g., `BlenderConnectionError` in `connection.py`)
- Inherit from `Exception`
- Document in docstring

## Special Directories

**src/blend_ai/__pycache__/:**
- Purpose: Python bytecode cache
- Generated: Yes
- Committed: No (in .gitignore)

**addon/__pycache__/:**
- Purpose: Python bytecode cache for addon
- Generated: Yes
- Committed: No (in .gitignore)

**tests/__pycache__/:**
- Purpose: Pytest bytecode cache
- Generated: Yes
- Committed: No (in .gitignore)

**.planning/codebase/:**
- Purpose: GSD codebase analysis and architecture documents
- Generated: Yes (by GSD mapping tools)
- Committed: Yes (part of project documentation)

**.pytest_cache/:**
- Purpose: Pytest internal cache
- Generated: Yes
- Committed: No (in .gitignore)

**test_project/:**
- Purpose: Sample Blender project for manual testing
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-03-23*
