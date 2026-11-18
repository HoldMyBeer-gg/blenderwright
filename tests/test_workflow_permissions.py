"""Every workflow limits its GITHUB_TOKEN.

Without a permissions block a workflow gets the repository default, which
can include write access it never uses. Code scanning flagged ci.yml and
pylint.yml for this; the guard keeps a new workflow from repeating it.
"""

import os
import re

import pytest

WORKFLOWS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".github", "workflows"
)


@pytest.mark.parametrize(
    "name", sorted(f for f in os.listdir(WORKFLOWS) if f.endswith((".yml", ".yaml")))
)
def test_workflow_declares_top_level_permissions(name):
    with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as f:
        text = f.read()
    assert re.search(r"^permissions:", text, re.M), f"{name} has no top-level permissions"
