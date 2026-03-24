# Phase 1: Blender 5.1 Compatibility - Research

**Researched:** 2026-03-23
**Domain:** Blender Python API breaking changes (5.0 and 5.1), bpy pip package, CI configuration, test coverage gaps
**Confidence:** HIGH

## Summary

Blender 5.1 introduced Python 3.13 and ships with a matching `bpy==5.1.0` pip package (released March 17, 2026, wheels for Windows x86-64/ARM64, Linux x86-64, macOS ARM64). The breaking changes that affect this codebase fall into two generations: Blender 5.0 introduced the large structural renames (EEVEE engine identifier, compositor node tree access, Grease Pencil/Annotation split, paint system), and Blender 5.1 layered on sculpt brush consolidation, VSE strip time property renames, and the `sculpt.sample_color` operator removal.

All six COMPAT requirements map to specific, localized file changes — no architectural rewrites are needed. The deepest change is COMPAT-04 (Grease Pencil/Annotation split), because `bpy.ops.object.gpencil_add` and `obj.type == "GPENCIL"` are both wrong on 5.x — the handler and its type checks require a targeted rewrite. For COMPAT-01 (EEVEE), both the MCP-side allowlist constant AND the test that explicitly asserts `BLENDER_EEVEE` is invalid must flip together. The existing test suite (882 tests, all passing on Python 3.13 today) already runs on the correct Python version, so COMPAT-06 requires audit not rewrite.

The CI success criterion (test handler suite against `bpy==5.1.0`) requires creating a new GitHub Actions workflow. The `bpy==5.1.0` package is available on PyPI and requires Python 3.13 exactly. A separate `fake-bpy-module-5.1` package does not yet exist (latest fake-bpy-module release is 20260128, supporting only up to 5.0), so handler tests must use either the real `bpy==5.1.0` pip package or a handcrafted mock that matches 5.1 API shapes. The real `bpy` pip package is the correct choice for CI — it validates actual API behavior.

**Primary recommendation:** Fix the five API break sites in a strict order (COMPAT-01 first as it has ripple effects on tests, then COMPAT-02, COMPAT-03, COMPAT-04, COMPAT-05), write/update tests to encode the 5.1-correct API, then create a CI workflow that installs `bpy==5.1.0` on Python 3.13 and runs the handler test suite.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COMPAT-01 | All tools work correctly on Blender 5.1 with the EEVEE engine identifier change (`BLENDER_EEVEE_NEXT` → `BLENDER_EEVEE`) | `ALLOWED_RENDER_ENGINES` constant in `src/blend_ai/tools/rendering.py` must change; existing test explicitly asserts old identifier is invalid — test must be inverted |
| COMPAT-02 | Compositor tools use `scene.compositing_node_group` instead of `scene.node_tree` | No compositor handler exists today; the scene info handler that returns render/compositor state may reference `scene.node_tree`; the fix is to add a version guard or use the 5.x attribute unconditionally since 5.0+ is the target |
| COMPAT-03 | Sculpting tools handle consolidated `brush.stroke_method` enum replacing 8 individual properties | Current sculpting handler does not reference the removed boolean properties directly, but the `set_brush_property` allowlist may need `stroke_method` added as a valid settable property |
| COMPAT-04 | Grease pencil tools work with Annotation API split (`bpy.data.annotations`, `AnnotationStroke`) | Handler uses `bpy.ops.object.gpencil_add` (removed on 5.x), `obj.type == "GPENCIL"` (type no longer valid on 5.x) — requires targeted rewrite using `bpy.data.annotations.new()` and `bpy.types.Annotation` |
| COMPAT-05 | VSE strip tools handle renamed time properties (`frame_final_duration` → `duration`, etc.) | No VSE-specific handler or tool exists in the codebase — this requirement is a no-op for existing code; CI test must verify this by confirming no references exist |
| COMPAT-06 | All existing tools pass on Python 3.13 without errors | Test suite already runs on Python 3.13.2 and passes 882 tests; audit needed for any Python 3.12-specific patterns; CI workflow must pin Python 3.13 |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Test-first**: Write unit tests before implementation code
- **Thread model**: Blender is single-threaded — all `bpy` calls run on main thread via queue (no impact on these fixes; thread safety already implemented)
- **Security**: No arbitrary code execution without sandboxing (no impact on compatibility fixes)
- **Blender API**: Must use official Python API (`bpy`); no private/internal API access
- **Python 3.10+**: Code targets Python 3.10+ via `pyproject.toml`
- **Line length**: 100 characters (Ruff, configured in `pyproject.toml`)
- **No AI signatures in commits**
- **GSD workflow**: Changes must go through a GSD workflow entry point (`/gsd:execute-phase`)

