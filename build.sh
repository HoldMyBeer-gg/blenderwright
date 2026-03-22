#!/usr/bin/env bash
# Build the blend-ai Blender addon zip for distribution.
# Usage: ./build.sh [version]
# Example: ./build.sh 0.2.0
#
# If no version is provided, reads it from addon/__init__.py bl_info.

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

# Create zip with addon/ contents nested under blend_ai/ (Blender expects a folder)
cd "$SCRIPT_DIR"
rm -f "$OUTPUT"
zip -r "$OUTPUT" addon/ \
    -x "addon/__pycache__/*" \
    -x "addon/handlers/__pycache__/*" \
    -x "addon/**/__pycache__/*" \
    -x "*.pyc"

echo "Built: $OUTPUT"
