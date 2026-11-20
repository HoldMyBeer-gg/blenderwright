"""Load tools from separately installed packages.

A package adds tools by declaring an entry point in the blenderwright.plugins
group, for example in its pyproject.toml:

    [project.entry-points."blenderwright.plugins"]
    my_plugin = "my_package.tools"

Loading the entry point imports that module, and its @mcp.tool() decorators
register the tools on the shared server like any built-in module. A plugin
that wants its tools reachable in auto or core mode calls
toolsets.register_toolset() with its module name.

Plugins are installed Python packages, so they carry the same trust as any
other dependency; this adds no new way to run code.
"""

import sys
from importlib.metadata import entry_points

PLUGIN_GROUP = "blenderwright.plugins"


def load_plugins() -> list[str]:
    """Import every installed plugin.

    A plugin that fails to import is reported on stderr and skipped, so one
    broken package cannot take the whole server down.

    Returns:
        Names of the plugins that loaded, in discovery order.
    """
    loaded = []
    for ep in entry_points(group=PLUGIN_GROUP):
        try:
            ep.load()
        except Exception as exc:
            print(f"blenderwright: plugin {ep.name!r} failed to load: {exc}", file=sys.stderr)
            continue
        loaded.append(ep.name)
    return loaded
