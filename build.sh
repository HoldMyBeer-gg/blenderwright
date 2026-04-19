#!/usr/bin/env bash
# Build the blend-ai Blender addon zip for distribution.
# Usage: ./build.sh [version]
# Example: ./build.sh 0.2.0
#
# If no version is provided, reads it from addon/blender_manifest.toml.
# The zip contains a blend_ai/ folder so Blender installs it as the
# "blend_ai" addon module.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADDON_DIR="$SCRIPT_DIR/addon"

if [ ! -d "$ADDON_DIR" ]; then
    echo "Error: addon/ directory not found at $ADDON_DIR" >&2
    exit 1
fi

# Get version from argument or parse from blender_manifest.toml
if [ $# -ge 1 ]; then
    VERSION="$1"
else
    VERSION=$(grep -m1 '^version' "$ADDON_DIR/blender_manifest.toml" | sed 's/.*"\(.*\)"/\1/')
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
