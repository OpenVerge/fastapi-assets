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
        validator = PathValidator(on_error_detail=custom_error)
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
