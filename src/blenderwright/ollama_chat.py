"""Interactive Ollama chat client for controlling Blender via blenderwright."""

import ast
import asyncio
import base64
import json
import math
import re
import sys
from typing import Any

try:
    import ollama
    from ollama import Client as OllamaClient
except ImportError:
    ollama = None
    OllamaClient = None

from blenderwright.connection import BlenderConnectionError
from blenderwright.tool_registry import get_ollama_tools
from blenderwright.toolsets import TOOLSETS, apply_toolsets, enabled_toolsets

# Supported image formats for the !image REPL command
SUPPORTED_IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# Default models
# The 175 tool schemas cost roughly 31,000 tokens on every request, measured
# against qwen3.5 via prompt_eval_count. A 32,768 window therefore leaves under
# 1,700 tokens for up to MAX_TOOL_ROUNDS rounds of calls and their results, so
# work overflowed mid-task and Ollama silently dropped messages. Give the
# conversation real room; models in use here support far larger windows.
DEFAULT_NUM_CTX = 65536

# Below this share of the window left for the conversation, start with the
# core toolsets and let the model enable the rest. Half: a request that
# spends more than half its window on tool schemas has no room to work.
AUTO_THRESHOLD = 0.5

DEFAULT_CHAT_MODEL = "qwen2.5-coder:14b"
DEFAULT_VISION_MODEL = "llava-llama3:latest"

# The real bound on a tool-calling loop is the context window: Ollama reports
# prompt_eval_count and eval_count on every reply, and the loop stops when
# the next request would not fit. This counter is only a backstop against a
# model that loops forever on tiny calls. A shuttle is more than 25 calls.
MAX_TOOL_ROUNDS = 200

# Tokens kept free at the end of the window for the model's final answer.
CONTEXT_RESERVE = 4096

# What the chat model is told when the vision model says nothing. Silence
# used to reach it as an empty string, which it read as approval.
NO_VISION_VERDICT = "(The vision model returned no description of the screenshot.)"

# Tools whose result carries an encoded image, and the keys it arrives under.
SCREENSHOT_TOOLS = frozenset({"get_viewport_screenshot", "capture_viewport"})
IMAGE_KEYS = ("base64", "image")

# Calling one of these twice in a row with the same arguments cannot return
# anything new. A local model will do exactly that, five times, instead of
# building. The repeat is answered from the previous result with a nudge.
READ_ONLY_TOOLS = frozenset({
    "get_scene_info", "list_objects", "get_object_info", "get_selection",
    "list_materials", "list_lights", "list_scenes", "list_keyframes",
    "list_strips", "list_collections", "list_recent_files", "list_toolsets",
    "get_node_tree", "get_color_ramp", "list_procedural_patterns",
    "list_geometry_node_inputs", "analyze_mesh_quality", "analyze_sweep_path",
    "check_3d_printability",
})

# Base system prompt: tool list is appended dynamically in initialize()
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

Choose the primitive that matches the object's silhouette, not its category:
- Round in cross-section (rocket, fuselage, pipe, tank, barrel, column, limb, \
tree trunk): CYLINDER. Taper with CONE. This is the most commonly missed one; \
"mechanical" does not mean "box".
- Boxy in cross-section (crate, building, table, panel, brick): CUBE.
- Rounded or blobby (head, boulder, pod, dome): UV_SPHERE.
- Dish or nozzle shapes (engine bell, funnel, horn): CONE, often scaled and \
flipped.
Ask yourself what the object looks like sliced through the middle, then pick \
the primitive with that cross-section.

Every object is solid and needs all three axes sized. X, Y and Z:
- Before creating anything, state its real width, depth and height.
- A part left at its default depth produces a flat cardboard cutout of the \
object rather than the object. This is the single most common failure. If two \
of the three dimensions are large and one is still the default, it is wrong.
- Cylinders are round: their X and Y should usually match each other, with Z \
as the length.

Parts must actually meet. An assembly is not a pile:
- Stack parts so their surfaces touch or slightly overlap. Compute positions \
from the sizes you chose: a 40m stage sitting on top of a 30m stage is centred \
20m above that stage's centre, not at the same location.
- Two parts at the same location are inside each other, not stacked.
- Engines, fins and greebles attach to the surface of the body, not floating \
beside it. If you name something "left", create a matching "right".

