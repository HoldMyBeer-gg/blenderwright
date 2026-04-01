"""Interactive Ollama chat client for controlling Blender via blend-ai."""

import asyncio
import base64
import json
import re
import sys
from typing import Any

try:
    import ollama
    from ollama import Client as OllamaClient
except ImportError:
    ollama = None
    OllamaClient = None

from blend_ai.connection import BlenderConnectionError
from blend_ai.tool_registry import get_ollama_tools

# Supported image formats for the !image REPL command
SUPPORTED_IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# Default models
DEFAULT_CHAT_MODEL = "qwen2.5-coder:14b"
DEFAULT_VISION_MODEL = "llava-llama3:latest"

# Max tool-call loop iterations to prevent infinite retries
MAX_TOOL_ROUNDS = 25

# Base system prompt — tool list is appended dynamically in initialize()
SYSTEM_PROMPT_BASE = """You are an expert Blender 3D artist and technical director. You control \
Blender through tool calls.

IMPORTANT: You must ONLY use tools from the list below. Do NOT invent tool names.

Guidelines:
- Always get_scene_info first to understand the current state before making changes.
- Use get_viewport_screenshot to visually check your work after significant changes.
- To delete an object, use delete_object with the "name" parameter.
- To move/rotate/scale objects, use set_location, set_rotation, set_scale.
- To create objects, use create_object with "type" (CUBE, SPHERE, etc).
- Apply professional 3D practices: proper topology, edge flow, material setup.
- Name objects descriptively. Keep scenes organized with collections.
- When the user describes something to create, break it into logical steps.
- Explain what you're doing briefly, then execute with tool calls.

Modeling strategy — what actually works with available tools:
- Organic/anatomical (bodies, creatures, faces): build from multiple positioned primitives \
(UV_SPHERE for rounded forms, CYLINDER for shafts). Scale and position each part, then \
join_objects to merge. Add Subdivision modifier (levels 2-3) and set_smooth_shading for \
smooth results. Do NOT use sculpt mode — no stroke tools are available.
- Hard-surface (mechanical, weapons, props): CUBE with add_loop_cut and extrude_faces. \
Use bevel_edges for chamfers. Mirror modifier for symmetric objects.
- Layered organic forms: overlap multiple UV_SPHEREs at different scales and positions \
to approximate organic volume, then join. Subdivision smooths the joins.
- DO NOT use boolean_operation for organic shapes — unreliable without perfectly clean \
manifold meshes. Prefer join_objects + smooth shading instead.
- DO NOT enter sculpt mode — there are no brush stroke tools. It is a dead end.

Always plan before acting:
1. State your approach: what primitives, how many, how positioned, what modifiers.
2. Then execute step by step with tool calls.
3. After major changes, use get_viewport_screenshot to verify visually.
"""


def parse_image_command(user_input: str) -> tuple[str, str] | None:
    """Parse a !image command from user input.

    Args:
        user_input: Raw user input string.

    Returns:
        Tuple of (image_path, message) or None if not an image command.
    """
    if not user_input.startswith("!image "):
        return None
    remainder = user_input[len("!image "):].strip()
    if not remainder:
        return None
    parts = remainder.split(None, 1)
    image_path = parts[0]
    message = parts[1] if len(parts) > 1 else ""
    return (image_path, message)


def load_image_as_base64(image_path: str) -> str:
    """Load an image file and return its base64-encoded string.

    Args:
        image_path: Absolute or relative path to the image file.

    Returns:
        Base64-encoded string of the image bytes.

    Raises:
        ValueError: If the file extension is not in SUPPORTED_IMAGE_FORMATS.
        FileNotFoundError: If the file does not exist.
        OSError: If the file cannot be read.
    """
    import pathlib
    ext = pathlib.Path(image_path).suffix.lower()
    if ext not in SUPPORTED_IMAGE_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_IMAGE_FORMATS))
        raise ValueError(f"Unsupported image format '{ext}'. Supported: {supported}")
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


