#!/usr/bin/env bash
set -e

# --extra chat pulls in the ollama package. Without it, `uv run` resolves only
# the default dependencies and will prune ollama from the venv on its next
# sync, which is how this script broke once already.
uv run --extra chat python -m blend_ai.ollama_chat \
    --model qwen3.5:latest \
    --vision-model qwen3.5:latest \
    --ollama-host http://mbpc:11434