Modeling strategy: what actually works with available tools:
- Organic/anatomical (bodies, creatures, faces): build from multiple positioned \
primitives (UV_SPHERE for rounded forms, CYLINDER for shafts). Scale and \
position each part, then join_objects to merge. Add Subdivision modifier \
(levels 2-3) and set_smooth_shading for smooth results. Do NOT use sculpt mode: \
no stroke tools are available.
- Hard-surface (mechanical, weapons, props): start from the primitive whose \
cross-section matches, then refine with add_loop_cut and extrude_faces. Use \
bevel_edges for chamfers. Mirror modifier for symmetric objects.
- Layered organic forms: overlap multiple UV_SPHEREs at different scales and \
positions to approximate organic volume, then join. Subdivision smooths the \
joins.
- DO NOT use boolean_operation for organic shapes: unreliable without \
perfectly clean manifold meshes. Prefer join_objects + smooth shading instead.
- DO NOT enter sculpt mode: there are no brush stroke tools. It is a dead end.

Always plan before acting:
1. State your approach: which primitive for each part and why that \
cross-section, the width/depth/height of each, and where each sits relative to \
the others.
2. Then execute step by step with tool calls.
3. After major changes, use get_viewport_screenshot to verify visually. Check \
that nothing is flat, nothing floats, and nothing is buried inside another part.
4. Finish the whole request. If asked for several things, a scene, effects, a \
check, do all of them, and say which you could not do rather than stopping.
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
        num_ctx: int = DEFAULT_NUM_CTX,
        toolsets: str | None = None,
    ):
        self.chat_model = chat_model
        self.vision_model = vision_model
        self.host = host
        self.port = port
        self.think = think
        self.num_ctx = num_ctx
        # None means: use BLENDERWRIGHT_TOOLSETS if set, else let the window
        # size decide in initialize().
        self.toolsets = toolsets
        self.toolset_mode = "all"
        if OllamaClient is None:
            raise RuntimeError(
                "The ollama package is required for the chat client. "
                "Install it with: uv pip install -e '.[chat]'"
            )
        self.ollama_client = OllamaClient(host=ollama_host) if ollama_host else OllamaClient()
        self.messages: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []
        self._tool_names: set[str] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def initialize(self) -> None:
        """Connect to Blender and load tool definitions."""
        # Import here to avoid circular imports: server module registers all tools
        from blenderwright.server import mcp

        # Configure and verify Blender connection
        from blenderwright.connection import BlenderConnection
        from blenderwright import server as srv
        srv._connection = BlenderConnection(host=self.host, port=self.port)
        srv._connection.connect()

        import os

        spec = self.toolsets
        if spec is None:
            spec = os.environ.get("BLENDERWRIGHT_TOOLSETS") or None

        # Measure the full set first: that is what the decision is about.
        apply_toolsets(mcp, None)
        full_prompt_tokens = self._estimate_prompt_tokens(get_ollama_tools(mcp))

        if spec is None:
            spec = choose_toolsets(full_prompt_tokens, self.num_ctx)
            if spec == "auto":
                print(f"All tools would cost ~{full_prompt_tokens:,} of "
                      f"{self.num_ctx:,} tokens. Starting in auto mode with the "
                      f"core toolsets; the model enables the rest as it needs "
                      f"them. Pass --toolsets all to load everything.")

        self.toolset_mode = apply_toolsets(mcp, spec).mode
        self._refresh_tools()

        # Roughly four characters per token. Exact enough to show whether the
        # tools have eaten the window before the conversation starts.
        prompt_tokens = self._estimate_prompt_tokens(self.tools)
        headroom = self.num_ctx - prompt_tokens
        print(f"Tools: {len(self.tools)} | prompt ~{prompt_tokens:,} tokens "
              f"of {self.num_ctx:,} | ~{headroom:,} left for the conversation")
        if headroom < prompt_tokens // 2:
            print("  Warning: little room left for tool results. "
                  "Raise --num-ctx if replies stop early.")

    def _estimate_prompt_tokens(self, tools: list[dict[str, Any]]) -> int:
        prompt = self._system_prompt(tools)
        return (len(prompt) + len(json.dumps(tools))) // 4

    def _system_prompt(self, tools: list[dict[str, Any]]) -> str:
        """The base prompt, the tool list, and in auto mode the toolset menu."""
        prompt = SYSTEM_PROMPT_BASE + "\nAvailable tools:\n" + _build_tool_list(tools)
        if self.toolset_mode == "auto":
            prompt += "\n\n" + _build_toolset_menu()
        return prompt

    def _refresh_tools(self) -> None:
        """Re-read the registry into the request tool list and the prompt.

        Called at start and after every enable_toolset, so the next request
        carries the tools the model just asked for.
        """
        from blenderwright.server import mcp

        self.tools = get_ollama_tools(mcp)
        self._tool_names = {t["function"]["name"] for t in self.tools}
        system = {"role": "system", "content": self._system_prompt(self.tools)}
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0] = system
        else:
            self.messages.insert(0, system)

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a blenderwright tool through the MCP tool layer.

        Routes through FastMCP's call_tool so we get proper parameter
        validation and correct parameter-to-command mapping.

        Args:
            name: The tool name (as registered with @mcp.tool()).
            arguments: The tool parameters.

        Returns:
            JSON string of the result.
        """
        from blenderwright.server import mcp

        if self._loop is None:
            self._loop = asyncio.new_event_loop()

        try:
            result = self._loop.run_until_complete(mcp.call_tool(name, arguments))
            # call_tool returns list[TextContent], or (list[TextContent],
            # structured) for a tool with a typed return. Either way the
            # model wants the text, never a repr of the wrapper.
            content = result[0] if isinstance(result, tuple) else result
            if content and hasattr(content[0], "text"):
                return content[0].text
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"status": "error",
                               "result": self._explain_unknown_parameters(name, str(e))})

    def _explain_unknown_parameters(self, name: str, message: str) -> str:
        """Replace pydantic's extra-field error with the tool's real parameters.

        "Extra inputs are not permitted" plus a URL told a model nothing it
        could act on, so it guessed another name and lost another round.
        Naming the parameters that exist ends the guessing.
        """
        unknown = re.findall(r"\n(\w+)\n\s+Extra inputs are not permitted", message)
        missing = re.findall(r"\n(\w+)\n\s+Field required", message)
        if not unknown and not missing:
            return message
        params = []
        for tool in self.tools:
            if tool["function"]["name"] == name:
                params = list(tool["function"]["parameters"].get("properties", {}))
                break
        parts = []
        if unknown:
            parts.append(f"{name} does not accept: {', '.join(unknown)}.")
        if missing:
            parts.append(f"{name} requires: {', '.join(missing)}.")
        if params:
            parts.append(f"Its parameters are: {', '.join(params)}.")
        return " ".join(parts)

    def analyze_screenshot(self, image_base64: str, context: str = "") -> str:
        """Send a viewport screenshot to the vision model for analysis.

        Args:
            image_base64: Base64-encoded PNG image data.
            context: Optional context about what to look for.

        Returns:
            Vision model's analysis of the image.
        """
        prompt = "This is a screenshot of a 3D model in progress in Blender. "
        if context:
            prompt += context + " "
        prompt += (
            "Answer in a few short lines: 1) what objects you see and how they are "
            "arranged; 2) what is wrong: anything floating, flat, buried inside "
            "another part, missing, or off in scale; 3) whether it resembles what "
            "was asked for. Be blunt and specific. Do not praise."
        )

        # think=False: a thinking model spends its whole output budget on
        # thought about the image, hits the length limit, and returns empty
        # content. Measured: 17,000 characters of thinking, zero of answer.
        response = self.ollama_client.chat(
            model=self.vision_model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [image_base64],
            }],
            think=False,
        )
        verdict = (response.message.content or "").strip()
        if not verdict:
            reason = getattr(response, "done_reason", None)
            print(f"  [!] Vision model {self.vision_model} returned no description"
                  f"{f' (done_reason={reason})' if reason else ''}. Try --vision-model "
                  f"with a model that lists 'vision' in `ollama show`.")
            return NO_VISION_VERDICT
        return verdict

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
            "options": {"num_ctx": self.num_ctx},
        }

        # Last tool call and its result, for answering an identical read-only
        # repeat without a round trip. Reset per user message.
        last_call: tuple[str, str] | None = None
        last_result = ""

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

                # Check if tool exists: if not, give model corrective feedback
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

                tool_args = coerce_arguments(tool_name, tool_args, self.tools)
                print(f"  -> {tool_name}({_format_args(tool_args)})")

                call_key = (tool_name, json.dumps(tool_args, sort_keys=True, default=str))
                if tool_name in READ_ONLY_TOOLS and call_key == last_call:
                    print("  [=] unchanged since the previous call; answered from cache")
                    self.messages.append({
                        "role": "tool",
                        "content": json.dumps({
                            "status": "unchanged",
                            "note": f"Identical to your previous {tool_name} call and "
                                    f"nothing has changed since. Do not call it again; "
                                    f"continue with the next step.",
                            "result": _as_json(last_result),
                        }),
                    })
                    continue

                result = self.execute_tool(tool_name, tool_args)
                last_call, last_result = call_key, result

                # If tool errored, still feed it back so the model can recover
                if result.startswith('{"status": "error"'):
                    print(f"  [!] Error: {result}")

                # The model just loaded a toolset: the next request has to
                # carry the new schemas or it cannot call what it asked for.
                if tool_name == "enable_toolset" and not result.startswith('{"status": "error"'):
                    self._refresh_tools()
                    chat_kwargs["tools"] = self.tools

                # A screenshot goes to the vision model, and the chat model
                # gets the words. The encoded PNG must never enter the
                # conversation: it is tens of thousands of tokens the chat
                # model cannot read, and it empties the window in one call.
                tool_content = result
                if tool_name in SCREENSHOT_TOOLS:
                    tool_content = self._describe_screenshot(result)
                self.messages.append({
                    "role": "tool",
                    "content": tool_content,
                })

            # The calls the model just made have run. If their results would
            # not fit in the window, stop here rather than let Ollama drop
            # messages silently.
            if context_exhausted(response, self.num_ctx):
                used = _count(getattr(response, "prompt_eval_count", None))
                note = (f"(Context window is nearly full: ~{used:,} of "
                        f"{self.num_ctx:,} tokens used. The scene is kept. Send a "
                        f"new message to continue from here, or raise --num-ctx.)")
                print(f"  [!] {note}")
                self.messages.append({"role": "assistant", "content": note})
                return note

        return "(Reached maximum tool-calling rounds. Please try a simpler request.)"

    def _describe_screenshot(self, result: str) -> str:
        """Swap the encoded image in a screenshot result for a description.

        Args:
            result: The tool's JSON result. The handlers put the PNG under
                "base64"; "image" is accepted for older builds.

        Returns:
            The result as JSON with the image removed and a "vision_analysis"
            field added, or the result untouched if it carried no image.
        """
        try:
            data = json.loads(result)
        except json.JSONDecodeError:
            return result
        if not isinstance(data, dict):
            return result
        key = next((k for k in IMAGE_KEYS if k in data), None)
        if key is None:
            return result
        encoded = data.pop(key)
        print("  -> Analyzing screenshot with vision model...")
        request = next((m.get("content", "") for m in reversed(self.messages)
                        if m.get("role") == "user"), "")
        context = f"The user asked for: {request.strip()}." if request.strip() else ""
        try:
            data["vision_analysis"] = self.analyze_screenshot(encoded, context)
            excerpt = " ".join(str(data["vision_analysis"]).split())
            print(f"  [vision] {excerpt[:200]}{'...' if len(excerpt) > 200 else ''}")
        except Exception as exc:
            data["vision_analysis"] = f"(vision model unavailable: {exc})"
        return json.dumps(data)

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
        from blenderwright import server as srv
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
        # Accept all parsed tool calls: validation happens in the chat loop
        calls.append({"name": func_name, "arguments": args})

    if calls:
        return calls

    # Pattern 2: JSON object with name/arguments: find by scanning for opening brace
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


def _as_json(text: str) -> Any:
    """A tool result as data when it parses, else as the text it was."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def _count(value: Any) -> int:
    """An Ollama token count, or 0 when the field is missing or not a number."""
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def context_exhausted(response: Any, num_ctx: int) -> bool:
    """True when the reply just received leaves no room for another round.

    Args:
        response: An Ollama chat response. prompt_eval_count is the size of
            everything sent; eval_count is the size of what came back.
        num_ctx: The window the model is running with.

    Returns:
        Whether prompt plus reply already reach into CONTEXT_RESERVE.
    """
    used = _count(getattr(response, "prompt_eval_count", None)) + _count(
        getattr(response, "eval_count", None)
    )
    return used > num_ctx - CONTEXT_RESERVE