## Standard Stack

### Core (already in use — no new dependencies needed for compatibility fixes)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 (installed) | Test runner | Project standard; 882 existing tests |
| pytest-asyncio | 1.3.0 (installed) | Async test support | MCP framework uses anyio |
| unittest.mock | stdlib | Mock bpy and connections | Established pattern in all test files |
| bpy | 5.1.0 (pip, CI only) | Real Blender API for handler tests | Only source of truth for actual 5.1 API behavior |

### CI-Only (new, for success criterion 5)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| bpy | ==5.1.0 | Real Blender Python module in CI | Handler tests that verify 5.1 API correctness |
| GitHub Actions | ubuntu-latest | CI runner | Already used for pylint workflow |

**Installation (CI test requirements):**
```bash
pip install bpy==5.1.0  # requires Python ==3.13.*
```

**Version verification:**
```bash
# bpy 5.1.0 confirmed available March 17, 2026
# Verified at https://pypi.org/project/bpy/#history
# Requires Python ==3.13.* (no other Python version will work)
```

**Note on fake-bpy-module:** `fake-bpy-module-5.1` does not yet exist on PyPI (latest release 20260128 supports only up to 5.0). Do not use fake-bpy-module for handler tests. Use `bpy==5.1.0` in CI, and use `unittest.mock.MagicMock()` for the existing `tests/test_addon/` pattern (which already mocks the full `bpy` module).

## Architecture Patterns

### What changes and what does not

The three-tier architecture (MCP tools → TCP socket → Blender addon handlers) is unchanged. Each compatibility fix touches exactly two files per requirement: the MCP tool (in `src/blend_ai/tools/`) and the addon handler (in `addon/handlers/`), plus one test file.

### Pattern 1: Allowlist Constant Update (COMPAT-01)
**What:** Change `ALLOWED_RENDER_ENGINES` in `src/blend_ai/tools/rendering.py` to replace `BLENDER_EEVEE_NEXT` with `BLENDER_EEVEE`. Also update `src/blend_ai/tools/scene.py` where it is also defined.
**When to use:** When an API identifier is renamed — the MCP layer validates against this constant before forwarding to Blender.
**Example (after fix):**
```python
# src/blend_ai/tools/rendering.py
ALLOWED_RENDER_ENGINES = {"BLENDER_EEVEE", "CYCLES", "BLENDER_WORKBENCH"}
```
**Test change required:** `test_rendering.py::TestSetRenderEngine::test_set_eevee` currently calls `set_render_engine("BLENDER_EEVEE_NEXT")` and `test_invalid_engine` asserts `BLENDER_EEVEE` raises `ValidationError`. Both must invert.

### Pattern 2: Version-Guarded Attribute Access (COMPAT-02)
**What:** When Blender 5.0 removed `scene.node_tree` and replaced it with `scene.compositing_node_group`, any handler code accessing the compositor node tree must use the new attribute. Since this project targets 5.0+ (not 4.x compatibility), use the new attribute unconditionally.
**When to use:** Compositor-adjacent handler code.
**Example:**
```python
# Blender 5.0+ only
tree = bpy.context.scene.compositing_node_group
if tree is None:
    tree = bpy.data.node_groups.new("Compositor", "CompositorNodeTree")
    bpy.context.scene.compositing_node_group = tree
```
**Note:** No existing handler in `addon/handlers/` currently accesses `scene.node_tree` for compositor purposes. The `scene.py` tool returns compositor info but delegates to the handler. Audit confirms this is low-risk; may require adding correct access to the scene info handler if it reads compositor state.

