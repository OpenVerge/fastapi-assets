"""
Tests for the CookieAssert class.

This file is structured to mirror the patterns in test_file_validator.py.
It tests the __init__, __call__, and individual _validate_* methods.
"""

import pytest
import uuid
from unittest.mock import MagicMock, PropertyMock
from fastapi import HTTPException, Request

# We must import from the package structure
try:
    from fastapi_assets.core.base_validator import ValidationError
    from fastapi_assets.validators.cookie_validator import CookieAssert, PRE_BUILT_PATTERNS
except ImportError:
    # This allows tests to run even if the package isn't "installed"
    # (by adding the parent directory to the path)
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from fastapi_assets.core.base_validator import ValidationError
    from fastapi_assets.validators.cookie_validator import CookieAssert, PRE_BUILT_PATTERNS


@pytest.fixture
def mock_request() -> MagicMock:
    """
    Returns a configurable mock of a FastAPI Request object.
    The most important part is the `cookies` dictionary.
    """
    request = MagicMock(spec=Request)
    
    # Set default cookies. Tests can override this attribute.
    request.cookies = {
        "session-id": "default-session-value-123",
        "user-id": "42"
    }
    return request


# --- Test Cases ---

@pytest.mark.asyncio
class TestCookieAssertInit:
    """Tests for the CookieAssert's __init__ method."""

    def test_init_requires_alias(self):
        """Tests that 'alias' is a required argument."""
        with pytest.raises(TypeError, match="missing 1 required keyword-only argument: 'alias'"):
            CookieAssert()

    def test_init_defaults(self):
        """Tests that all rules are None/default when only alias is provided."""
        validator = CookieAssert(alias="test")
        
        # Validation rules
        assert validator.gt is None
        assert validator.ge is None
        assert validator.lt is None
        assert validator.le is None
        assert validator.min_length is None
        assert validator.max_length is None
        assert validator.final_regex is None
        assert validator.custom_validator is None
        
        # Behavior
        assert validator.default is ...
        assert validator.is_required is True # No default means required
        assert validator.alias == "test"

    def test_init_with_default_sets_not_required(self):
        """Tests that providing a default value correctly sets is_required=False."""
        validator = CookieAssert(alias="test", default=None)
        assert validator.default is None
        assert validator.is_required is False
        
        validator_2 = CookieAssert(alias="test", default="guest")
        assert validator_2.default == "guest"
        assert validator_2.is_required is False

    def test_init_required_overrides_default(self):
        """Tests that required=True makes the cookie required even with a default."""
        validator = CookieAssert(alias="test", default=None, required=True)
        assert validator.default is None
        assert validator.is_required is True

    def test_init_invalid_format_and_regex(self):
        """Tests that using 'format' and 'regex' at the same time fails."""
        with pytest.raises(ValueError, match="Cannot use 'regex'/'pattern' and 'format'"):
            CookieAssert(alias="test", regex=r"abc", format="uuid4")
        
        with pytest.raises(ValueError, match="Cannot use 'regex'/'pattern' and 'format'"):
            CookieAssert(alias="test", pattern=r"abc", format="uuid4")

    def test_init_unknown_format(self):
        """Tests that an invalid 'format' key raises a ValueError."""
        with pytest.raises(ValueError, match="Unknown format: 'not-a-real-format'"):
            CookieAssert(alias="test", format="not-a-real-format")

    def test_init_format_compiles_regex(self):
        """Tests that 'format' correctly loads a pre-built regex pattern."""
        validator = CookieAssert(alias="test", format="uuid4")
        assert validator.final_regex is not None
        assert validator.final_regex.pattern == PRE_BUILT_PATTERNS["uuid4"]

    def test_init_pattern_compiles_regex(self):
        """Tests that 'pattern' (or 'regex') correctly compiles a custom regex."""
        pattern = r"^[a-z]{3}$"
        validator = CookieAssert(alias="test", pattern=pattern)
        assert validator.final_regex is not None
        assert validator.final_regex.pattern == pattern
        
        validator_regex = CookieAssert(alias="test", regex=pattern)
        assert validator_regex.final_regex is not None
        assert validator_regex.final_regex.pattern == pattern

    def test_init_custom_error_details(self):
        """Tests that all custom error detail messages are stored."""
        errors = {
            "on_required_error_detail": "req",
            "on_numeric_error_detail": "num",
            "on_comparison_error_detail": "comp",
            "on_length_error_detail": "len",
            "on_pattern_error_detail": "pat",
            "on_validator_error_detail": "val",
        }
        validator = CookieAssert(alias="test", **errors)
        
        assert validator.err_required == "req"
        assert validator.err_numeric == "num"
        assert validator.err_compare == "comp"
        assert validator.err_length == "len"
        assert validator.err_pattern == "pat"
        assert validator.err_validator == "val"


