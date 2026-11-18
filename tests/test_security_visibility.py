"""The security model must be visible where search engines and AI summaries look.

Search summaries of blenderwright missed the signed socket entirely, because
it lived only in a collapsed section at the bottom of the README. These
tests pin the claims to the places that get indexed: the README's feature
list, the PyPI summary, and the docs site's head and header.
"""

import os
import re
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def _key_features():
    readme = _read("README.md")
    match = re.search(r"## Key Features\n(.*?)\n## ", readme, re.S)
    assert match, "Key Features section not found"
    return match.group(1)


def test_key_features_names_the_signed_socket():
    features = _key_features().lower()
    assert "signed" in features
    assert "hmac" in features


def test_key_features_names_raw_python_off_by_default():
    assert "allow raw python" in _key_features().lower()


def test_readme_never_calls_raw_python_a_sandbox():
    readme = _read("README.md")
    assert "Sandboxed" not in readme


def test_security_section_is_not_collapsed():
    readme = _read("README.md")
    assert "<summary><strong>Security</strong></summary>" not in readme
    assert re.search(r"^## Security\s*$", readme, re.M)


def test_pypi_summary_mentions_signed_socket_and_raw_python():
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        summary = tomllib.load(f)["project"]["description"].lower()
    assert "signed" in summary
    assert "raw python" in summary


def test_docs_site_meta_description_mentions_security_model():
    html = _read("docs", "index.html")
    meta = re.search(r'<meta name="description" content="([^"]*)"', html).group(1).lower()
    assert "signed" in meta
    assert "raw python" in meta


def test_docs_site_has_security_block_in_header():
    html = _read("docs", "index.html")
    header = re.search(r"<header>(.*?)</header>", html, re.S).group(1)
    assert 'id="security"' in header
    assert "HMAC" in header


def test_readme_compares_the_security_model_with_other_blender_mcp_servers():
    readme = _read("README.md")
    match = re.search(r"## How it compares\n(.*?)\n## ", readme, re.S)
    assert match, "comparison section not found"
    section = match.group(1)
    assert "lab/blender_mcp" in section
    assert "mcp-for-blender" in section
    assert "Checked against" in section
