#!/usr/bin/env bash
# Install the blend-ai Blender addon.
# Usage: ./install-addon.sh [path/to/blender]
#
# With no argument, Blender installations are auto-detected and offered
# as a numbered list. No third-party dependencies.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/install_addon.py" install "$@"