@pytest.mark.asyncio
class TestCookieAssertCall:
    """Tests the main __call__ entry point, ensuring it raises HTTException."""

    async def test_call_valid_cookie(self, mock_request: MagicMock):
        """Tests the happy path where the cookie is valid and returned."""
        validator = CookieAssert(alias="session-id", min_length=10)
        
        # Mock cookie is "default-session-value-123" which has length > 10
        result = await validator(mock_request)
        
        assert result == "default-session-value-123"

    async def test_call_required_cookie_missing(self, mock_request: MagicMock):
        """Tests that a required cookie missing raises a 400 HTTPException."""
        validator = CookieAssert(alias="missing-cookie", on_required_error_detail="Not found")
        mock_request.cookies = {} # No cookies
        
        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_request)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Not found"

    async def test_call_not_required_cookie_missing(self, mock_request: MagicMock):
        """Tests that an optional cookie missing returns the default value."""
        validator = CookieAssert(alias="missing-cookie", default="guest", required=False)
        mock_request.cookies = {}
        
        result = await validator(mock_request)
        assert result == "guest"

    async def test_call_invalid_numeric(self, mock_request: MagicMock):
        """Tests that a numeric rule on a non-numeric string raises a 400."""
        validator = CookieAssert(alias="user-id", gt=100, on_numeric_error_detail="Not a num")
        mock_request.cookies = {"user-id": "not-a-number"}
        
        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_request)
            
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Not a num"

    async def test_call_invalid_comparison(self, mock_request: MagicMock):
        """Tests that a numeric comparison failure raises a 400."""
        validator = CookieAssert(alias="user-id", gt=100, on_comparison_error_detail="Too small")
        # mock_request has user-id: "42"
        
        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_request)
            
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Too small"

    async def test_call_invalid_length(self, mock_request: MagicMock):
        """Tests that a length failure raises a 400."""
        validator = CookieAssert(alias="user-id", min_length=3, on_length_error_detail="Too short")
        # mock_request has user-id: "42" (length 2)
        
        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_request)
            
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Too short"

    async def test_call_invalid_pattern(self, mock_request: MagicMock):
        """Tests that a regex failure raises a 400."""
        validator = CookieAssert(alias="session-id", format="uuid4", on_pattern_error_detail="Bad format")
        # mock_request has session-id: "default-session-value-123"
        
        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_request)
            
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Bad format"

    async def test_call_invalid_custom_validator(self, mock_request: MagicMock):
        """Tests that a custom validator failure raises a 400."""
        validator = CookieAssert(
            alias="user-id",
            validator=lambda v: v == "admin",
            on_validator_error_detail="Not admin"
        )
        # mock_request has user-id: "42"
        
        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_request)
            
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Not admin"

    async def test_call_no_alias_raises_500(self, mock_request: MagicMock):
        """Tests that an empty/missing alias (misconfiguration) raises a 500."""
        validator = CookieAssert(alias="")
        
        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_request)
            
        assert exc_info.value.status_code == 500
        assert "must be initialized with an `alias`" in exc_info.value.detail

    async def test_call_unexpected_error_raises_500(self, mock_request: MagicMock):
        """Tests that a non-ValidationError is caught and raised as a 500."""
        validator = CookieAssert(alias="session-id")
        
        # Force an unexpected error by making request.cookies raise an exception
        type(mock_request).cookies = PropertyMock(
            side_effect=Exception("Unexpected crash!")
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_request)
            
        assert exc_info.value.status_code == 500
        assert "An unexpected error" in exc_info.value.detail
        