### Pattern 3: Type Check Update (COMPAT-04)
**What:** The gpencil handler checks `obj.type == "GPENCIL"` and calls `bpy.ops.object.gpencil_add()`. In Blender 5.x, the Annotation type is separate from Grease Pencil v3. The handler's function (drawing annotations with layers/strokes) maps to the Annotation API.
**Decision required at planning time:** COMPAT-04 targets the **Annotation API** (viewport overlay notes, `bpy.data.annotations`, `bpy.types.Annotation`) not Grease Pencil v3 objects (`bpy.types.GreasePencilv3`). This matches the STATE.md blocker note: "must decide whether COMPAT-04 targets GreasePencilv3 (3D drawing objects), Annotation (viewport overlays), or both." The existing handler behavior (creating objects with layers/frames/strokes matching old GPencil semantics for annotation-style use) aligns with the Annotation API.
**Example (5.0+ annotation pattern):**
```python
# Create annotation data
ann = bpy.data.annotations.new(name)  # was: bpy.data.grease_pencils.new()

# Type check
if obj.type != "GPENCIL":  # WRONG on 5.x — "GPENCIL" type removed for annotation objects
    raise ValueError(...)
# Correct approach: check data type
if not isinstance(obj.data, bpy.types.Annotation):
    raise ValueError(...)
```

### Pattern 4: Brush stroke_method Exposure (COMPAT-03)
**What:** In Blender 5.1, the 8 individual boolean brush stroke properties (`use_airbrush`, `use_anchor`, `use_space`, `use_line`, `use_curve`, `use_restore_mesh`, `use_restore_mesh`, `use_drag_dot`) are consolidated into a single enum `brush.stroke_method`. The current `handle_set_brush_property` handler does not reference any of these booleans — it only handles `size`, `strength`, `auto_smooth_factor`, `use_frontface`. However, `stroke_method` should now be added as a settable property so 5.1 users can configure brush behavior.
**Example:**
```python
# addon/handlers/sculpting.py  — add stroke_method handling
elif prop == "stroke_method":
    ALLOWED_STROKE_METHODS = {
        "DOTS", "DRAG_DOT", "SPACE", "AIRBRUSH",
        "ANCHORED", "LINE", "CURVE",
    }
    if value not in ALLOWED_STROKE_METHODS:
        raise ValueError(f"Unknown stroke_method: {value}")
    brush.stroke_method = value
```

### Pattern 5: VSE Audit (COMPAT-05)
**What:** VSE strip time properties were renamed in Blender 5.1 (`frame_final_duration` → `duration`, etc.). Audit confirms no existing handler or tool in the codebase references any VSE strip time properties. COMPAT-05 is satisfied by the absence of code — but a test must assert this continues to be true by verifying the codebase does not contain the deprecated names.

### Anti-Patterns to Avoid
- **Mixing version guards everywhere:** Do not scatter `if bpy.app.version >= (5, 0, 0):` checks across every handler. The project targets 5.0+ — use the 5.x API unconditionally.
- **Keeping both identifiers in an allowlist:** Do not add `BLENDER_EEVEE` alongside `BLENDER_EEVEE_NEXT`. The old identifier is invalid on 5.x; having both misleads users and creates confusion.
- **Using fake-bpy-module for handler tests:** The latest fake-bpy-module (20260128) only covers up to 5.0. Handler integration tests must use `bpy==5.1.0` in CI or a carefully handcrafted mock.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Blender API introspection at test time | Custom API shape validator | `bpy==5.1.0` pip package in CI | Real package validates actual API; no maintenance cost |
| Version detection in handlers | `bpy.app.version` branching per handler | Unconditional 5.x API | Targeting only 5.0+; branching creates dead code and dual-maintenance burden |
| Custom Grease Pencil type checking | Manual `obj.type` string comparison | `isinstance(obj.data, bpy.types.Annotation)` | Robust to type renames; idiomatic bpy pattern |

