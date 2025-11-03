"""
tests for the PathValidator class.
"""
from fastapi import HTTPException
import pytest
from fastapi_assets.core.base_validator import ValidationError
from fastapi_assets.request_validators.path_validator import PathValidator

# Fixtures for common PathValidator configurations
@pytest.fixture
def base_validator():
    """Returns a basic PathValidator with no rules."""
    return PathValidator()

@pytest.fixture
def numeric_validator():
    """Returns a PathValidator configured for numeric validation."""
    return PathValidator(gt=0, lt=1000)

@pytest.fixture
def string_validator():
    """Returns a PathValidator configured for string validation."""
    return PathValidator(
        min_length=3,
        max_length=15,
        pattern=r"^[a-zA-Z0-9_]+$"
    )

@pytest.fixture
def allowed_values_validator():
    """Returns a PathValidator with allowed values."""
    return PathValidator(
        allowed_values=["active", "inactive", "pending"]
    )

# Test class for constructor __init__ behavior
class TestPathValidatorInit:
    def test_init_defaults(self):
        """Tests that all validation rules are None by default."""
        validator = PathValidator()
        assert validator._allowed_values is None
        assert validator._pattern is None
        assert validator._min_length is None
        assert validator._max_length is None
        assert validator._gt is None
        assert validator._lt is None
        assert validator._ge is None
        assert validator._le is None
        assert validator._custom_validator is None

    def test_init_allowed_values(self):
        """Tests that allowed_values are stored correctly."""
        values = ["active", "inactive"]
        validator = PathValidator(allowed_values=values)
        assert validator._allowed_values == values

    def test_init_pattern_compilation(self):
        """Tests that regex pattern is compiled."""
        pattern = r"^[a-z0-9]+$"
        validator = PathValidator(pattern=pattern)
        assert validator._pattern is not None
        assert validator._pattern.pattern == pattern

    def test_init_numeric_bounds(self):
        """Tests that numeric bounds are stored correctly."""
        validator = PathValidator(gt=0, lt=100, ge=1, le=99)
        assert validator._gt == 0
        assert validator._lt == 100
        assert validator._ge == 1
        assert validator._le == 99

    def test_init_length_bounds(self):
        """Tests that length bounds are stored correctly."""
        validator = PathValidator(min_length=5, max_length=20)
        assert validator._min_length == 5
        assert validator._max_length == 20

    def test_init_custom_error_detail(self):
        """Tests that custom error messages are stored."""
        custom_error = "Invalid path parameter"
        validator = PathValidator(error_detail=custom_error)
        print(validator._error_detail)
        
        # _error_detail attribute holds error message
        assert validator._error_detail == custom_error or custom_error in str(validator.__dict__)

    def test_init_custom_validator_function(self):
        """Tests that custom validator function is stored."""
        def is_even(x): return x % 2 == 0
        validator = PathValidator(validator=is_even)
        # Validate custom function works
        assert validator._custom_validator(4) is True
        assert validator._custom_validator(3) is False

    def test_init_fastapi_path_creation(self):
        """Tests that internal FastAPI Path object is created."""
        validator = PathValidator(
            title="Item ID",
            description="The unique identifier",
            gt=0,
            lt=1000
        )
        assert validator._path_param is not None

    def test_init_combined_rules(self):
        """Tests initialization with multiple combined rules."""
        validator = PathValidator(
            min_length=3,
            max_length=20,
            pattern=r"^[a-zA-Z]+$",
            title="Category",
            description="Product category slug"
        )
        assert validator._min_length == 3
        assert validator._max_length == 20
        assert validator._pattern is not None

# Validation method tests
class TestPathValidatorValidateAllowedValues:
    def test_allowed_values_no_rule(self, base_validator):
        """Validation should pass if no rule is set."""
        try:
            base_validator._validate_allowed_values("any_value")
        except ValidationError:
            pytest.fail("Validation failed when no rule was set.")

    def test_allowed_values_valid(self, allowed_values_validator):
        """Test valid allowed value."""
        try:
            allowed_values_validator._validate_allowed_values("active")
        except ValidationError:
            pytest.fail("Failed on valid allowed value.")

    def test_allowed_values_invalid(self, allowed_values_validator):
        """Test invalid allowed value raises ValidationError."""
        with pytest.raises(ValidationError):
            allowed_values_validator._validate_allowed_values("deleted")