_VECTOR_NAMES = {"pi": math.pi, "tau": math.tau, "e": math.e}
_VECTOR_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}


def _eval_number(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id in _VECTOR_NAMES:
        return _VECTOR_NAMES[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _eval_number(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in _VECTOR_OPS:
        return _VECTOR_OPS[type(node.op)](_eval_number(node.left), _eval_number(node.right))
    raise ValueError("not a plain number")


def parse_vector_text(text: str) -> list[float] | None:
    """Read a vector a model wrote as text, arithmetic included.

    rotation='[-3.1416/2,0,0]' is a list with a division in it. Only
    literals, pi/tau/e, unary sign and + - * / are allowed; anything else
    (names, calls, powers, attribute access) returns None.

    Args:
        text: The string the model sent.

    Returns:
        The numbers, or None if the text is not a plain numeric vector.
    """
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except (SyntaxError, ValueError):
        return None
    body = tree.body
    if not isinstance(body, (ast.List, ast.Tuple)):
        return None
    try:
        return [_eval_number(el) for el in body.elts]
    except (ValueError, ZeroDivisionError):
        return None


def coerce_arguments(name: str, args: dict[str, Any], tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn text that should be a vector back into one, per the tool's schema.

    Args:
        name: The tool being called.
        args: The arguments as the model sent them.
        tools: The Ollama tool definitions, for the parameter types.

    Returns:
        The arguments with array-typed parameters parsed from text where
        that parses cleanly. Anything else is left for the validator.
    """
    schema = next((t["function"]["parameters"] for t in tools
                   if t["function"]["name"] == name), None)
    if not schema or not isinstance(args, dict):
        return args
    props = schema.get("properties", {})
    out = dict(args)
    for key, value in args.items():
        if isinstance(value, str) and props.get(key, {}).get("type") == "array":
            parsed = parse_vector_text(value)
            if parsed is not None:
                out[key] = parsed
    return out


def choose_toolsets(prompt_tokens: int, num_ctx: int) -> str:
    """Decide between every tool and the core set from the window size.

    Args:
        prompt_tokens: Estimated cost of the system prompt plus every tool
            schema.
        num_ctx: The context window the model will be run with.

    Returns:
        "all" when the full set leaves at least half the window for the
        conversation, "auto" otherwise.
    """
    if prompt_tokens > num_ctx * AUTO_THRESHOLD:
        return "auto"
    return "all"


def _build_toolset_menu() -> str:
    """The toolsets a model can enable, for the system prompt in auto mode."""
    from blenderwright.server import mcp

    on = enabled_toolsets(mcp)
    lines = [
        "Only the core tools are loaded. More are available in groups. When a "
        "task needs one of these, call enable_toolset with the group name, "
        "then use the tools it lists:",
    ]
    for name in sorted(TOOLSETS):
        if name in on:
            continue
        lines.append(f"- {name}: {TOOLSETS[name]}")
    return "\n".join(lines)


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
        prog="blenderwright-chat",
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
        "--num-ctx",
        type=int,
        default=DEFAULT_NUM_CTX,
        help=f"Ollama context window (default: {DEFAULT_NUM_CTX}); the tool "
             f"schemas alone cost ~31k tokens",
    )
    parser.add_argument(
        "--toolsets",
        default=None,
        help="all, auto, core, or a comma-separated list of toolsets. Default: "
             "all if the window has room, otherwise auto. Overrides "
             "BLENDERWRIGHT_TOOLSETS.",
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
        num_ctx=args.num_ctx,
        toolsets=args.toolsets,
    )

    ollama_display = args.ollama_host or "localhost:11434"
    think_display = " | think: on" if args.think else ""
    print(f"blenderwright chat | model: {args.model} | vision: {args.vision_model}{think_display}")
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