## Runtime State Inventory

This phase is code-only changes to Python source files. No runtime state (databases, stored data, OS registrations, secrets) is affected by renaming API string constants.

**Nothing found in any category — verified by codebase search. All changes are source file edits only.**

## Common Pitfalls

### Pitfall 1: Inverting the EEVEE Test Without Updating Both Places
**What goes wrong:** `ALLOWED_RENDER_ENGINES` is defined in two files: `src/blend_ai/tools/rendering.py` AND `src/blend_ai/tools/scene.py`. Fixing only one leaves the other with the stale identifier. The test `test_invalid_engine` in `test_rendering.py` asserts `BLENDER_EEVEE` (the correct 5.x name) is *invalid* — this test must be changed to assert it is *valid*, and `BLENDER_EEVEE_NEXT` becomes the invalid name.
**Why it happens:** The two files define the same constant independently.
**How to avoid:** Search for all occurrences of `BLENDER_EEVEE_NEXT` before writing any code; fix all sites atomically.
**Warning signs:** `test_set_eevee` passes with old identifier; `test_invalid_engine` passes before it should fail.

### Pitfall 2: COMPAT-04 Scope — Annotation vs. Grease Pencil v3
**What goes wrong:** Blender 5.x has two separate data types: `bpy.types.Annotation` (viewport overlays, simple drawing) and `bpy.types.GreasePencilv3` (full 3D GP objects with materials, modifiers, etc.). The existing handler was built against the old unified `bpy.types.GreasePencil` which blurred this line. Migrating to the wrong type (GPv3 when annotation behavior was intended, or vice versa) will produce objects that work but don't match user expectations.
**Why it happens:** The Blender 5.x split is architecturally significant; the old API served both use cases from one type.
**How to avoid:** The handler currently creates objects for annotation-style use (layers, frames, strokes as drawing marks). Target `bpy.data.annotations` / `bpy.types.Annotation`. If full 3D GP objects are needed in future, add a separate GPv3 handler.
**Warning signs:** Handler creates objects with type `GPENCIL` that do not appear in the Viewport Overlays Annotations panel.

### Pitfall 3: bpy==5.1.0 Requires Python ==3.13 Exactly
**What goes wrong:** If the CI workflow uses a Python matrix with 3.10, 3.11, or 3.12, `pip install bpy==5.1.0` will fail with "no matching distribution found." Each bpy release is strictly tied to one Python version.
**Why it happens:** Blender embeds one specific Python; the pip package reflects that constraint.
**How to avoid:** The CI workflow for handler tests must use `python-version: "3.13"` (not a matrix). The existing pylint workflow targets `["3.8", "3.9", "3.10"]` — the new handler test workflow is separate and must NOT reuse that matrix.
**Warning signs:** CI job fails immediately at `pip install bpy==5.1.0` with a "no matching distribution" error.

### Pitfall 4: Handler Tests in test_addon/test_handlers/ Are Empty
**What goes wrong:** `tests/test_addon/test_handlers/` exists with only `__init__.py`. There are zero handler-specific tests. The current 882-test suite covers MCP tool layer only (mocked connection), NOT addon handler behavior. COMPAT-04's gpencil handler rewrite, COMPAT-01's rendering handler, and COMPAT-03's sculpting handler changes are not covered by any test.
**Why it happens:** Handler tests require `bpy` — which is not available in the standard test environment. The project punted on handler tests.
**How to avoid:** For Phase 1, write handler unit tests that use the project's existing `MagicMock` pattern for `bpy` (as in `tests/test_addon/conftest.py`) OR write them as integration tests that run only in CI with `bpy==5.1.0` installed. The mock-based approach is faster and follows project conventions. The CI workflow is the gate that validates with real `bpy==5.1.0`.
**Warning signs:** Phase completes but no handler tests exist; CI workflow has nothing to run.

