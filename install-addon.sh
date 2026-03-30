#!/usr/bin/env bash
# Install the blend-ai Blender addon via an interactive TUI.
# Usage: ./install-addon.sh [path/to/blender]
#
# Requires: pip install textual

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! python3 -c "import textual" 2>/dev/null; then
    echo "Installing textual..."
    pip install textual
fi

python3 "$SCRIPT_DIR/install_addon.py" "$@"
