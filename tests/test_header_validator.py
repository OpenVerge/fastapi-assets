"""
Tests for the HeaderValidator class.
"""

import pytest
from fastapi import HTTPException
from fastapi_assets.core import ValidationError
from fastapi_assets.request_validators import HeaderValidator


#  Fixtures


@pytest.fixture
def base_validator():
    """Returns a basic HeaderValidator with no rules."""
    return HeaderValidator()


@pytest.fixture
def required_validator():
    """Returns a HeaderValidator with required=True."""
    return HeaderValidator(default="Hello")


@pytest.fixture
def pattern_validator():
    """Returns a HeaderValidator with pattern validation."""
    return HeaderValidator(pattern=r"^[a-zA-Z0-9]{32}$")


@pytest.fixture
def format_validator():
    """Returns a HeaderValidator with bearer_token format."""
    return HeaderValidator(format="bearer_token")


@pytest.fixture
def allowed_values_validator():
    """Returns a HeaderValidator with allowed values."""
    return HeaderValidator(allowed_values=["v1", "v2", "v3"])


@pytest.fixture
def custom_validator_obj():
    """Returns a HeaderValidator with custom validator function."""

    def is_even_length(val: str):
        if len(val) % 2 != 0:
            raise ValidationError(detail="Length is not even")

    return HeaderValidator(validators=[is_even_length])


#  Test Classes


