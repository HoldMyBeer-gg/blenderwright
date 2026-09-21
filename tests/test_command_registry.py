"""Guard against a command name being claimed twice.

Both layers resolve a name collision silently, and they resolve it in
opposite directions. FastMCP's add_tool keeps the first registration and
logs a warning. The dispatcher's register_handler is a plain dict
assignment, so it keeps the last. A name defined in two modules therefore
exposes one module's schema and runs the other module's handler, and the
parameters no longer line up.

Per-module unit tests cannot see this. Each one imports its own function
by name and mocks the connection, so both halves of a duplicate pass in
isolation. These tests read the whole tree instead.
"""

import ast
import collections
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(ROOT, "src", "blend_ai", "tools")
HANDLERS_DIR = os.path.join(ROOT, "addon", "handlers")


def _modules(directory):
    for filename in sorted(os.listdir(directory)):
        if filename.endswith(".py") and filename != "__init__.py":
            with open(os.path.join(directory, filename)) as f:
                yield filename, ast.parse(f.read())


def _is_mcp_tool(node):
    """True if the function carries an @mcp.tool() decorator."""
    for decorator in node.decorator_list:
        func = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(func, ast.Attribute) and func.attr == "tool":
            return True
    return False


def _callee_name(node):
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def _first_arg_literal(node):
    if node.args and isinstance(node.args[0], ast.Constant):
        if isinstance(node.args[0].value, str):
            return node.args[0].value
    return None


def _tool_names():
    """Tool name -> set of modules that register it with @mcp.tool()."""
    names = collections.defaultdict(set)
    for filename, tree in _modules(TOOLS_DIR):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _is_mcp_tool(node):
                    names[node.name].add(filename)
    return names


def _sent_commands():
    """Command string -> set of modules that transmit it.

    Covers conn.send_command("x", ...) and the private per-module helpers
    (_send_camera_command and friends), which all take the command name as
    their first positional argument.
    """
    names = collections.defaultdict(set)
    for filename, tree in _modules(TOOLS_DIR):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _callee_name(node)
            if callee == "send_command" or (
                callee.startswith("_send_") and callee.endswith("_command")
            ):
                command = _first_arg_literal(node)
                if command is not None:
                    names[command].add(filename)
    return names


def _registered_commands():
    """Command string -> set of handler modules that register it."""
    names = collections.defaultdict(set)
    for filename, tree in _modules(HANDLERS_DIR):
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _callee_name(node) == "register_handler":
                command = _first_arg_literal(node)
                if command is not None:
                    names[command].add(filename)
    return names


def test_no_duplicate_tool_names():
    """Two @mcp.tool() functions sharing a name: the second is dropped."""
    duplicates = {
        name: sorted(modules)
        for name, modules in _tool_names().items()
        if len(modules) > 1
    }
    assert not duplicates, (
        f"Tool names registered by more than one module: {duplicates}. "
        f"FastMCP keeps the first and logs 'Tool already exists', so the "
        f"later definition never reaches the client."
    )


def test_no_duplicate_handler_registrations():
    """Two register_handler calls sharing a name: the first is overwritten."""
    duplicates = {
        command: sorted(modules)
        for command, modules in _registered_commands().items()
        if len(modules) > 1
    }
    assert not duplicates, (
        f"Commands registered by more than one handler module: {duplicates}. "
        f"register_handler assigns into a dict, so the last registration "
        f"silently wins and the earlier handler is unreachable."
    )


def test_every_sent_command_has_a_handler():
    """A command with no handler fails at runtime with 'Unknown command'."""
    registered = _registered_commands()
    orphans = {
        command: sorted(modules)
        for command, modules in _sent_commands().items()
        if command not in registered
    }
    assert not orphans, (
        f"Commands sent by the tool layer with no addon handler: {orphans}."
    )


def test_every_sent_command_resolves_to_one_handler():
    """The pairing that matters: one schema, one implementation."""
    registered = _registered_commands()
    ambiguous = {
        command: sorted(registered[command])
        for command in _sent_commands()
        if len(registered.get(command, ())) > 1
    }
    assert not ambiguous, (
        f"Commands whose handler is ambiguous: {ambiguous}. The tool layer "
        f"and the dispatcher break ties in opposite directions, so the "
        f"exposed parameters and the executed handler can disagree."
    )
