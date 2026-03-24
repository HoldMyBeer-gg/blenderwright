# Phase 04: Security & New 5.1 Tools - Research

**Researched:** 2026-03-24
**Domain:** Python sandboxing, Blender 5.1 new nodes/operators, EEVEE light path, SLIM UV unwrap
**Confidence:** HIGH (sandboxing), MEDIUM (new 5.1 node names — need runtime verification)

## Summary

Phase 4 has two major work areas: (1) sandboxing `code_exec` against RCE by restricting dangerous builtins and imports, and (2) adding MCP tool support for Blender 5.1's new shader/geometry/compositor nodes and features.

For sandboxing, the approach is a restricted `__builtins__` dict that removes `__import__`, `exec`, `eval`, `compile`, `open`, `globals`, and `input`, plus an import hook that blocks dangerous modules (`os`, `subprocess`, `socket`, `shutil`, `sys`, `ctypes`, `importlib`). This is simpler and more maintainable than RestrictedPython and sufficient for the localhost-only threat model.

For new 5.1 tools, the main additions are: new shader node types added to the allowlist, a SLIM UV unwrap method option, and EEVEE light path intensity controls.

**Primary recommendation:** Three plans: (1) code_exec sandboxing with import blocking, (2) new 5.1 node types in allowlists, (3) SLIM UV unwrap + EEVEE light path intensity.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STAB-03 | code_exec sandboxed against RCE — import os/subprocess/socket blocked | Restricted builtins dict + import hook in handler |
| NEW51-01 | Raycast shader node available via add_shader_node | Add "ShaderNodeRaycast" to ALLOWED_SHADER_NODE_TYPES |
| NEW51-02 | Bone Info geometry node available | Add to geometry node allowlist (if one exists) or document |
| NEW51-03 | Grid Dilate/Erode compositor nodes available | Add to compositor node allowlist |
| NEW51-04 | Mask to SDF compositor node available | Add to compositor node allowlist |
| NEW51-05 | SLIM UV unwrap method available | Add "SLIM" to allowed unwrap methods in UV tools |
| NEW51-06 | EEVEE Light Path Intensity controls accessible | New tool or property setter for EEVEE light path settings |
| NEW51-07 | N-panel unsafe mode toggle for code_exec | UI property in addon preferences, read by handler |
</phase_requirements>

## Architecture Patterns

### Pattern 1: Code Exec Sandboxing

**What:** Replace `exec(code, {"__builtins__": __builtins__})` with a restricted exec that blocks dangerous imports and builtins.

**Approach — Import hook + restricted builtins:**

```python
# Blocked modules — no access to OS, network, process, or dynamic import
BLOCKED_MODULES = {
    "os", "subprocess", "socket", "shutil", "sys", "ctypes",
    "importlib", "pathlib", "signal", "multiprocessing", "threading",
    "pickle", "shelve", "tempfile", "http", "urllib", "ftplib",
    "smtplib", "xmlrpc", "code", "codeop", "compileall",
}

# Safe builtins — everything except dangerous functions
SAFE_BUILTINS = {
    k: v for k, v in __builtins__.items()
    if k not in {
        "__import__", "exec", "eval", "compile", "open",
        "globals", "locals", "vars", "input", "breakpoint",
        "exit", "quit", "help", "memoryview",
    }
} if isinstance(__builtins__, dict) else {
    k: getattr(__builtins__, k) for k in dir(__builtins__)
    if k not in {
        "__import__", "exec", "eval", "compile", "open",
        "globals", "locals", "vars", "input", "breakpoint",
        "exit", "quit", "help", "memoryview",
    } and not k.startswith("_")
}

def _safe_import(name, *args, **kwargs):
    """Import hook that blocks dangerous modules."""
    base_module = name.split(".")[0]
    if base_module in BLOCKED_MODULES:
        raise ImportError(f"Module '{name}' is blocked for security reasons")
    return __builtins__.__import__(name, *args, **kwargs)

# Add safe import to builtins
SAFE_BUILTINS["__import__"] = _safe_import
```

The `exec()` call becomes:
```python
exec(code, {"__builtins__": SAFE_BUILTINS})
```