class TestHeaderValidatorInit:
    """Tests for the HeaderValidator's __init__ method."""

    def test_init_defaults(self):
        """Tests that all validation rules are None by default."""
        validator = HeaderValidator()
        assert validator._allowed_values is None
        assert validator._pattern_str is None
        assert validator._custom_validators == []

    def test_init_pattern_compilation(self):
        """Tests that pattern is compiled to regex."""
        pattern = r"^[A-Z0-9]+$"
        validator = HeaderValidator(pattern=pattern)
        assert validator._pattern_str is not None
        assert validator._pattern_str == pattern

    def test_init_invalid_format(self):
        """Tests that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Unknown format"):
            HeaderValidator(format="invalid_format")

    def test_init_pattern_and_format_conflict(self):
        """Tests that both pattern and format cannot be specified."""
        with pytest.raises(ValueError, match="Cannot specify both"):
            HeaderValidator(pattern=r"^test$", format="uuid4")

    def test_init_allowed_values(self):
        """Tests that allowed values are stored correctly."""
        values = ["alpha", "beta", "gamma"]
        validator = HeaderValidator(allowed_values=values)
        assert validator._allowed_values == values

    def test_init_custom_validator_function(self):
        """Tests that custom validator function is stored."""

        def is_positive(val: str):
            if not val.startswith("+"):
                raise ValidationError(detail="Value does not start with '+'")

        validator = HeaderValidator(validators=[is_positive])
        assert validator._custom_validators is not None
        assert validator._custom_validators[0]("+test") is None

    def test_init_custom_error_detail(self):
        """Tests that custom error detail is stored."""
        custom_msg = "Invalid header value"
        validator = HeaderValidator(error_detail=custom_msg)
        assert validator._error_detail == custom_msg

    def test_init_alias(self):
        """Tests that alias for header name is set."""
        validator = HeaderValidator(alias="X-API-Key")
        assert validator._header_param is not None


class TestHeaderValidatorValidateRequired:
    """Tests for the _validate_required method."""

    def test_required_with_value(self, required_validator):
        """Tests required validation passes when value is present."""
        try:
            required_validator._validate_required("some_value")
        except ValidationError:
            pytest.fail("Required validation failed with valid value")


class TestHeaderValidatorValidateAllowedValues:
    """Tests for the _validate_allowed_values method."""

    def test_allowed_values_no_rule(self, base_validator):
        """Tests that no validation happens when no allowed_values rule."""
        try:
            base_validator._validate_allowed_values("any_value")
        except ValidationError:
            pytest.fail("Validation failed with no rule set")

    def test_allowed_values_valid(self, allowed_values_validator):
        """Tests allowed value passes validation."""
        try:
            allowed_values_validator._validate_allowed_values("v1")
        except ValidationError:
            pytest.fail("Valid allowed value failed")

    def test_allowed_values_invalid(self, allowed_values_validator):
        """Tests invalid allowed value raises error."""
        with pytest.raises(ValidationError) as e:
            allowed_values_validator._validate_allowed_values("v4")

        assert e.value.status_code == 400
        assert "not allowed" in e.value.detail.lower()

    def test_allowed_values_all_options(self, allowed_values_validator):
        """Tests all allowed values individually."""
        for value in ["v1", "v2", "v3"]:
            try:
                allowed_values_validator._validate_allowed_values(value)
            except ValidationError:
                pytest.fail(f"Valid allowed value '{value}' failed")

    def test_allowed_values_case_sensitive(self, allowed_values_validator):
        """Tests that allowed values are case-sensitive."""
        with pytest.raises(ValidationError):
            allowed_values_validator._validate_allowed_values("V1")


class TestHeaderValidatorValidatePattern:
    """Tests for the _validate_pattern method."""

    def test_pattern_no_rule(self, base_validator):
        """Tests validation passes with no pattern rule."""
        try:
            base_validator._validate_pattern("anything")
        except ValidationError:
            pytest.fail("Validation failed with no pattern rule")

    def test_pattern_valid_match(self, pattern_validator):
        """Tests pattern matches valid value."""
        try:
            pattern_validator._validate_pattern("abcdefghijklmnopqrstuvwxyz123456")
        except ValidationError:
            pytest.fail("Valid pattern match failed")

    def test_pattern_invalid_match(self, pattern_validator):
        """Tests pattern fails on invalid value."""
        with pytest.raises(ValidationError) as e:
            pattern_validator._validate_pattern("short")

        assert e.value.status_code == 400
        assert "invalid format" in e.value.detail.lower()

    def test_pattern_format_uuid4_valid(self):
        """Tests uuid4 format validation passes."""
        validator = HeaderValidator(format="uuid4")
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        try:
            validator._validate_pattern(valid_uuid)
        except ValidationError:
            pytest.fail("Valid UUID4 failed")

    def test_pattern_format_uuid4_invalid(self):
        """Tests uuid4 format validation fails."""
        validator = HeaderValidator(format="uuid4")
        with pytest.raises(ValidationError) as e:
            validator._validate_pattern("not-a-uuid")

        assert "format" in e.value.detail.lower()

    def test_pattern_format_bearer_token_valid(self, format_validator):
        """Tests bearer token format validation passes."""
        try:
            format_validator._validate_pattern("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        except ValidationError:
            pytest.fail("Valid bearer token failed")

    def test_pattern_format_bearer_token_invalid(self, format_validator):
        """Tests bearer token format validation fails."""
        with pytest.raises(ValidationError):
            format_validator._validate_pattern("InvalidToken")

    def test_pattern_format_email_valid(self):
        """Tests email format validation passes."""
        validator = HeaderValidator(format="email")
        try:
            validator._validate_pattern("user@example.com")
        except ValidationError:
            pytest.fail("Valid email failed")

    def test_pattern_format_email_invalid(self):
        """Tests email format validation fails."""
        validator = HeaderValidator(format="email")
        with pytest.raises(ValidationError):
            validator._validate_pattern("not-an-email")


class TestHeaderValidatorValidateCustom:
    """Tests for the _validate_custom method."""

    @pytest.mark.asyncio
    async def test_custom_no_validator(self, base_validator):
        """Tests validation passes with no custom validator."""
        try:
            await base_validator._validate_custom("any_value")
        except ValidationError:
            pytest.fail("Validation failed with no custom validator")

    @pytest.mark.asyncio
    async def test_custom_validator_valid(self, custom_validator_obj):
        """Tests custom validator passes on valid input."""
        try:
            await custom_validator_obj._validate_custom("even")  # 4 chars
        except ValidationError:
            pytest.fail("Valid custom validation failed")

    @pytest.mark.asyncio
    async def test_custom_validator_invalid(self, custom_validator_obj):
        """Tests custom validator fails on invalid input."""
        with pytest.raises(ValidationError) as e:
            await custom_validator_obj._validate_custom("odd")  # 3 chars

        assert e.value.status_code == 400
        # Accept either failure message depending on your validator code
        # The custom validator raises ValidationError with detail="Length is not even"
        assert (
            "failed custom validation" in e.value.detail.lower()
            or "custom validation error" in e.value.detail.lower()
            or "length is not even" in e.value.detail.lower()
        )

    @pytest.mark.asyncio
    async def test_custom_validator_exception(self):
        """Tests custom validator exception is caught."""

        def buggy_validator(val: str):
            raise ValueError("Unexpected error")

        validator = HeaderValidator(validators=[buggy_validator])
        with pytest.raises(ValidationError) as e:
            await validator._validate_custom("test")

        assert "custom validation failed" in e.value.detail.lower()


class TestHeaderValidatorValidate:
    """Tests for the main _validate method."""

    @pytest.mark.asyncio
    async def test_validate_valid_header(self):
        """Tests full validation pipeline with valid header."""
        validator = HeaderValidator(
            required=True, allowed_values=["api", "web"], pattern=r"^[a-z]+$"
        )
        try:
            result = await validator._validate("api")
            assert result == "api"
        except ValidationError:
            pytest.fail("Valid header failed validation")

    @pytest.mark.asyncio
    async def test_validate_fails_required(self):
        """Tests validation fails on required check."""
        validator = HeaderValidator(required=True)
        with pytest.raises(ValidationError):
            await validator._validate(None)

    @pytest.mark.asyncio
    async def test_validate_fails_allowed_values(self):
        """Tests validation fails on allowed values check."""
        validator = HeaderValidator(allowed_values=["good"])
        with pytest.raises(ValidationError):
            await validator._validate("bad")

    @pytest.mark.asyncio
    async def test_validate_fails_pattern(self):
        """Tests validation fails on pattern check."""
        validator = HeaderValidator(pattern=r"^[0-9]+$")
        with pytest.raises(ValidationError):
            await validator._validate("abc")

    @pytest.mark.asyncio
    async def test_validate_fails_custom(self):
        """Tests validation fails on custom validator."""

        def no_spaces(val: str):
            if " " in val:
                raise ValidationError(detail="Spaces are not allowed")

        validator = HeaderValidator(validators=[no_spaces])
        with pytest.raises(ValidationError):
            await validator._validate("has space")

    @pytest.mark.asyncio
    async def test_validate_empty_optional_header(self):
        """Tests optional header with empty string passes."""
        validator = HeaderValidator(default="")
        result = await validator._validate("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_validate_none_optional_header(self):
        """Tests optional header with None passes."""
        validator = HeaderValidator(default=None)
        result = await validator._validate(None)
        assert result is None
