"""Fixtures for the tool-layer tests.

This file used to install a fake ``blend_ai.server`` module into sys.modules
at collection, with sys.modules.setdefault, and never remove it. Whether any
test saw the real server then depended on import order, which made assertions
against the real tool registry pass alone and fail in suite, and produced
fifteen collection errors in tests/test_ollama_chat.py that looked
unexplained and pre-existing for a long time.

Nothing needs it. The two prompt test modules that reached into the mock to
make ``@mcp.prompt()`` behave as a decorator were working around a problem the
real FastMCP does not have: its decorator already returns the function. The
whole suite passes against the real server.
"""