This blocks:
- `import os` → ImportError
- `import subprocess` → ImportError
- `__import__("os")` → ImportError
- `exec("malicious")` → NameError (exec not in builtins)
- `eval("malicious")` → NameError
- `open("/etc/passwd")` → NameError
- `import bpy` → ✓ ALLOWED (bpy is safe)
- `import bmesh` → ✓ ALLOWED
- `import mathutils` → ✓ ALLOWED
- `import math` → ✓ ALLOWED

### Pattern 2: N-Panel Unsafe Mode Toggle

**What:** A BoolProperty in addon preferences that enables/disables the sandbox. Defaults to OFF (sandboxed). When ON, the old unrestricted exec is used.

```python
# In addon/__init__.py or a preferences module
class BlendAIPreferences(bpy.types.AddonPreferences):
    bl_idname = "blend_ai"  # or the addon module name
    
    unsafe_mode: bpy.props.BoolProperty(
        name="Unsafe Mode",
        description="Allow unrestricted code execution (DANGEROUS)",
        default=False,
    )
```

The handler reads this preference:
```python
def handle_execute_code(params: dict) -> dict:
    # Check if unsafe mode is enabled
    prefs = bpy.context.preferences.addons.get("blend_ai")
    unsafe = prefs and prefs.preferences.unsafe_mode if prefs else False
    
    if unsafe:
        exec(code, {"__builtins__": __builtins__})
    else:
        exec(code, {"__builtins__": SAFE_BUILTINS})
```

### Pattern 3: Adding New Node Types to Allowlists

The existing `ALLOWED_SHADER_NODE_TYPES` in `src/blend_ai/tools/materials.py` needs new 5.1 entries. Same pattern — just add strings to the set.

For Blender 5.1 new shader nodes, the exact type names need verification. Known new nodes:
- Raycast node: `ShaderNodeRaycast` (needs verification)

For geometry nodes and compositor nodes, there may be separate allowlists or they may need to be created.

### Pattern 4: SLIM UV Unwrap

The UV unwrap tool likely has a method parameter. SLIM was added in Blender 5.1 as a new unwrap algorithm.

```python
# In src/blend_ai/tools/uv.py
ALLOWED_UNWRAP_METHODS = {"ANGLE_BASED", "CONFORMAL", "SLIM"}
```

### Pattern 5: EEVEE Light Path Intensity

EEVEE in Blender 5.1 added Light Path Intensity controls for diffuse, glossy, and transmission bounces:
```python
# Access via scene.eevee
scene.eevee.light_path_diffuse_intensity = 1.0
scene.eevee.light_path_glossy_intensity = 1.0  
scene.eevee.light_path_transmission_intensity = 1.0
```

## Common Pitfalls

### Pitfall 1: `__builtins__` is a dict in modules but a module in __main__
**What goes wrong:** Code assumes `__builtins__` is always a dict.
**How to avoid:** Handle both cases: `isinstance(__builtins__, dict)` check.

### Pitfall 2: Sandbox bypass via `__class__.__bases__`
**What goes wrong:** Python allows attribute chain escapes: `().__class__.__bases__[0].__subclasses__()` to find `os._wrap_close` etc.
**How to avoid:** For localhost-only use, this is an acceptable risk. The sandbox blocks casual/accidental dangerous imports, not determined attackers. The N-panel toggle provides an escape valve.

### Pitfall 3: New 5.1 node type names may differ
**What goes wrong:** Adding "ShaderNodeRaycast" when the actual name is different.
**How to avoid:** The plan should note which names are confirmed vs inferred. Tests should verify the names are in the allowlist but can't verify they work in Blender without a running instance.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `addon/handlers/code_exec.py`, `src/blend_ai/tools/materials.py`, `src/blend_ai/tools/uv.py`
- Python docs: `exec()` globals parameter, `__builtins__` behavior

### Secondary (MEDIUM confidence)  
- Blender 5.1 release notes for new node types (need web verification)
- EEVEE light path intensity property names (need API verification)

## Metadata

**Confidence:**
- Code exec sandboxing: HIGH — well-understood Python exec restriction pattern
- N-panel toggle: HIGH — standard Blender addon preference pattern
- New node type names: MEDIUM — need runtime verification
- SLIM UV method: MEDIUM — name needs verification
- EEVEE light path properties: MEDIUM — property names need verification

**Research date:** 2026-03-24
