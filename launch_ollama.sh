#!/usr/bin/env bash
set -e

uv run python -m blend_ai.ollama_chat \
    --model qwen3.5:latest \
    --vision-model qwen3.5:latest \
    --ollama-host http://mbpc:11434 