### Pitfall 5: scene.use_nodes Deprecated — Do Not Set It
**What goes wrong:** In Blender 5.0, `scene.use_nodes` is deprecated and always returns `True`. Any handler code that sets `scene.use_nodes = True` before accessing compositor nodes is now a no-op — but it is not an error. The real risk is code that checks `if not scene.use_nodes:` and skips compositor setup — this will never skip on 5.x, masking bugs.
**Why it happens:** Developers migrating from 4.x carry the `scene.use_nodes = True` pattern.
**How to avoid:** Use `scene.compositing_node_group` directly without touching `scene.use_nodes`.
**Warning signs:** Handler sets `scene.use_nodes` without checking if this attribute still controls anything.

### Pitfall 6: CI Workflow Using pylint.yml Python Matrix
**What goes wrong:** The existing `pylint.yml` workflow runs against Python 3.8/3.9/3.10 — none of which support `bpy==5.1.0`. Adding the handler test step to this workflow will fail immediately.
**Why it happens:** Reusing existing workflow infrastructure feels natural.
**How to avoid:** Create a NEW workflow file `.github/workflows/test-bpy51.yml` that targets only Python 3.13 and runs ONLY the handler test suite.

## Code Examples

Verified patterns from official Blender 5.0/5.1 release notes and bpy API docs:

### COMPAT-01: EEVEE Engine Identifier Fix
```python
# Source: https://developer.blender.org/docs/release_notes/5.0/python_api/
# src/blend_ai/tools/rendering.py
ALLOWED_RENDER_ENGINES = {"BLENDER_EEVEE", "CYCLES", "BLENDER_WORKBENCH"}

# addon/handlers/rendering.py — set_render_samples handler branch
engine = bpy.context.scene.render.engine
if engine == "CYCLES":
    bpy.context.scene.cycles.samples = samples
else:
    # BLENDER_EEVEE (5.x) or BLENDER_WORKBENCH
    bpy.context.scene.eevee.taa_render_samples = samples
```

### COMPAT-02: Compositor Node Group Access
```python
# Source: https://developer.blender.org/docs/release_notes/5.0/python_api/
# addon/handlers/ — any handler needing compositor access
tree = bpy.context.scene.compositing_node_group
if tree is None:
    # Create a new compositor node tree and assign it
    tree = bpy.data.node_groups.new("Compositor", "CompositorNodeTree")
    bpy.context.scene.compositing_node_group = tree
node = tree.nodes.new(type="CompositorNodeRLayers")
```

### COMPAT-03: Brush stroke_method (5.1 consolidated enum)
```python
# Source: https://developer.blender.org/docs/release_notes/5.1/python_api/
# addon/handlers/sculpting.py
ALLOWED_STROKE_METHODS = {
    "DOTS", "DRAG_DOT", "SPACE", "AIRBRUSH",
    "ANCHORED", "LINE", "CURVE",
}
# In handle_set_brush_property:
elif prop == "stroke_method":
    if value not in ALLOWED_STROKE_METHODS:
        raise ValueError(f"stroke_method '{value}' not in {ALLOWED_STROKE_METHODS}")
    brush.stroke_method = value
```

### COMPAT-04: Annotation API (Blender 5.x)
```python
# Source: https://developer.blender.org/docs/release_notes/5.0/python_api/
# addon/handlers/gpencil.py — create annotation object pattern
ann_data = bpy.data.annotations.new(name)  # was: bpy.data.grease_pencils.new()
# Note: bpy.ops.object.gpencil_add() removed on 5.x for annotation use
# Annotations are not scene objects — they are viewport overlay data
layer = ann_data.layers.new(layer_name)
frame = layer.frames.new(bpy.context.scene.frame_current)
stroke = frame.strokes.new()
stroke.points.add(len(points_data))
for i, pt in enumerate(points_data):
    stroke.points[i].co = tuple(pt)
    stroke.points[i].pressure = pressure
    # AnnotationStroke has no .strength property
```

