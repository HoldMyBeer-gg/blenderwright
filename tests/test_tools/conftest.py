"""Conftest that mocks blend_ai.server before tool modules are imported.

The real server.py creates a FastMCP instance and eagerly imports every tool
module (plus resources/prompts), which pulls in dependencies that may not be
available in the test environment.  We replace the server module with a thin
mock so that tool modules can be imported in isolation.
"""

import sys
import types
from unittest.mock import MagicMock

# Build a fake ``blend_ai.server`` module with the two names every tool file
# imports: ``mcp`` (with a no-op ``tool`` decorator) and ``get_connection``.

_fake_server = types.ModuleType("blend_ai.server")

# ``mcp.tool()`` is used as a decorator – it must return the function unchanged.
_mcp_mock = MagicMock()
_mcp_mock.tool.return_value = lambda fn: fn  # @mcp.tool() → identity decorator
_fake_server.mcp = _mcp_mock  # type: ignore[attr-defined]

# ``get_connection`` will be patched per-test via the ``mock_conn`` fixture, but
# we still need a placeholder so the import-time reference resolves.
_fake_server.get_connection = MagicMock()  # type: ignore[attr-defined]

# Inject *before* any tool module is imported.
sys.modules.setdefault("blend_ai.server", _fake_server)
