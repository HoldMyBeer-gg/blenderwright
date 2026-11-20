"""The README must ask for sponsorship with a badge that actually clicks through.

GitHub proxies README images through camo, which drops shields.io's
``link=`` parameter, so a bare badge image opens the SVG instead of the
Sponsors page. The badge has to be wrapped in a markdown link.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPONSORS_URL = "https://github.com/sponsors/jabberwock"


def _readme() -> str:
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        return f.read()


def test_sponsor_badge_is_wrapped_in_a_link():
    pattern = r"\[!\[[^\]]*\]\(https://img\.shields\.io/github/sponsors/jabberwock[^)]*\)\]\(" + (
        re.escape(SPONSORS_URL) + r"\)"
    )
    assert re.search(pattern, _readme()), "sponsor badge missing or not clickable"


def test_sponsor_ask_appears_before_the_first_demo():
    readme = _readme()
    first_image = readme.index("![blenderwright")
    assert readme.find(SPONSORS_URL) != -1
    assert readme.find(SPONSORS_URL) < first_image, "sponsor ask is buried below the demos"
