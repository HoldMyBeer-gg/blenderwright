"""Comprehensive tests for blend_ai.validators."""

import pytest
from blend_ai.validators import (
    ValidationError,
    validate_object_name,
    validate_file_path,
    validate_numeric_range,
    validate_color,
    validate_vector,
    validate_enum,
    MAX_OBJECT_NAME_LENGTH,
)


# ---------------------------------------------------------------------------
# validate_object_name
# ---------------------------------------------------------------------------
class TestValidateObjectName:
    def test_valid_simple_name(self):
        assert validate_object_name("Cube") == "Cube"

    def test_valid_name_with_underscore(self):
        assert validate_object_name("my_object") == "my_object"

    def test_valid_name_with_hyphen(self):
        assert validate_object_name("my-object") == "my-object"

    def test_valid_name_with_dot(self):
        assert validate_object_name("Cube.001") == "Cube.001"

    def test_valid_name_with_spaces(self):
        assert validate_object_name("My Cool Object") == "My Cool Object"

    def test_valid_name_with_digits(self):
        assert validate_object_name("Object123") == "Object123"

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            validate_object_name("")

    def test_none_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            validate_object_name(None)

    def test_non_string_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            validate_object_name(42)

    def test_too_long_raises(self):
        long_name = "A" * (MAX_OBJECT_NAME_LENGTH + 1)
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            validate_object_name(long_name)

    def test_max_length_ok(self):
        name = "A" * MAX_OBJECT_NAME_LENGTH
        assert validate_object_name(name) == name

    def test_invalid_chars_raises(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_object_name("Cube@#!")

    def test_slash_raises(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_object_name("path/name")

    def test_whitespace_stripping(self):
        assert validate_object_name("  Cube  ") == "Cube"

    def test_only_whitespace_raises(self):
        # After stripping, empty string fails the pattern check or length
        with pytest.raises(ValidationError):
            validate_object_name("   ")


# ---------------------------------------------------------------------------
# validate_file_path
# ---------------------------------------------------------------------------
class TestValidateFilePath:
    def test_valid_absolute_path(self):
        result = validate_file_path("/tmp/model.fbx")
        assert result.endswith("model.fbx")

    def test_valid_path_with_allowed_extension(self):
        result = validate_file_path(
            "/tmp/scene.glb", allowed_extensions={".glb", ".gltf"}
        )
        assert result.endswith(".glb")

    def test_null_bytes_raise(self):
        # Python's Path.resolve() raises ValueError on null bytes before our check,
        # or our validator raises ValidationError -- either way it must not pass.
        with pytest.raises((ValidationError, ValueError)):
            validate_file_path("/tmp/evil\x00.fbx")

    def test_wrong_extension_raises(self):
        with pytest.raises(ValidationError, match="not allowed"):
            validate_file_path("/tmp/model.exe", allowed_extensions={".fbx", ".obj"})

    def test_must_exist_nonexistent_raises(self):
        with pytest.raises(ValidationError, match="does not exist"):
            validate_file_path(
                "/tmp/nonexistent_blend_ai_test_file_12345.fbx", must_exist=True
            )

    def test_empty_path_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            validate_file_path("")

    def test_none_path_raises(self):
        with pytest.raises(ValidationError, match="non-empty string"):
            validate_file_path(None)

    def test_no_extension_filter(self):
        # When allowed_extensions is None, any extension is fine
        result = validate_file_path("/tmp/anything.xyz")
        assert isinstance(result, str)

    def test_allowed_extensions_case_insensitive(self):
        # Path suffix is lowercased before comparison
        result = validate_file_path(
            "/tmp/model.FBX", allowed_extensions={".fbx"}
        )
        assert result.endswith(".FBX") or result.endswith(".fbx")


# ---------------------------------------------------------------------------
# validate_numeric_range
# ---------------------------------------------------------------------------
class TestValidateNumericRange:
    def test_in_range(self):
        assert validate_numeric_range(5, min_val=0, max_val=10) == 5

    def test_at_min_boundary(self):
        assert validate_numeric_range(0, min_val=0, max_val=10) == 0

    def test_at_max_boundary(self):
        assert validate_numeric_range(10, min_val=0, max_val=10) == 10

    def test_below_min_raises(self):
        with pytest.raises(ValidationError, match="must be >="):
            validate_numeric_range(-1, min_val=0)

    def test_above_max_raises(self):
        with pytest.raises(ValidationError, match="must be <="):
            validate_numeric_range(11, max_val=10)

    def test_float_in_range(self):
        assert validate_numeric_range(0.5, min_val=0.0, max_val=1.0) == 0.5

    def test_non_numeric_raises(self):
        with pytest.raises(ValidationError, match="must be a number"):
            validate_numeric_range("five", min_val=0, max_val=10)

    def test_no_bounds(self):
        assert validate_numeric_range(999999) == 999999

    def test_custom_name_in_error(self):
        with pytest.raises(ValidationError, match="intensity"):
            validate_numeric_range(-1, min_val=0, name="intensity")


# ---------------------------------------------------------------------------
# validate_color
# ---------------------------------------------------------------------------
class TestValidateColor:
    def test_valid_rgb(self):
        assert validate_color([1.0, 0.5, 0.0]) == (1.0, 0.5, 0.0)

    def test_valid_rgba(self):
        assert validate_color([1.0, 0.5, 0.0, 1.0]) == (1.0, 0.5, 0.0, 1.0)

    def test_valid_tuple_input(self):
        assert validate_color((0.0, 0.0, 0.0)) == (0.0, 0.0, 0.0)

    def test_integer_components(self):
        assert validate_color([0, 1, 0]) == (0, 1, 0)

    def test_wrong_length_two(self):
        with pytest.raises(ValidationError, match="3 .RGB. or 4 .RGBA."):
            validate_color([0.5, 0.5])

    def test_wrong_length_five(self):
        with pytest.raises(ValidationError, match="3 .RGB. or 4 .RGBA."):
            validate_color([0.5, 0.5, 0.5, 0.5, 0.5])

    def test_component_too_high(self):
        with pytest.raises(ValidationError, match="between 0.0 and 1.0"):
            validate_color([1.5, 0.0, 0.0])

    def test_component_negative(self):
        with pytest.raises(ValidationError, match="between 0.0 and 1.0"):
            validate_color([-0.1, 0.0, 0.0])

    def test_non_numeric_component(self):
        with pytest.raises(ValidationError, match="between 0.0 and 1.0"):
            validate_color(["red", 0.0, 0.0])

    def test_not_list_or_tuple(self):
        with pytest.raises(ValidationError, match="list or tuple"):
            validate_color("red")

    def test_returns_tuple(self):
        result = validate_color([0.5, 0.5, 0.5])
        assert isinstance(result, tuple)


# ---------------------------------------------------------------------------
# validate_vector
# ---------------------------------------------------------------------------
class TestValidateVector:
    def test_valid_3d(self):
        assert validate_vector([1.0, 2.0, 3.0]) == (1.0, 2.0, 3.0)

    def test_valid_4d_quaternion(self):
        assert validate_vector([1.0, 0.0, 0.0, 0.0], size=4) == (1.0, 0.0, 0.0, 0.0)

    def test_valid_2d(self):
        assert validate_vector([1.0, 2.0], size=2) == (1.0, 2.0)

    def test_wrong_size_raises(self):
        with pytest.raises(ValidationError, match="exactly 3 components"):
            validate_vector([1.0, 2.0])

    def test_wrong_size_4d(self):
        with pytest.raises(ValidationError, match="exactly 4 components"):
            validate_vector([1.0, 2.0, 3.0], size=4)

    def test_non_numeric_component(self):
        with pytest.raises(ValidationError, match="must be a number"):
            validate_vector([1.0, "two", 3.0])

    def test_not_list_or_tuple(self):
        with pytest.raises(ValidationError, match="list or tuple"):
            validate_vector("1,2,3")

    def test_tuple_input(self):
        assert validate_vector((1.0, 2.0, 3.0)) == (1.0, 2.0, 3.0)

    def test_integer_components(self):
        assert validate_vector([1, 2, 3]) == (1, 2, 3)

    def test_custom_name_in_error(self):
        with pytest.raises(ValidationError, match="rotation"):
            validate_vector([1.0, 2.0], name="rotation")

    def test_returns_tuple(self):
        result = validate_vector([0, 0, 0])
        assert isinstance(result, tuple)


# ---------------------------------------------------------------------------
# validate_enum
# ---------------------------------------------------------------------------
class TestValidateEnum:
    def test_valid_value(self):
        allowed = {"MESH", "CURVE", "SURFACE"}
        assert validate_enum("MESH", allowed) == "MESH"

    def test_invalid_value_raises(self):
        allowed = {"MESH", "CURVE", "SURFACE"}
        with pytest.raises(ValidationError, match="must be one of"):
            validate_enum("LIGHT", allowed)

    def test_error_message_shows_value(self):
        allowed = {"A", "B"}
        with pytest.raises(ValidationError, match="got 'C'"):
            validate_enum("C", allowed)

    def test_non_string_raises(self):
        allowed = {"MESH", "CURVE"}
        with pytest.raises(ValidationError, match="must be a string"):
            validate_enum(42, allowed)

    def test_custom_name_in_error(self):
        allowed = {"X"}
        with pytest.raises(ValidationError, match="mode"):
            validate_enum(123, allowed, name="mode")

    def test_case_sensitive(self):
        allowed = {"MESH"}
        with pytest.raises(ValidationError, match="must be one of"):
            validate_enum("mesh", allowed)


class TestValidateScale:
    """A local model asked for scale=[0.15, -0.2, 0] and we said yes.

    Zero collapses the object to zero thickness: a "leaf" came out with
    dimensions 0.5 x 2 x 0. Negative silently mirrors the object and inverts
    its normals, in the same session where the user had asked for a flipped
    normal check. validate_vector only checked type, length and numeric-ness.
    """

    def test_accepts_normal_scale(self):
        from blend_ai.validators import validate_scale
        assert validate_scale([1.0, 2.0, 0.5]) == (1.0, 2.0, 0.5)

    def test_accepts_very_small_positive_scale(self):
        from blend_ai.validators import validate_scale
        assert validate_scale([0.001, 0.001, 0.001]) == (0.001, 0.001, 0.001)

    def test_rejects_zero_component(self):
        from blend_ai.validators import ValidationError, validate_scale
        with pytest.raises(ValidationError) as exc:
            validate_scale([0.15, 0.2, 0])
        assert "zero" in str(exc.value).lower()

    def test_rejects_negative_component(self):
        from blend_ai.validators import ValidationError, validate_scale
        with pytest.raises(ValidationError) as exc:
            validate_scale([0.5, 0.6, -1])
        assert "negative" in str(exc.value).lower()

    def test_negative_error_points_at_the_mirror_modifier(self):
        """Refusing is only helpful if it says what to do instead."""
        from blend_ai.validators import ValidationError, validate_scale
        with pytest.raises(ValidationError) as exc:
            validate_scale([-1, 1, 1])
        assert "mirror" in str(exc.value).lower()

    def test_names_the_offending_axis(self):
        from blend_ai.validators import ValidationError, validate_scale
        with pytest.raises(ValidationError) as exc:
            validate_scale([1, 1, 0])
        assert "component 2" in str(exc.value) or "z" in str(exc.value).lower()

    def test_still_enforces_three_components(self):
        from blend_ai.validators import ValidationError, validate_scale
        with pytest.raises(ValidationError):
            validate_scale([0.3, 0.25])


class TestNumericStringCoercion:
    """Local models send numbers as strings: value='0.55', value='2'.

    The modifier handler already coerces them, with a comment saying LLMs do
    this, but the tool-layer validators rejected them outright, so
    set_material_property(property='roughness', value='0.55') failed with
    "roughness must be a number" and cost a round trip.
    """

    def test_accepts_a_numeric_string(self):
        from blend_ai.validators import validate_numeric_range
        assert validate_numeric_range("0.55", min_val=0.0, max_val=1.0) == 0.55

    def test_accepts_an_integer_string(self):
        from blend_ai.validators import validate_numeric_range
        assert validate_numeric_range("2", min_val=0, max_val=10) == 2.0

    def test_coerced_value_is_still_range_checked(self):
        from blend_ai.validators import ValidationError, validate_numeric_range
        with pytest.raises(ValidationError):
            validate_numeric_range("5.0", min_val=0.0, max_val=1.0)

    def test_rejects_a_non_numeric_string(self):
        from blend_ai.validators import ValidationError, validate_numeric_range
        with pytest.raises(ValidationError) as exc:
            validate_numeric_range("high", min_val=0.0, max_val=1.0)
        assert "number" in str(exc.value).lower()

    def test_rejects_booleans_which_are_technically_ints(self):
        from blend_ai.validators import ValidationError, validate_numeric_range
        with pytest.raises(ValidationError):
            validate_numeric_range(True, min_val=0.0, max_val=1.0)

    def test_plain_numbers_are_unchanged(self):
        from blend_ai.validators import validate_numeric_range
        assert validate_numeric_range(0.5, min_val=0.0, max_val=1.0) == 0.5
        assert validate_numeric_range(3, min_val=0, max_val=10) == 3


class TestOutOfRangeAngleSuggestsRadians:
    """A model sent shade_auto_smooth(angle=30), meaning 30 degrees.

    The error said "angle must be <= 3.14159, got 30.0", which is true and
    tells the caller nothing about why. Every angle in this API is radians,
    and a value that looks like degrees is the common mistake.
    """

    def test_degree_sized_angle_is_told_about_radians(self):
        from blend_ai.validators import ValidationError, validate_numeric_range
        with pytest.raises(ValidationError) as exc:
            validate_numeric_range(30, min_val=0.0, max_val=3.14159, name="angle")
        message = str(exc.value)
        assert "radian" in message.lower()
        assert "0.52" in message, "the converted value should be offered"

    def test_non_angle_parameters_get_no_radian_hint(self):
        from blend_ai.validators import ValidationError, validate_numeric_range
        with pytest.raises(ValidationError) as exc:
            validate_numeric_range(30, min_val=0.0, max_val=1.0, name="roughness")
        assert "radian" not in str(exc.value).lower()

    def test_in_range_angle_is_unaffected(self):
        from blend_ai.validators import validate_numeric_range
        assert validate_numeric_range(0.52, min_val=0.0, max_val=3.14159,
                                      name="angle") == 0.52

    def test_angle_below_range_is_not_given_a_degree_hint(self):
        from blend_ai.validators import ValidationError, validate_numeric_range
        with pytest.raises(ValidationError) as exc:
            validate_numeric_range(-5, min_val=0.0, max_val=3.14159, name="angle")
        assert "radian" not in str(exc.value).lower()


class TestModifierPropertyCaps:
    """MAX_SUBDIVISION_LEVEL and MAX_ARRAY_COUNT were declared and never used.

    set_modifier_property applied no numeric bound at all, so levels=11 on a
    Subdivision modifier or count=100000 on an Array is accepted and hangs
    Blender. The connection then burns its ~5 minute retry budget and dies.
    """

    def test_subdivision_levels_are_capped(self):
        from blend_ai.validators import (MAX_SUBDIVISION_LEVEL, ValidationError,
                                         validate_modifier_property_value)
        with pytest.raises(ValidationError) as exc:
            validate_modifier_property_value("SUBSURF", "levels",
                                             MAX_SUBDIVISION_LEVEL + 1)
        assert str(MAX_SUBDIVISION_LEVEL) in str(exc.value)

    def test_subdivision_at_the_cap_is_allowed(self):
        from blend_ai.validators import (MAX_SUBDIVISION_LEVEL,
                                         validate_modifier_property_value)
        assert validate_modifier_property_value(
            "SUBSURF", "levels", MAX_SUBDIVISION_LEVEL) == MAX_SUBDIVISION_LEVEL

    def test_render_levels_are_capped_too(self):
        from blend_ai.validators import ValidationError, validate_modifier_property_value
        with pytest.raises(ValidationError):
            validate_modifier_property_value("SUBSURF", "render_levels", 12)

    def test_array_count_is_capped(self):
        from blend_ai.validators import (MAX_ARRAY_COUNT, ValidationError,
                                         validate_modifier_property_value)
        with pytest.raises(ValidationError):
            validate_modifier_property_value("ARRAY", "count", MAX_ARRAY_COUNT + 1)

    def test_numeric_strings_are_coerced_here_too(self):
        from blend_ai.validators import validate_modifier_property_value
        assert validate_modifier_property_value("SUBSURF", "levels", "2") == 2

    def test_unbounded_properties_pass_through_untouched(self):
        from blend_ai.validators import validate_modifier_property_value
        assert validate_modifier_property_value("SUBSURF", "use_limit_surface",
                                                True) is True
        assert validate_modifier_property_value("BEVEL", "width", 0.02) == 0.02

    def test_unknown_modifier_type_is_not_blocked(self):
        """Only bound what we know; do not invent limits."""
        from blend_ai.validators import validate_modifier_property_value
        assert validate_modifier_property_value("WEIRD", "levels", 99) == 99