### COMPAT-05: VSE Properties — No Code to Write
```python
# No existing handler references VSE strip time properties.
# Verified by: grep -r "frame_final_duration\|frame_final_start\|frame_offset_start" addon/ src/
# Result: no matches. COMPAT-05 is satisfied by the absence of code.
```

### Handler Test Pattern (mock-based, following existing conftest.py)
```python
# tests/test_addon/test_handlers/test_rendering_handler.py
"""Tests for rendering handler — validates 5.1 API compliance with mocked bpy."""
import sys
from unittest.mock import MagicMock, patch
import pytest

# bpy is already mocked in tests/test_addon/conftest.py
import bpy  # resolves to MagicMock

def test_handle_set_render_engine_eevee():
    """handle_set_render_engine must use BLENDER_EEVEE (5.x) not BLENDER_EEVEE_NEXT."""
    bpy.context.scene.render.engine = None  # capture assignment
    from addon.handlers.rendering import handle_set_render_engine
    handle_set_render_engine({"engine": "BLENDER_EEVEE"})
    assert bpy.context.scene.render.engine == "BLENDER_EEVEE"
```

### GitHub Actions CI Workflow for bpy 5.1
```yaml
# .github/workflows/test-bpy51.yml
name: Handler Tests (bpy 5.1)
on: [push, pull_request]
jobs:
  handler-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install dependencies
        run: |
          pip install bpy==5.1.0
          pip install pytest pytest-cov
      - name: Run handler tests
        run: pytest tests/test_addon/test_handlers/ -v
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `BLENDER_EEVEE_NEXT` engine identifier | `BLENDER_EEVEE` | Blender 5.0 | All engine enum comparisons must use new name |
| `scene.node_tree` for compositor | `scene.compositing_node_group` | Blender 5.0 | Direct attribute access; `scene.use_nodes` deprecated |
| `bpy.data.grease_pencils` for annotations | `bpy.data.annotations` | Blender 5.0 | Entirely separate data block type |
| `GPencilStroke` type | `AnnotationStroke` type | Blender 5.0 | `.strength` property absent from AnnotationStroke |
| 8 individual brush stroke booleans | `brush.stroke_method` enum | Blender 5.1 | Single settable property replaces 8 |
| `sculpt.sample_color` operator | `paint.sample_color` | Blender 5.1 | Not referenced in current handlers — no change needed |
| VSE `frame_final_duration` | VSE `duration` | Blender 5.1 | Deprecated (not removed); not referenced in codebase |
| `bpy.types.GreasePencil` (unified) | `bpy.types.Annotation` (overlays) + `bpy.types.GreasePencilv3` (3D objects) | Blender 5.0 | Handler must target one type explicitly |

**Deprecated/outdated:**
- `BLENDER_EEVEE_NEXT`: Removed in Blender 5.0; using it silently sets no engine or errors
- `scene.node_tree` (compositor): Removed in Blender 5.0
- `bpy.ops.object.gpencil_add`: Behavior changed; no longer creates annotation data on 5.x
- `scene.use_nodes`: Deprecated in 5.0; always returns True; do not call

## Open Questions

1. **Does `bpy.context.scene.eevee.taa_render_samples` still exist in Blender 5.1?**
   - What we know: EEVEE was significantly refactored in 5.0 (new lighting model). Some `eevee` properties moved (e.g., `gtao_distance` moved to `view_layer.eevee`).
   - What's unclear: Whether `taa_render_samples` was also relocated.
   - Recommendation: The handler test with `bpy==5.1.0` in CI will catch this. If it fails, look for the property under `scene.eevee` in the 5.1 API docs. Mark as a known risk in the plan.

2. **Can `bpy.ops.object.gpencil_add` be avoided entirely for annotation creation?**
   - What we know: The old handler uses this operator. On 5.x, annotations are not scene objects — they are `bpy.data.annotations` blocks used as viewport overlays, not placed in the scene as objects. This is a fundamentally different model.
   - What's unclear: Whether MCP clients expect annotation tools to create viewport overlays or 3D scene objects.
   - Recommendation: Target `bpy.data.annotations` for annotation functionality. If 3D GP drawing objects are needed, that is a separate GPENCIL v3 handler for a future phase.

3. **Does `fake-bpy-module-5.1` exist yet?**
   - What we know: Latest fake-bpy-module release (20260128) only covers up to 5.0.
   - What's unclear: Whether a 5.1 release is imminent.
   - Recommendation: Do not wait for it. Use `bpy==5.1.0` in CI and `MagicMock` in local handler tests.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.13 | bpy==5.1.0 in CI | Yes (local) | 3.13.2 | — |
| uv | Package management | Yes | 0.10.11 | pip |
| pytest | Test runner | Yes (via uv run) | 9.0.2 | — |
| bpy==5.1.0 | CI handler tests | Not installed locally | 5.1.0 on PyPI | MagicMock for local dev |
| GitHub Actions | CI workflow | Yes (existing workflows) | ubuntu-latest | — |

**Missing dependencies with no fallback:**
- `bpy==5.1.0` is required for the CI success criterion but is not installed locally (and should not be — it pulls in all of Blender's Python dependencies). The plan must include a step that installs it in CI only.

**Missing dependencies with fallback:**
- Local handler tests: use `MagicMock` (as in `tests/test_addon/conftest.py`) rather than real `bpy`. The CI job validates real API behavior.

## Sources

### Primary (HIGH confidence)
- [Blender 5.0 Python API Release Notes](https://developer.blender.org/docs/release_notes/5.0/python_api/) — EEVEE rename, compositor node_tree removal, annotation split, paint system
- [Blender 5.1 Python API Release Notes](https://developer.blender.org/docs/release_notes/5.1/python_api/) — brush.stroke_method, VSE renames, sculpt.sample_color removal, Python 3.13
- [bpy 5.1.0 on PyPI](https://pypi.org/project/bpy/) — Python ==3.13.* requirement, platforms, release date March 17, 2026

### Secondary (MEDIUM confidence)
- [nutti/fake-bpy-module releases](https://github.com/nutti/fake-bpy-module/releases) — confirms 5.1 not yet supported (latest 20260128 = 5.0 max)
- WebSearch results on Annotation API split — confirms `bpy.data.annotations.new()`, `bpy.types.Annotation`, `AnnotationStroke` naming on 5.x

### Tertiary (LOW confidence)
- Training knowledge on `eevee.taa_render_samples` availability in 5.1 — flagged as open question; CI test will verify

## Metadata

**Confidence breakdown:**
- COMPAT-01 (EEVEE): HIGH — confirmed by official 5.0 release notes
- COMPAT-02 (compositor): HIGH — confirmed by official 5.0 release notes; no handler currently exists so impact is low
- COMPAT-03 (sculpt stroke_method): HIGH — confirmed by official 5.1 release notes; current handler does not reference removed properties so impact is minimal
- COMPAT-04 (annotation split): HIGH — confirmed by official 5.0 release notes + API docs showing `bpy.data.annotations`; scope decision (annotation vs GPv3) is locked in this research
- COMPAT-05 (VSE): HIGH — grep confirms zero references to deprecated VSE properties; no code to write
- COMPAT-06 (Python 3.13): HIGH — test suite already passes on Python 3.13.2; CI workflow needs creation
- CI workflow pattern: HIGH — existing `.github/workflows/` confirms infrastructure; `bpy==5.1.0` pip availability confirmed

**Research date:** 2026-03-23
**Valid until:** Stable (Blender 5.1 API is released and finalized; valid until Blender 5.2 or 6.0 breaking changes)
