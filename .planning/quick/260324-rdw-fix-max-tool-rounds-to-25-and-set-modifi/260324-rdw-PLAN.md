---
phase: quick
plan: 260324-rdw
type: execute
wave: 1
depends_on: []
files_modified:
  - src/blend_ai/ollama_chat.py
  - addon/handlers/modeling.py
  - tests/test_ollama_chat.py
  - tests/test_addon/test_handlers/test_modeling_handler.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "MAX_TOOL_ROUNDS constant equals 25"
    - "set_modifier_property coerces string values to the property's native type before setattr"
    - "Bool properties are coerced correctly (not converted to int)"
    - "List/tuple/None current values skip coercion"
    - "Failed coercion falls through to setattr for Blender's own error"
  artifacts:
    - path: "src/blend_ai/ollama_chat.py"
      provides: "MAX_TOOL_ROUNDS = 25"
      contains: "MAX_TOOL_ROUNDS = 25"
    - path: "addon/handlers/modeling.py"
      provides: "Type coercion in handle_set_modifier_property"
      contains: "type(current)(value)"
    - path: "tests/test_ollama_chat.py"
      provides: "Test asserting MAX_TOOL_ROUNDS == 25"
    - path: "tests/test_addon/test_handlers/test_modeling_handler.py"
      provides: "Tests for type coercion in set_modifier_property"
  key_links: []
---

<objective>
Fix two bugs: increase MAX_TOOL_ROUNDS from 10 to 25 for complex Blender tasks, and add type coercion to handle_set_modifier_property so string values from LLMs are cast to the property's native type before setattr.

Purpose: LLMs frequently exceed 10 tool rounds on complex tasks, and they often pass numeric values as strings which causes Blender TypeError.
Output: Updated constants and handler logic with tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/blend_ai/ollama_chat.py
@addon/handlers/modeling.py
@tests/test_ollama_chat.py
@tests/test_tools/test_modeling.py
@tests/test_addon/test_handlers/test_camera_handler.py (reference for handler test pattern)
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write tests, then fix MAX_TOOL_ROUNDS and add type coercion</name>
  <files>
    tests/test_ollama_chat.py
    tests/test_addon/test_handlers/test_modeling_handler.py
    src/blend_ai/ollama_chat.py
    addon/handlers/modeling.py
  </files>
  <behavior>
    - Test: MAX_TOOL_ROUNDS equals 25 (import and assert)
    - Test: handle_set_modifier_property coerces string "3" to int 3 when current property is int
    - Test: handle_set_modifier_property coerces string "2.5" to float 2.5 when current property is float
    - Test: handle_set_modifier_property coerces int 1 to bool True when current property is bool (bool checked before int since bool is subclass of int)
    - Test: handle_set_modifier_property skips coercion when current value is None
    - Test: handle_set_modifier_property skips coercion when current value is a list or tuple
    - Test: handle_set_modifier_property falls through to setattr when coercion fails (e.g., string "abc" for int property)
    - Test: handle_set_modifier_property passes value unchanged when types already match
  </behavior>
  <action>
    **Tests first (RED):**

    1. In `tests/test_ollama_chat.py`, add a test in a new class `TestConstants`:
       ```python
       def test_max_tool_rounds_is_25():
           from blend_ai.ollama_chat import MAX_TOOL_ROUNDS
           assert MAX_TOOL_ROUNDS == 25
       ```

    2. Create `tests/test_addon/test_handlers/test_modeling_handler.py` following the pattern from `test_camera_handler.py`:
       - Use `importlib.util` to load `addon/handlers/modeling.py` with mocked `bpy` and `dispatcher`
       - Mock `bpy.data.objects.get` to return a mock object with a mock modifier
       - Set modifier attributes to simulate current property types (int, float, bool, None, list)
       - Test each coercion case listed in behavior block

    **Implementation (GREEN):**

    3. In `src/blend_ai/ollama_chat.py` line 28: change `MAX_TOOL_ROUNDS = 10` to `MAX_TOOL_ROUNDS = 25`

    4. In `addon/handlers/modeling.py` `handle_set_modifier_property()`, replace the bare `setattr(mod, prop, value)` at line 90 with:
       ```python
       # Coerce value to match the property's current type.
       # LLMs often pass numbers as strings (e.g., "3" for int property).
       current = getattr(mod, prop)
       if current is not None and not isinstance(current, (list, tuple)):
           target_type = type(current)
           # Check bool before int — bool is a subclass of int
           if target_type is bool:
               if isinstance(value, str):
                   value = value.lower() in ("true", "1", "yes")
               else:
                   value = bool(value)
           elif not isinstance(value, target_type):
               try:
                   value = target_type(value)
               except (TypeError, ValueError):
                   pass  # Let setattr raise Blender's own error
       setattr(mod, prop, value)
       ```
  </action>
  <verify>
    <automated>cd /Users/michael/code/blend-ai && python -m pytest tests/test_ollama_chat.py::TestConstants -x && python -m pytest tests/test_addon/test_handlers/test_modeling_handler.py -x</automated>
  </verify>
  <done>
    - MAX_TOOL_ROUNDS == 25 and test passes
    - All type coercion tests pass: string-to-int, string-to-float, int-to-bool, None skip, list skip, failed coercion fallthrough, same-type passthrough
    - Existing tests still pass: `python -m pytest tests/test_ollama_chat.py tests/test_tools/test_modeling.py -x`
  </done>
</task>

</tasks>

<verification>
```bash
cd /Users/michael/code/blend-ai && python -m pytest tests/test_ollama_chat.py tests/test_addon/test_handlers/test_modeling_handler.py tests/test_tools/test_modeling.py -x -v
```
</verification>

<success_criteria>
- MAX_TOOL_ROUNDS constant is 25
- handle_set_modifier_property coerces types correctly for int, float, bool
- Coercion is skipped for None, list, tuple current values
- Failed coercion does not crash — falls through to setattr
- All existing tests continue to pass
</success_criteria>

<output>
After completion, create `.planning/quick/260324-rdw-fix-max-tool-rounds-to-25-and-set-modifi/260324-rdw-SUMMARY.md`
</output>
