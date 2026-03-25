# Quick Task 260324-rns Summary

**Task:** Fix !image to route through vision model before chat
**Date:** 2026-03-25
**Commit:** 2efa82a

## Problem

`!image` was passing raw image bytes directly to the chat model via `chat(images=[...])`.
Non-vision models (qwen2.5-coder) return HTTP 500 when sent image data.

## Fix

Added `_handle_image_command(image_path, message)` to `BlenderChatSession`:

1. Loads image → base64
2. Calls `analyze_screenshot(image_data, context=message)` → vision model returns text description
3. Calls `chat(f"[Reference image analysis]: {description}\n\nUser request: {message}")` → text-only to chat model

`main()` REPL now delegates to `_handle_image_command()` instead of calling `chat(images=...)` directly.

## Tests Added

- `TestImageCommandRouting::test_image_command_calls_analyze_screenshot_not_chat_images`
- `TestImageCommandRouting::test_image_command_prepends_vision_description_to_chat`

## Result

57/57 tests pass. No more HTTP 500 on `!image`.
