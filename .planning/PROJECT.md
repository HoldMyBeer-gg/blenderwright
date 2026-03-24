# Blend AI

## What This Is

The most intuitive and complete MCP server for Blender — an AI-powered bridge that lets any MCP-compatible client (Claude, etc.) control Blender with expert-level quality. It goes beyond tool exposure: it guides the LLM to produce professional 3D results through smart prompts, proven workflows, and automatic visual feedback.

## Core Value

An LLM using this MCP should produce professional-quality 3D output without the user needing to know Blender — the MCP provides the expertise.

## Requirements

### Validated

- ✓ Three-tier MCP-to-TCP bridge architecture (stdio → TCP → Blender addon) — existing
- ✓ 161 tools across 24 modules (scene, objects, materials, rendering, etc.) — existing
- ✓ Thread-safe command dispatch via main-thread queue — existing
- ✓ Render guard with busy-state retry logic — existing
- ✓ Input validation layer (names, paths, numerics, enums, shader nodes) — existing
- ✓ Command allowlist security (only registered handlers execute) — existing
- ✓ Localhost-only communication (127.0.0.1:9876) — existing
- ✓ N-panel UI for server start/stop — existing
- ✓ Screenshot capture tool — existing
- ✓ Code execution tool (with security concerns) — existing

### Active

- [x] Auto-screenshot feedback loop — after building/modifying, LLM captures viewport and critiques result (Validated in Phase 3)
- [x] Context-aware Blender extension suggestions — when a task would benefit from a free plugin, suggest it before starting (Validated in Phase 2)
- [x] Full Blender 5.1 compatibility — fix any breaking changes from 4.x API (Validated in Phase 1)
- [ ] New Blender 5.1 tools — expose new operators, nodes, and features added in 5.1
- [x] Expert-quality MCP prompts — guide the LLM on best practices, proven modeling patterns, and optimal parameter choices (Validated in Phase 2)
- [x] Improved mesh quality — better defaults, proper topology, connected geometry, realistic proportions (Validated in Phase 2)
- [ ] Missing tool coverage — boolean operations, edge loops, snapping, and other gaps that force workarounds
- [ ] Smarter workflow tools — high-level operations that chain multiple low-level tools into expert patterns
- [x] Fix known bugs — render guard stuck state, stale connections, screenshot blocking during renders (Validated in Phase 2 + 3)
- [x] Harden security — address code_exec vulnerability, add command auditing, improve path validation (Validated in Phase 4)
- [ ] Improve test coverage — code_exec sandbox unvalidated, socket error paths uncovered (handler tests added in Phase 1)

### Out of Scope

- Mobile/remote access — localhost-only is a security feature, not a limitation
- Multi-user collaboration — Blender is single-threaded, MCP is single-connection by design
- Real-time streaming — MCP protocol is request/response; streaming would require protocol changes
- Non-Blender 3D tools — this is Blender-specific, not a general 3D MCP

## Context

- Existing codebase: ~161 tools, Python MCP server + Blender addon, v0.2.0
- Architecture: MCP (stdio) → TCP socket → Blender addon (main thread queue)
- Known issues: code_exec security vulnerability, render guard can get stuck, timeout mismatches between layers, parameter validation inconsistencies in addon handlers
- Competition: Other Blender MCPs exist but produce rough results and lack workflow intelligence
- User pain: Models look toy-like, meshes don't connect properly, LLM doesn't know best Blender practices
- Blender target: Full 5.1 support (Phase 1 complete — EEVEE renamed, GPencil→Annotation, sculpt stroke_method, CI on Python 3.13)

## Constraints

- **Thread model**: Blender is single-threaded — all bpy calls must run on main thread via queue
- **Security**: No arbitrary code execution without sandboxing; localhost-only; command allowlist
- **MCP protocol**: Stateless request/response — no persistent session context between calls
- **Test-first**: Project rules require writing unit tests before implementation code
- **Blender API**: Must use official Python API (bpy); no private/internal API access

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Auto-screenshot for feedback (not iterative loop) | Simpler to implement, less token-heavy, user can trigger more cycles manually | — Pending |
| Context-aware plugin suggestions (not searchable tool) | Proactive suggestions fit the "smart assistant" vision better than a search tool | — Pending |
| Full 5.1 compat + new features | Users expect both backward compat and access to new capabilities | Phase 1 complete |
| Expert prompts over more tools | The LLM needs guidance on HOW to use tools well, not just more tools | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-24 after Phase 1 completion*