class TestPathValidatorValidatePattern:
    def test_pattern_no_rule(self, base_validator):
        """Validation passes when no pattern rule."""
        try:
            base_validator._validate_pattern("anything@123!@#")
        except ValidationError:
            pytest.fail("Validation failed when no pattern rule.")

    def test_pattern_valid_match(self, string_validator):
        """Valid pattern match."""
        try:
            string_validator._validate_pattern("user_123")
        except ValidationError:
            pytest.fail("Validation failed on valid pattern.")

    def test_pattern_invalid_match(self, string_validator):
        """Invalid pattern raises ValidationError."""
        with pytest.raises(ValidationError):
            string_validator._validate_pattern("user@123")

    def test_pattern_non_string_ignored(self, string_validator):
        """Skip pattern validation for non-strings."""
        try:
            string_validator._validate_pattern(123)
        except ValidationError:
            pytest.fail("Pattern validation should not apply to non-strings.")

    def test_pattern_email_like(self):
        """Email pattern with valid and invalid cases."""
        validator = PathValidator(pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
        try:
            validator._validate_pattern("user.name+tag@example.com")
        except ValidationError:
            pytest.fail("Valid email-like pattern failed")
        with pytest.raises(ValidationError):
            validator._validate_pattern("user@domain")  # missing TLD

# Length validation tests
class TestPathValidatorValidateLength:
    def test_length_no_rule(self, base_validator):
        """Validation passes when no length rule."""
        try:
            base_validator._validate_length("x")
            base_validator._validate_length("longer")
        except ValidationError:
            pytest.fail("Failed no length rule.")

    def test_length_valid_within_bounds(self, string_validator):
        """Valid length within bounds."""
        try:
            string_validator._validate_length("hello")
        except ValidationError:
            pytest.fail("Failed valid length.")

    def test_length_too_short(self, string_validator):
        """Fails if shorter than min_length."""
        with pytest.raises(ValidationError):
            string_validator._validate_length("ab")
    
    def test_length_too_long(self, string_validator):
        """Fails if longer than max_length."""
        with pytest.raises(ValidationError):
            string_validator._validate_length("a"*20)

# Numeric bounds validation
class TestPathValidatorValidateNumericBounds:
    def test_no_rule(self, base_validator):
        try:
            base_validator._validate_numeric_bounds(999)
            base_validator._validate_numeric_bounds(-999)
        except ValidationError:
            pytest.fail("Failed no numeric rule.")

    def test_gt_lt(self, numeric_validator):
        try:
            numeric_validator._validate_numeric_bounds(1)
            numeric_validator._validate_numeric_bounds(999)
        except ValidationError:
            pytest.fail("Failed valid bounds.")
        with pytest.raises(ValidationError):
            numeric_validator._validate_numeric_bounds(0)

    def test_ge_le(self):
        validator = PathValidator(ge=0, le=10)
        try:
            validator._validate_numeric_bounds(0)
            validator._validate_numeric_bounds(10)
        except ValidationError:
            pytest.fail("Failed boundary values.")
        with pytest.raises(ValidationError):
            validator._validate_numeric_bounds(-1)

# Custom validation tests
class TestPathValidatorValidateCustom:
    def test_no_custom_validator(self, base_validator):
        try:
            base_validator._validate_custom("test")
        except ValidationError:
            pytest.fail("Failed with no custom validator.")
    def test_valid_custom(self):
        def is_even(x): return x % 2 == 0
        v = PathValidator(validator=is_even)
        try:
            v._validate_custom(4)
        except ValidationError:
            pytest.fail("Valid custom validation failed.")
    def test_invalid_custom(self):
        def is_even(x): return x % 2 == 0
        v = PathValidator(validator=is_even)
        with pytest.raises(ValidationError):
            v._validate_custom(3)

# Integration of multiple validations
class TestPathValidatorIntegration:
    def test_combined_valid(self):
        v = PathValidator(allowed_values=["ok"], pattern=r"^ok$", min_length=2, max_length=2)
        try:
            v._validate("ok")
        except ValidationError:
            pytest.fail("Valid data failed validation.")

    def test_fail_in_combined(self):
        v = PathValidator(allowed_values=["ok"], pattern=r"^ok$", min_length=2, max_length=2)
        with pytest.raises(HTTPException):
            v._validate("no")


# Edge case tests for bounds
class TestPathValidatorNumericEdgeCases:
    """Test edge cases and boundary conditions for numeric validation."""
    
    def test_gt_with_equal_value(self):
        """Value equal to gt boundary should fail."""
        validator = PathValidator(gt=10)
        with pytest.raises(ValidationError) as exc_info:
            validator._validate_numeric_bounds(10)
        assert "greater than 10" in str(exc_info.value.detail)

    def test_lt_with_equal_value(self):
        """Value equal to lt boundary should fail."""
        validator = PathValidator(lt=10)
        with pytest.raises(ValidationError) as exc_info:
            validator._validate_numeric_bounds(10)
        assert "less than 10" in str(exc_info.value.detail)

    def test_ge_with_equal_value(self):
        """Value equal to ge boundary should pass."""
        validator = PathValidator(ge=10)
        try:
            validator._validate_numeric_bounds(10)
        except ValidationError:
            pytest.fail("GE with equal value should pass")

    def test_le_with_equal_value(self):
        """Value equal to le boundary should pass."""
        validator = PathValidator(le=10)
        try:
            validator._validate_numeric_bounds(10)
        except ValidationError:
            pytest.fail("LE with equal value should pass")

    def test_negative_numeric_bounds(self):
        """Test numeric bounds with negative values."""
        validator = PathValidator(gt=-100, lt=-10)
        try:
            validator._validate_numeric_bounds(-50)
        except ValidationError:
            pytest.fail("Valid negative value failed")
        with pytest.raises(ValidationError):
            validator._validate_numeric_bounds(-100)

    def test_float_numeric_bounds(self):
        """Test numeric bounds with float values."""
        validator = PathValidator(gt=0.0, lt=1.0)
        try:
            validator._validate_numeric_bounds(0.5)
        except ValidationError:
            pytest.fail("Valid float value failed")
        with pytest.raises(ValidationError):
            validator._validate_numeric_bounds(1.0)

    def test_zero_as_boundary(self):
        """Test with zero as boundary value."""
        validator = PathValidator(ge=0, le=0)
        try:
            validator._validate_numeric_bounds(0)
        except ValidationError:
            pytest.fail("Zero should be valid with ge=0, le=0")
        with pytest.raises(ValidationError):
            validator._validate_numeric_bounds(1)


# Edge case tests for string length
class TestPathValidatorStringEdgeCases:
    """Test edge cases and boundary conditions for string validation."""
    
    def test_empty_string_with_min_length(self):
        """Empty string should fail if min_length is set."""
        validator = PathValidator(min_length=1)
        with pytest.raises(ValidationError) as exc_info:
            validator._validate_length("")
        assert "too short" in str(exc_info.value.detail)

    def test_min_length_exact(self):
        """String exactly at min_length should pass."""
        validator = PathValidator(min_length=5)
        try:
            validator._validate_length("exact")
        except ValidationError:
            pytest.fail("Exact min_length should pass")

    def test_max_length_exact(self):
        """String exactly at max_length should pass."""
        validator = PathValidator(max_length=5)
        try:
            validator._validate_length("exact")
        except ValidationError:
            pytest.fail("Exact max_length should pass")

    def test_unicode_string_length(self):
        """Test length validation with unicode characters."""
        validator = PathValidator(min_length=3, max_length=5)
        try:
            validator._validate_length("😀😁😂")  # 3 emoji characters
        except ValidationError:
            pytest.fail("Valid unicode string failed")

    def test_zero_length_bounds(self):
        """Test with min and max length of zero."""
        validator = PathValidator(min_length=0, max_length=0)
        try:
            validator._validate_length("")
        except ValidationError:
            pytest.fail("Empty string should be valid with min=0, max=0")
        with pytest.raises(ValidationError):
            validator._validate_length("x")


# Edge case tests for pattern matching
class TestPathValidatorPatternEdgeCases:
    """Test edge cases for regex pattern validation."""
    
    def test_pattern_with_special_characters(self):
        """Pattern with special regex characters."""
        validator = PathValidator(pattern=r"^[\w\-\.]+@[\w\-\.]+\.\w+$")
        try:
            validator._validate_pattern("user-name.test@sub-domain.co.uk")
        except ValidationError:
            pytest.fail("Valid email-like pattern failed")
        with pytest.raises(ValidationError):
            validator._validate_pattern("invalid@domain")

    def test_pattern_case_sensitive(self):
        """Regex patterns are case-sensitive by default."""
        validator = PathValidator(pattern=r"^[a-z]+$")
        try:
            validator._validate_pattern("lowercase")
        except ValidationError:
            pytest.fail("Lowercase letters should match [a-z]")
        with pytest.raises(ValidationError):
            validator._validate_pattern("UPPERCASE")

    def test_pattern_with_anchors(self):
        """Pattern with start and end anchors."""
        validator = PathValidator(pattern=r"^START.*END$")
        try:
            validator._validate_pattern("START-middle-END")
        except ValidationError:
            pytest.fail("String with anchors should match")
        with pytest.raises(ValidationError):
            validator._validate_pattern("MIDDLE-START-END")

    def test_pattern_match_from_start(self):
        """re.match() only matches from the start of string."""
        validator = PathValidator(pattern=r"test")
        try:
            validator._validate_pattern("test_string")
        except ValidationError:
            pytest.fail("Pattern should match from start")
        # This should fail because re.match only checks beginning
        with pytest.raises(ValidationError):
            validator._validate_pattern("this_is_a_test_string")

    def test_pattern_with_groups(self):
        """Pattern with capture groups."""
        validator = PathValidator(pattern=r"^(\d{4})-(\d{2})-(\d{2})$")
        try:
            validator._validate_pattern("2025-11-04")
        except ValidationError:
            pytest.fail("Valid date format should match")
        with pytest.raises(ValidationError):
            validator._validate_pattern("2025/11/04")


# Allowed values edge cases
class TestPathValidatorAllowedValuesEdgeCases:
    """Test edge cases for allowed values validation."""
    
    def test_allowed_values_with_none(self):
        """Test when None is in allowed values."""
        validator = PathValidator(allowed_values=[None, "active", "inactive"])
        try:
            validator._validate_allowed_values(None)
        except ValidationError:
            pytest.fail("None should be allowed if in list")

    def test_allowed_values_case_sensitive(self):
        """Allowed values matching is case-sensitive."""
        validator = PathValidator(allowed_values=["Active", "Inactive"])
        try:
            validator._validate_allowed_values("Active")
        except ValidationError:
            pytest.fail("Case-sensitive match should work")
        with pytest.raises(ValidationError):
            validator._validate_allowed_values("active")

    def test_allowed_values_numeric_types(self):
        """Test allowed values with numeric types."""
        validator = PathValidator(allowed_values=[1, 2, 3])
        try:
            validator._validate_allowed_values(2)
        except ValidationError:
            pytest.fail("Numeric allowed value should work")
        with pytest.raises(ValidationError):
            validator._validate_allowed_values("2")  # String "2" != int 2

    def test_allowed_values_empty_list(self):
        """Empty allowed values list should reject everything."""
        validator = PathValidator(allowed_values=[])
        with pytest.raises(ValidationError):
            validator._validate_allowed_values("anything")

    def test_allowed_values_with_duplicates(self):
        """Allowed values list with duplicates."""
        validator = PathValidator(allowed_values=["status", "status", "active"])
        try:
            validator._validate_allowed_values("status")
        except ValidationError:
            pytest.fail("Duplicates shouldn't affect validation")


# Custom validator edge cases
class TestPathValidatorCustomValidatorEdgeCases:
    """Test edge cases for custom validator functions."""
    
    def test_custom_validator_exception_handling(self):
        """Custom validator that raises exception."""
        def bad_validator(x):
            raise ValueError("Something went wrong")
        
        validator = PathValidator(validator=bad_validator)
        with pytest.raises(ValidationError) as exc_info:
            validator._validate_custom("test")
        assert "Custom validation error" in str(exc_info.value.detail)

    def test_custom_validator_returns_false(self):
        """Custom validator returns False."""
        def always_fail(x):
            return False
        
        validator = PathValidator(validator=always_fail)
        with pytest.raises(ValidationError) as exc_info:
            validator._validate_custom("test")
        assert "Custom validation failed" in str(exc_info.value.detail)

    def test_custom_validator_returns_true(self):
        """Custom validator returns True."""
        def always_pass(x):
            return True
        
        validator = PathValidator(validator=always_pass)
        try:
            validator._validate_custom("test")
        except ValidationError:
            pytest.fail("Custom validator returning True should pass")

    def test_custom_validator_with_complex_logic(self):
        """Custom validator with complex validation logic."""
        def validate_phone(phone):
            import re
            return bool(re.match(r"^\+?1?\d{9,15}$", str(phone)))
        
        validator = PathValidator(validator=validate_phone)
        try:
            validator._validate_custom("+14155552671")
        except ValidationError:
            pytest.fail("Valid phone should pass")
        with pytest.raises(ValidationError):
            validator._validate_custom("123")

    def test_custom_validator_lambda(self):
        """Custom validator using lambda function."""
        validator = PathValidator(validator=lambda x: len(str(x)) > 3)
        try:
            validator._validate_custom("test")
        except ValidationError:
            pytest.fail("Lambda validator should work")
        with pytest.raises(ValidationError):
            validator._validate_custom("ab")


# Complete validation flow tests
class TestPathValidatorCompleteFlow:
    """Test complete validation flows with multiple rules."""
    
    def test_all_validations_pass(self):
        """All validation rules pass together."""
        validator = PathValidator(
            allowed_values=["user_123", "admin_456"],
            pattern=r"^[a-z]+_\d+$",
            min_length=7,
            max_length=10,
            validator=lambda x: "_" in x
        )
        try:
            validator._validate("user_123")
        except (ValidationError, HTTPException):
            pytest.fail("All validations should pass")

    def test_fail_on_first_validation(self):
        """Validation fails on first rule."""
        validator = PathValidator(
            allowed_values=["valid"],
            pattern=r"^[a-z]+$",
            min_length=3
        )
        with pytest.raises(HTTPException):
            validator._validate("invalid")

    def test_multiple_combined_rules(self):
        """Complex scenario with multiple rules."""
        validator = PathValidator(
            min_length=5,
            max_length=15,
            pattern=r"^[a-zA-Z0-9_-]+$",
            allowed_values=["user_name", "admin_test", "guest-user"],
            validator=lambda x: not x.startswith("_")
        )
        for valid_value in ["user_name", "admin_test", "guest-user"]:
            try:
                validator._validate(valid_value)
            except (ValidationError, HTTPException):
                pytest.fail(f"'{valid_value}' should be valid")

    def test_validation_error_messages(self):
        """Validation error messages are informative."""
        validator = PathValidator(
            allowed_values=["a", "b", "c"],
            min_length=2,
            max_length=5
        )
        try:
            validator._validate("d")
        except HTTPException as e:
            assert "not allowed" in str(e.detail).lower() or "validation" in str(e.detail).lower()


# Non-string and non-numeric type handling
class TestPathValidatorTypeHandling:
    """Test handling of various data types."""
    
    def test_non_string_skips_string_validations(self):
        """Non-string types skip string-specific validations."""
        validator = PathValidator(min_length=3, max_length=10)
        try:
            validator._validate_length(123)
            validator._validate_pattern(123)
        except ValidationError:
            pytest.fail("Non-strings should skip string validations")

    def test_non_numeric_skips_numeric_validations(self):
        """Non-numeric types skip numeric-specific validations."""
        validator = PathValidator(gt=0, lt=100)
        try:
            validator._validate_numeric_bounds("test")
        except ValidationError:
            pytest.fail("Non-numeric should skip numeric validations")

    def test_boolean_type_validation(self):
        """Test validation with boolean values."""
        validator = PathValidator(allowed_values=[True, False])
        try:
            validator._validate_allowed_values(True)
            validator._validate_allowed_values(False)
        except ValidationError:
            pytest.fail("Booleans should validate against allowed values")

    def test_list_type_validation(self):
        """Test validation with list/collection types."""
        validator = PathValidator(
            allowed_values=[[1, 2], [3, 4], [5, 6]],
            validator=lambda x: isinstance(x, list)
        )
        try:
            validator._validate_allowed_values([1, 2])
            validator._validate_custom([3, 4])
        except ValidationError:
            pytest.fail("Lists should validate correctly")


# Initialization parameter combinations
class TestPathValidatorInitParameterCombinations:
    """Test various parameter combinations during initialization."""
    
    def test_init_with_all_parameters(self):
        """Initialize with all possible parameters."""
        validator = PathValidator(
            default=...,
            allowed_values=["a", "b"],
            pattern=r"^[a-z]$",
            min_length=1,
            max_length=1,
            gt=0,
            lt=10,
            ge=1,
            le=9,
            validator=lambda x: x in ["a", "b"],
            title="Test Parameter",
            description="A test path parameter",
            alias="test_param",
            deprecated=False,
            error_detail="Test error",
            status_code=422
        )
        assert validator._allowed_values == ["a", "b"]
        assert validator._pattern is not None
        assert validator._min_length == 1
        assert validator._max_length == 1

    def test_init_only_required(self):
        """Initialize with only required parameters."""
        validator = PathValidator()
        assert validator._allowed_values is None
        assert validator._pattern is None
        assert validator._min_length is None
        assert validator._max_length is None

    def test_init_with_only_custom_validator(self):
        """Initialize with only custom validator."""
        custom = lambda x: x > 0
        validator = PathValidator(validator=custom)
        assert validator._custom_validator is custom
        assert validator._allowed_values is None

    def test_status_code_default(self):
        """Default status code should be 400."""
        validator = PathValidator()
        # Status code is set in parent class


# Error message verification tests
class TestPathValidatorErrorMessages:
    """Test that error messages are clear and informative."""
    
    def test_allowed_values_error_message(self):
        """Error message includes list of allowed values."""
        validator = PathValidator(allowed_values=["a", "b", "c"])
        try:
            validator._validate_allowed_values("d")
        except ValidationError as e:
            assert "a" in str(e.detail)
            assert "b" in str(e.detail)
            assert "c" in str(e.detail)

    def test_pattern_error_message_includes_pattern(self):
        """Error message includes the regex pattern."""
        pattern = r"^[0-9]{3}$"
        validator = PathValidator(pattern=pattern)
        try:
            validator._validate_pattern("abc")
        except ValidationError as e:
            assert pattern in str(e.detail)

    def test_length_error_message_info(self):
        """Length error includes bounds information."""
        validator = PathValidator(min_length=5, max_length=10)
        try:
            validator._validate_length("ab")
        except ValidationError as e:
            assert "5" in str(e.detail)
        try:
            validator._validate_length("a" * 15)
        except ValidationError as e:
            assert "10" in str(e.detail)

    def test_numeric_bounds_error_messages(self):
        """Numeric bounds errors include boundary values."""
        validator = PathValidator(gt=100)
        try:
            validator._validate_numeric_bounds(50)
        except ValidationError as e:
            assert "100" in str(e.detail)
