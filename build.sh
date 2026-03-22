#!/usr/bin/env bash
# Build the blend-ai Blender addon zip for distribution.
# Usage: ./build.sh [version]
# Example: ./build.sh 0.2.0
#
# If no version is provided, reads it from addon/__init__.py bl_info.
# The zip contains a blend_ai/ folder so Blender installs it as the
# "blend_ai" addon module.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADDON_DIR="$SCRIPT_DIR/addon"

if [ ! -d "$ADDON_DIR" ]; then
    echo "Error: addon/ directory not found at $ADDON_DIR" >&2
    exit 1
fi

# Get version from argument or parse from bl_info
if [ $# -ge 1 ]; then
    VERSION="$1"
else
    VERSION=$(python3 -c "
import ast, pathlib
src = pathlib.Path('$ADDON_DIR/__init__.py').read_text()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == 'bl_info':
                d = ast.literal_eval(node.value)
                print('.'.join(str(x) for x in d['version']))
")
fi

OUTPUT="$SCRIPT_DIR/blend-ai-v${VERSION}.zip"

echo "Building blend-ai addon v${VERSION}..."

# Create temp dir with addon contents under blend_ai/ name
TMPDIR=$(mktemp -d)
DEST="$TMPDIR/blend_ai"
cp -r "$ADDON_DIR" "$DEST"

# Remove __pycache__ and .pyc
find "$DEST" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$DEST" -name "*.pyc" -delete 2>/dev/null || true

# Create zip from temp dir
cd "$TMPDIR"
rm -f "$OUTPUT"
zip -r "$OUTPUT" blend_ai/

# Cleanup
rm -rf "$TMPDIR"

echo "Built: $OUTPUT"
