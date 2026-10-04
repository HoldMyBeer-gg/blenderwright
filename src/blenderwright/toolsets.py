"""Load a subset of the tools, or let the model load them on demand.

All 191 tool schemas cost about 48k tokens on every request. A Claude-class
client absorbs that, and seeing the whole menu is part of why the output is
good: a model only reaches for tools it can see. A 32k local model has nothing
left for the conversation and starts dropping messages mid-task.

The default is unchanged: every tool, every time. Opting down is explicit,
through BLENDERWRIGHT_TOOLSETS or --toolsets:

    all              every tool (the default)
    auto             the core set plus two meta tools; the model enables
                     the rest as it needs them
    core             the core set only
    modeling,uv      those modules only; "core" may appear in the list

Each toolset is one tool module, so the grouping cannot drift from the code.
Parked tools keep the Tool object strict.py and enum_hints.py already
hardened, so enabling one later hands back the same schema, not a rebuild.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context

# One line per module. This is what the model reads to decide what to enable,
# so each line names the things a user would ask for, not the implementation.
TOOLSETS: dict[str, str] = {
    "scene": "Scene info, frame range, scenes, extension suggestions",
    "objects": "Create primitives, prisms and threaded shafts; duplicate, join, parent, "
               "rename, delete, visibility, auto-smooth",
    "transforms": "Move, rotate, scale, apply transforms, set origin, snap to grid",
    "modeling": "Modifiers, boolean via modifier, subdivide, extrude, bevel, loop cut, "
                "merge, separate, bridge edge loops",
    "mesh_editing": "Edit-mode operations: inset, fill, seams, sharp, normals, dissolve, "
                    "knife project, spin, crease",
    "selection": "Select vertices, edges or faces by index, axis, similarity or side "
                 "count; report what is selected",
    "mesh_quality": "Find and repair mesh defects; decimate",
    "booltool": "Destructive boolean union, difference, intersect and slice",
    "materials": "Colours, metal, glass, emission; procedural wood, marble, fire and "
                 "more; raster textures; the shader node graph; colour ramps",
    "lighting": "Point, sun, spot and area lights, HDRI world, light rigs, shadows",
    "camera": "Create and aim cameras, depth of field, set from view, capture viewport",
    "animation": "Keyframes, interpolation, frame range, follow-path animation",
    "rendering": "Engine, resolution, samples, output format, render stills and animations",
    "curves": "Bezier, NURBS and path curves, 3D text, convert to mesh",
    "sweep": "Sweep a profile along a path: tubes, hoses, cables, rails",
    "print3d": "Check a mesh for 3D printability",
    "sequencer": "Video sequencer: image and sound strips, render to MP4, MKV or WebM",
    "sculpting": "Sculpt mode, brushes, remesh, multires, symmetry, dyntopo",
    "uv": "UV unwrap, smart project, projection, pack islands",
    "physics": "Rigid body, cloth, fluid, particles, bake",
    "geometry_nodes": "Geometry node trees: create, add, connect, set inputs",
    "armature": "Armatures, bones, constraints, weights, pose",
    "gpencil": "Annotation layers and strokes",
    "collections": "Collections: create, move objects, visibility, delete",
    "file_ops": "Import and export FBX, OBJ, glTF, USD, STL; save and open .blend",
    "viewport": "Viewport shading, overlays, focus on object",
    "screenshot": "Capture the viewport as an image for visual checks",
    "code_exec": "Run sandboxed Python inside Blender",
}

# What a model needs to build, check and present something without asking for
# more. The quality loop (look at it, check the mesh, light it, render it) is
# in here on purpose: a model only uses what it can see.
CORE: frozenset[str] = frozenset({
    "scene", "objects", "transforms", "modeling", "mesh_quality",
    "lighting", "camera", "rendering", "screenshot", "viewport", "collections",
})

META_TOOLS = ("list_toolsets", "enable_toolset")

_PARKED_ATTR = "_blenderwright_parked"
_MODE_ATTR = "_blenderwright_toolset_mode"


class ToolsetError(ValueError):
    """A toolset name that does not exist, or a spec that cannot be combined."""


@dataclass(frozen=True)
class Applied:
    mode: str
    enabled: frozenset[str]


def _module_of(tool: Any) -> str:
    return tool.fn.__module__.rsplit(".", 1)[-1]


def _registry(server: Any) -> dict[str, Any]:
    return server._tool_manager._tools


def _parked(server: Any) -> dict[str, Any]:
    if not hasattr(server, _PARKED_ATTR):
        setattr(server, _PARKED_ATTR, {})
    return getattr(server, _PARKED_ATTR)


def tools_by_toolset(server: Any) -> dict[str, list[str]]:
    """Map each toolset to the tool names it contains, parked or not.

    Args:
        server: A FastMCP instance with the tool modules imported.

    Returns:
        Toolset name to sorted tool names. The meta tools are not listed; they
        belong to no toolset.
    """
    grouped: dict[str, list[str]] = {}
    for name, tool in list(_registry(server).items()) + list(_parked(server).items()):
        if name in META_TOOLS:
            continue
        grouped.setdefault(_module_of(tool), []).append(name)
    return {k: sorted(v) for k, v in grouped.items()}


def parse_spec(value: str | None) -> tuple[str, frozenset[str]]:
    """Read a BLENDERWRIGHT_TOOLSETS value.

    Args:
        value: None, "all", "auto", "core", or a comma-separated list of
            toolset names in which "core" expands to the core set.

    Returns:
        (mode, names): mode is "all", "auto" or "static". names is empty
        unless mode is "static".

    Raises:
        ToolsetError: an unknown name, or "auto" combined with anything.
    """
    text = (value or "").strip().lower()
    if not text or text == "all":
        return "all", frozenset()
    if text == "auto":
        return "auto", frozenset()

    parts = [p.strip() for p in text.split(",") if p.strip()]
    if "auto" in parts or "all" in parts:
        raise ToolsetError("'auto' and 'all' stand alone; they cannot be combined")

    chosen: set[str] = set()
    for part in parts:
        if part == "core":
            chosen |= CORE
        elif part in TOOLSETS:
            chosen.add(part)
        else:
            raise ToolsetError(
                f"unknown toolset {part!r}. Valid names: core, "
                + ", ".join(sorted(TOOLSETS))
            )
    return "static", frozenset(chosen)


def restore_all(server: Any) -> None:
    """Put every parked tool back and remove the meta tools."""
    registry = _registry(server)
    parked = _parked(server)
    registry.update(parked)
    parked.clear()
    for name in META_TOOLS:
        registry.pop(name, None)
    setattr(server, _MODE_ATTR, "all")


def _park_except(server: Any, keep: frozenset[str]) -> None:
    registry = _registry(server)
    parked = _parked(server)
    for name, tool in list(registry.items()):
        if name in META_TOOLS:
            continue
        if _module_of(tool) not in keep:
            parked[name] = registry.pop(name)


def enable_toolset(server: Any, name: str) -> list[str]:
    """Bring a parked toolset back into the registry.

    Args:
        server: The FastMCP instance.
        name: A toolset name.

    Returns:
        The tool names added, sorted. Empty if the set was already enabled.

    Raises:
        ToolsetError: the name is not a toolset.
    """
    if name not in TOOLSETS:
        raise ToolsetError(
            f"unknown toolset {name!r}. Valid names: " + ", ".join(sorted(TOOLSETS))
        )
    registry = _registry(server)
    parked = _parked(server)
    added = []
    for tool_name in list(parked):
        if _module_of(parked[tool_name]) == name:
            registry[tool_name] = parked.pop(tool_name)
            added.append(tool_name)
    return sorted(added)


def enabled_toolsets(server: Any) -> frozenset[str]:
    """Toolsets with at least one tool currently in the registry."""
    return frozenset(
        _module_of(t) for n, t in _registry(server).items() if n not in META_TOOLS
    )


def mode_of(server: Any) -> str:
    return getattr(server, _MODE_ATTR, "all")


def _install_meta_tools(server: Any) -> None:
    registry = _registry(server)
    if all(name in registry for name in META_TOOLS):
        return

    def list_toolsets() -> dict[str, Any]:
        """List the optional tool groups and which are loaded.

        Only a core set of tools is loaded to keep the context small. Call
        enable_toolset with a name from this list to load the rest of that
        group; its tools then appear in the tool list.

        Returns:
            Dict of toolset name to its summary, whether it is enabled, and
            the tool names it contains.
        """
        grouped = tools_by_toolset(server)
        on = enabled_toolsets(server)
        return {
            name: {
                "summary": TOOLSETS[name],
                "enabled": name in on,
                "tools": grouped.get(name, []),
            }
            for name in sorted(TOOLSETS)
        }

    async def enable_toolset_tool(name: str, ctx: Context) -> dict[str, Any]:
        """Load an optional tool group so its tools can be called.

        The server starts with a core set. When a task needs materials,
        physics, sculpting, animation, curves or another group, call this
        with the group's name, then call the tools it lists. See
        list_toolsets for names and summaries.

        Args:
            name: Toolset name, e.g. "materials", "physics", "animation".

        Returns:
            Dict with the toolset enabled and the tool names now available.
        """
        added = enable_toolset(server, name)
        try:
            await ctx.session.send_tool_list_changed()
        except (ValueError, AttributeError):
            # No MCP session: the bundled Ollama client calls tools directly
            # and refreshes its own list from the result.
            pass
        return {
            "enabled": name,
            "added": len(added),
            "tools": tools_by_toolset(server).get(name, []),
        }

    server.add_tool(list_toolsets, name="list_toolsets")
    server.add_tool(enable_toolset_tool, name="enable_toolset")


def apply_toolsets(server: Any, spec: str | None) -> Applied:
    """Shape the registry to a spec. Safe to call again with a different spec.

    Args:
        server: The FastMCP instance with every tool module imported.
        spec: A BLENDERWRIGHT_TOOLSETS value; see parse_spec.

    Returns:
        The mode applied and the toolsets now enabled.
    """
    mode, chosen = parse_spec(spec)
    restore_all(server)
    if mode == "all":
        return Applied("all", frozenset(TOOLSETS))
    if mode == "auto":
        _park_except(server, CORE)
        _install_meta_tools(server)
        setattr(server, _MODE_ATTR, "auto")
        return Applied("auto", CORE)
    _park_except(server, chosen)
    setattr(server, _MODE_ATTR, "static")
    return Applied("static", chosen)