class BlenderChatSession:
    """Interactive chat session connecting Ollama to Blender."""

    def __init__(
        self,
        chat_model: str = DEFAULT_CHAT_MODEL,
        vision_model: str = DEFAULT_VISION_MODEL,
        host: str = "127.0.0.1",
        port: int = 9876,
        ollama_host: str | None = None,
        think: bool = False,
    ):
        self.chat_model = chat_model
        self.vision_model = vision_model
        self.host = host
        self.port = port
        self.think = think
        self.ollama_client = OllamaClient(host=ollama_host) if ollama_host else OllamaClient()
        self.messages: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []
        self._tool_names: set[str] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def initialize(self) -> None:
        """Connect to Blender and load tool definitions."""
        # Import here to avoid circular imports — server module registers all tools
        from blend_ai.server import mcp

        # Configure and verify Blender connection
        from blend_ai.connection import BlenderConnection
        from blend_ai import server as srv
        srv._connection = BlenderConnection(host=self.host, port=self.port)
        srv._connection.connect()

        self.tools = get_ollama_tools(mcp)
        self._tool_names = {t["function"]["name"] for t in self.tools}

        # Build system prompt with tool listing grouped by module
        tool_list = _build_tool_list(self.tools)
        system_prompt = SYSTEM_PROMPT_BASE + "\nAvailable tools:\n" + tool_list
        self.messages = [{"role": "system", "content": system_prompt}]

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a blend-ai tool through the MCP tool layer.

        Routes through FastMCP's call_tool so we get proper parameter
        validation and correct parameter-to-command mapping.

        Args:
            name: The tool name (as registered with @mcp.tool()).
            arguments: The tool parameters.

        Returns:
            JSON string of the result.
        """
        from blend_ai.server import mcp

        if self._loop is None:
            self._loop = asyncio.new_event_loop()

        try:
            result = self._loop.run_until_complete(mcp.call_tool(name, arguments))
            # call_tool returns list[TextContent] — extract the text
            if result and hasattr(result[0], "text"):
                return result[0].text
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"status": "error", "result": str(e)})

    def analyze_screenshot(self, image_base64: str, context: str = "") -> str:
        """Send a viewport screenshot to the vision model for analysis.

        Args:
            image_base64: Base64-encoded PNG image data.
            context: Optional context about what to look for.

        Returns:
            Vision model's analysis of the image.
        """
        prompt = "Analyze this Blender viewport screenshot. "
        if context:
            prompt += context
        else:
            prompt += (
                "Describe what you see: objects, materials, lighting, composition. "
                "Note any issues with topology, scale, or visual quality."
            )

        response = self.ollama_client.chat(
            model=self.vision_model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [image_base64],
            }],
        )
        return response.message.content

    def chat(self, user_message: str, images: list[str] | None = None) -> str:
        """Send a message and process the full tool-calling loop.

        Args:
            user_message: The user's message.
            images: Optional list of base64-encoded image strings to include.

        Returns:
            The final assistant response text.
        """
        if self.think:
            user_message = f"/think\n{user_message}"
        user_msg: dict[str, Any] = {"role": "user", "content": user_message}
        if images:
            user_msg["images"] = images
        self.messages.append(user_msg)

        chat_kwargs: dict[str, Any] = {
            "model": self.chat_model,
            "messages": self.messages,
            "tools": self.tools,
            "options": {"num_ctx": 32768},
        }

        for _round in range(MAX_TOOL_ROUNDS):
            response = self.ollama_client.chat(**chat_kwargs)

            # Check for native tool calls first
            tool_calls = response.message.tool_calls or []

            # Fallback: parse tool calls from text if model outputs them as text
            if not tool_calls and response.message.content:
                parsed = _parse_text_tool_calls(response.message.content, self._tool_names)
                if parsed:
                    tool_calls = parsed
                    # Strip tool-call markup from the message content before appending
                    clean_content = _strip_tool_markup(response.message.content)
                    self.messages.append({"role": "assistant", "content": clean_content})
                else:
                    self.messages.append(response.message)
                    return response.message.content
            elif not tool_calls:
                self.messages.append(response.message)
                return response.message.content or ""
            else:
                self.messages.append(response.message)

            for tool_call in tool_calls:
                if hasattr(tool_call, "function"):
                    tool_name = tool_call.function.name
                    tool_args = tool_call.function.arguments
                else:
                    tool_name = tool_call["name"]
                    tool_args = tool_call.get("arguments", {})

                # Check if tool exists — if not, give model corrective feedback
                if tool_name not in self._tool_names:
                    similar = _find_similar_tools(tool_name, self._tool_names)
                    hint = f"Tool '{tool_name}' does not exist."
                    if similar:
                        hint += f" Similar tools: {', '.join(similar)}."
                    hint += " Use get_scene_info to see available objects first."
                    print(f"  [!] {hint}")
                    self.messages.append({
                        "role": "tool",
                        "content": hint,
                    })
                    continue

                print(f"  -> {tool_name}({_format_args(tool_args)})")

                result = self.execute_tool(tool_name, tool_args)

                # If tool errored, still feed it back so the model can recover
                if result.startswith('{"status": "error"'):
                    print(f"  [!] Error: {result}")

                # If this was a screenshot, auto-analyze with vision model
                vision_note = ""
                if tool_name in ("get_viewport_screenshot", "fast_viewport_capture"):
                    try:
                        result_data = json.loads(result)
                        if isinstance(result_data, dict) and "image" in result_data:
                            print("  -> Analyzing screenshot with vision model...")
                            analysis = self.analyze_screenshot(result_data["image"])
                            vision_note = f"\n\n[Vision Analysis]: {analysis}"
                    except (json.JSONDecodeError, KeyError):
                        pass

                if vision_note:
                    try:
                        result_obj = json.loads(result)
                        result_obj["vision_analysis"] = analysis
                        tool_content = json.dumps(result_obj)
                    except (json.JSONDecodeError, TypeError):
                        tool_content = result + vision_note
                else:
                    tool_content = result
                self.messages.append({
                    "role": "tool",
                    "content": tool_content,
                })

        return "(Reached maximum tool-calling rounds. Please try a simpler request.)"

    def _handle_image_command(self, image_path: str, message: str) -> str:
        """Handle a !image command by routing through the vision model first.

        Sends the image to the vision model for analysis, then passes the
        resulting text description to the chat model. This avoids sending
        raw image bytes to non-vision chat models (which causes HTTP 500).

        Args:
            image_path: Path to the image file (already validated).
            message: User's instruction about what to do with the image.

        Returns:
            The final assistant response text.
        """
        image_data = load_image_as_base64(image_path)
        context = message if message else "Describe this image in detail for use as a 3D modeling reference."
        print("  -> Analyzing image with vision model...")
        description = self.analyze_screenshot(image_data, context=context)
        combined = f"[Reference image analysis]: {description}"
        if message:
            combined += f"\n\nUser request: {message}"
        return self.chat(combined)

    def close(self) -> None:
        """Disconnect from Blender."""
        from blend_ai import server as srv
        if srv._connection:
            srv._connection.disconnect()
        if self._loop is not None:
            self._loop.close()
            self._loop = None


def _parse_text_tool_calls(text: str, known_tools: set[str]) -> list[dict[str, Any]]:
    """Parse tool calls from model text output when native tool-calling isn't used.

    Handles formats like:
    - <function=name><parameter=key>value</parameter></function>
    - {"name": "tool", "arguments": {...}}

    Args:
        text: The model's text output.
        known_tools: Set of valid tool names.

    Returns:
        List of parsed tool call dicts, or empty list if none found.
    """
    calls = []

    # Pattern 1: XML-style <function=name>...</function>
    func_pattern = re.compile(
        r'<function=(\w+)>(.*?)</function>', re.DOTALL
    )
    param_pattern = re.compile(
        r'<parameter=(\w+)>\s*(.*?)\s*</parameter>', re.DOTALL
    )

    for match in func_pattern.finditer(text):
        func_name = match.group(1)
        body = match.group(2)
        args = {}
        for param_match in param_pattern.finditer(body):
            key = param_match.group(1)
            value = param_match.group(2).strip()
            try:
                args[key] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                args[key] = value
        # Accept all parsed tool calls — validation happens in the chat loop
        calls.append({"name": func_name, "arguments": args})

    if calls:
        return calls

    # Pattern 2: JSON object with name/arguments — find by scanning for opening brace
    for i, ch in enumerate(text):
        if ch != '{':
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
            if depth == 0:
                candidate = text[i:j + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
                        calls.append({
                            "name": obj["name"],
                            "arguments": obj.get("arguments", {}),
                        })
                except (json.JSONDecodeError, AttributeError):
                    pass
                break

    return calls


def _build_tool_list(tools: list[dict[str, Any]]) -> str:
    """Build a compact tool listing for the system prompt.

    Args:
        tools: List of Ollama tool definitions.

    Returns:
        Formatted string with tool names and brief descriptions.
    """
    lines = []
    for tool in sorted(tools, key=lambda t: t["function"]["name"]):
        name = tool["function"]["name"]
        desc = tool["function"].get("description", "")
        # Take just the first sentence for brevity
        short_desc = desc.split(".")[0].strip() if desc else ""
        lines.append(f"- {name}: {short_desc}")
    return "\n".join(lines)


def _find_similar_tools(name: str, known_tools: set[str], max_results: int = 5) -> list[str]:
    """Find tools with similar names for corrective suggestions.

    Args:
        name: The unknown tool name.
        known_tools: Set of valid tool names.
        max_results: Maximum suggestions to return.

    Returns:
        List of similar tool names, most relevant first.
    """
    name_words = set(name.lower().split("_"))
    scored = []
    for tool in known_tools:
        tool_words = set(tool.lower().split("_"))
        overlap = len(name_words & tool_words)
        if overlap > 0:
            scored.append((overlap, tool))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [s[1] for s in scored[:max_results]]


def _strip_tool_markup(text: str) -> str:
    """Remove tool-call markup from text, keeping any natural language."""
    # Remove XML-style function calls
    cleaned = re.sub(r'<function=\w+>.*?</function>', '', text, flags=re.DOTALL)
    # Remove opening <tool_call> tags
    cleaned = re.sub(r'<tool_call>', '', cleaned)
    # Remove closing </tool_call> tags
    cleaned = re.sub(r'</tool_call>', '', cleaned)
    return cleaned.strip() or ""


def _format_args(args: dict[str, Any]) -> str:
    """Format tool arguments for display, truncating long values."""
    parts = []
    for k, v in args.items():
        s = repr(v)
        if len(s) > 50:
            s = s[:47] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)


def main():
    """Run the interactive Ollama chat client for Blender."""
    if ollama is None:
        print("Error: 'ollama' package is not installed.")
        print("Install it with: uv pip install ollama")
        sys.exit(1)

    import argparse

    parser = argparse.ArgumentParser(
        description="Interactive Ollama chat client for Blender",
        prog="blend-ai-chat",
    )
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_CHAT_MODEL,
        help=f"Ollama chat model (default: {DEFAULT_CHAT_MODEL})",
    )
    parser.add_argument(
        "--vision-model", "-v",
        default=DEFAULT_VISION_MODEL,
        help=f"Ollama vision model for screenshots (default: {DEFAULT_VISION_MODEL})",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Blender addon host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=9876,
        help="Blender addon port (default: 9876)",
    )
    parser.add_argument(
        "--ollama-host",
        default=None,
        help="Ollama API host URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--think",
        action="store_true",
        default=False,
        help="Enable thinking mode (chain-of-thought reasoning before tool calls)",
    )
    args = parser.parse_args()

    session = BlenderChatSession(
        chat_model=args.model,
        vision_model=args.vision_model,
        host=args.host,
        port=args.port,
        ollama_host=args.ollama_host,
        think=args.think,
    )

    ollama_display = args.ollama_host or "localhost:11434"
    think_display = " | think: on" if args.think else ""
    print(f"blend-ai chat | model: {args.model} | vision: {args.vision_model}{think_display}")
    print(f"Ollama: {ollama_display}")
    print(f"Connecting to Blender at {args.host}:{args.port}...")

    try:
        session.initialize()
        print("Connected. Type 'quit' to exit.\n")
    except BlenderConnectionError as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                break

            parsed_img = parse_image_command(user_input)
            if parsed_img is not None:
                image_path, message = parsed_img
                try:
                    response = session._handle_image_command(image_path, message)
                    print(f"\nAssistant: {response}\n")
                except FileNotFoundError:
                    print(f"Error: Image file not found: {image_path}")
                except ValueError as e:
                    print(f"Error: {e}")
                except OSError as e:
                    print(f"Error reading image: {e}")
                continue

            try:
                response = session.chat(user_input)
                print(f"\nAssistant: {response}\n")
            except Exception as e:
                print(f"\nError: {e}\n")
    except KeyboardInterrupt:
        print("\n")
    finally:
        session.close()
        print("Disconnected from Blender.")


if __name__ == "__main__":
    main()