@pytest.mark.asyncio
class TestCookieAssertLogic:
    """
    Unit tests for the individual _validate_* logic methods.
    These test that the methods raise ValidationError correctly.
    """

    def test_numeric_no_rule(self):
        """Tests that no numeric rule set returns None."""
        validator = CookieAssert(alias="test")
        result = validator._validate_numeric("123")
        assert result is None

    def test_numeric_valid_conversion(self):
        """Tests that a valid string is converted to a float."""
        validator = CookieAssert(alias="test", gt=10)
        result = validator._validate_numeric("123.45")
        assert result == 123.45

    def test_numeric_invalid_conversion(self):
        """Tests that a non-numeric string raises ValidationError."""
        validator = CookieAssert(alias="test", gt=10, on_numeric_error_detail="Not num")
        with pytest.raises(ValidationError) as e:
            validator._validate_numeric("abc")
        
        assert e.value.status_code == 400
        assert e.value.detail == "Not num"

    def test_comparison_no_rule(self):
        """Tests that no comparison rules pass."""
        validator = CookieAssert(alias="test")
        try:
            validator._validate_comparison(123)
        except ValidationError:
            pytest.fail("Validation failed when no rule was set")

    def test_comparison_gt_fail(self):
        """Tests 'greater than' failure."""
        validator = CookieAssert(alias="test", gt=100, on_comparison_error_detail="Failed")
        with pytest.raises(ValidationError) as e:
            validator._validate_comparison(100) # 100 is not > 100
        assert e.value.detail == "Failed"
        
    def test_comparison_ge_pass(self):
        """Tests 'greater than or equal' success."""
        validator = CookieAssert(alias="test", ge=100)
        try:
            validator._validate_comparison(100) # 100 is >= 100
        except ValidationError:
            pytest.fail("Validation failed on valid ge comparison")

    def test_comparison_lt_fail(self):
        """Tests 'less than' failure."""
        validator = CookieAssert(alias="test", lt=50, on_comparison_error_detail="Failed")
        with pytest.raises(ValidationError) as e:
            validator._validate_comparison(50.5)
        assert e.value.detail == "Failed"

    def test_comparison_le_pass(self):
        """Tests 'less than or equal' success."""
        validator = CookieAssert(alias="test", le=50)
        try:
            validator._validate_comparison(49.9)
        except ValidationError:
            pytest.fail("Validation failed on valid le comparison")

    def test_length_no_rule(self):
        """Tests that no length rules pass."""
        validator = CookieAssert(alias="test")
        try:
            validator._validate_length("a" * 100)
        except ValidationError:
            pytest.fail("Validation failed when no rule was set")

    def test_length_min_fail(self):
        """Tests 'min_length' failure."""
        validator = CookieAssert(alias="test", min_length=5, on_length_error_detail="Too short")
        with pytest.raises(ValidationError) as e:
            validator._validate_length("1234") # length 4
        assert e.value.detail == "Too short"

    def test_length_max_fail(self):
        """Tests 'max_length' failure."""
        validator = CookieAssert(alias="test", max_length=5, on_length_error_detail="Too long")
        with pytest.raises(ValidationError) as e:
            validator._validate_length("123456") # length 6
        assert e.value.detail == "Too long"

    def test_length_pass(self):
        """Tests valid length success."""
        validator = CookieAssert(alias="test", min_length=3, max_length=5)
        try:
            validator._validate_length("1234")
        except ValidationError:
            pytest.fail("Validation failed on valid length")
            
    def test_pattern_no_rule(self):
        """Tests that no pattern rule passes."""
        validator = CookieAssert(alias="test")
        try:
            validator._validate_pattern("...any-string...")
        except ValidationError:
            pytest.fail("Validation failed when no rule was set")
            
    def test_pattern_fail(self):
        """Tests regex/format failure."""
        validator = CookieAssert(alias="test", format="uuid4", on_pattern_error_detail="Not UUID")
        with pytest.raises(ValidationError) as e:
            validator._validate_pattern("not-a-uuid")
        assert e.value.detail == "Not UUID"

    def test_pattern_pass(self):
        """Tests regex/format success."""
        validator = CookieAssert(alias="test", format="uuid4")
        valid_uuid = str(uuid.uuid4())
        try:
            validator._validate_pattern(valid_uuid)
        except ValidationError:
            pytest.fail("Validation failed on valid UUID")

    def test_custom_no_rule(self):
        """Tests that no custom validator passes."""
        validator = CookieAssert(alias="test")
        try:
            validator._validate_custom("...any-string...")
        except ValidationError:
            pytest.fail("Validation failed when no rule was set")

    def test_custom_fail_return_false(self):
        """Tests that a validator returning False raises an error."""
        validator = CookieAssert(
            alias="test",
            validator=lambda v: False,
            on_validator_error_detail="Returned false"
        )
        with pytest.raises(ValidationError) as e:
            validator._validate_custom("test")
        assert e.value.detail == "Returned false"

    def test_custom_fail_raises_exception(self):
        """Tests that a validator raising an exception is caught."""
        def fail_validator(value):
            raise ValueError("Test crash")
            
        validator = CookieAssert(
            alias="test",
            validator=fail_validator,
            on_validator_error_detail="Validator failed"
        )
        with pytest.raises(ValidationError) as e:
            validator._validate_custom("test")
        
        # The exception message is appended to the detail
        assert "Validator failed: Test crash" in e.value.detail

    def test_custom_pass(self):
        """Tests that a validator returning True passes."""
        validator = CookieAssert(alias="test", validator=lambda v: True)
        try:
            validator._validate_custom("test")
        except ValidationError:
            pytest.fail("Validation failed on valid custom validator")

