"""
Unit tests for the CookieAssert validator class.

This file is structured to mirror the 'test_file_validator.py' example,
splitting tests by __init__, __call__ (integration), and _validate_* (logic).
"""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from httpx import AsyncClient

# Import the class to test
from fastapi_assets.validators.cookie_validator import CookieAssert

# --- Test Fixtures ---


@pytest_asyncio.fixture(scope="module")
def test_app() -> FastAPI:
    """
    Creates a FastAPI app instance with test endpoints for the validator.
    """
    app = FastAPI()

    # --- Test Endpoints ---

    @app.get("/test-required")
    async def get_required(
        cookie_val: str = CookieAssert(
            alias="session-id",
            required=True,
            on_required_error_detail="Not found",
        ),
    ):
        return {"cookie": cookie_val}

    @app.get("/test-optional-numeric")
    async def get_optional_numeric(
        cookie_val: int = CookieAssert(
            alias="user-id",
            required=False,
            default=0,
            gt=0,
            lt=100,
            on_numeric_error_detail="Not a number",
            on_comparison_error_detail="Out of range",
        ),
    ):
        return {"cookie": cookie_val}

    @app.get("/test-length")
    async def get_length(
        cookie_val: str = CookieAssert(
            alias="auth-token",
            min_length=8,
            max_length=8,
            on_length_error_detail="Length must be 8",
        ),
    ):
        return {"cookie": cookie_val}

    @app.get("/test-pattern")
    async def get_pattern(
        cookie_val: str = CookieAssert(
            alias="promo-code",
            regex=r"^[A-Z]{5}$",
            on_pattern_error_detail="Must be 5 caps",
        ),
    ):
        return {"cookie": cookie_val}

    @app.get("/test-custom-validator")
    async def get_custom(
        cookie_val: str = CookieAssert(
            alias="user-role",
            validator=lambda v: v == "admin",
            on_validator_error_detail="Not admin",
        ),
    ):
        return {"cookie": cookie_val}

    return app


@pytest_asyncio.fixture(scope="module")
async def client(test_app: FastAPI) -> AsyncClient:
    """
    Provides an AsyncClient for making requests to the test_app.
    """
    async with AsyncClient(app=test_app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_request() -> MagicMock:
    """
    Provides a simple MagicMock for the Request object for unit tests.
    """
    request = MagicMock(spec=Request)
    request.cookies = {
        "session-id": "default-session-value-123",
        "user-id": "42",
    }
    return request


# --- Test Cases ---


class TestCookieAssertInit:
    """
    Tests for the CookieAssert's __init__ method.
    """

    def test_init_requires_alias(self):
        """Tests that 'alias' is a required keyword argument."""
        with pytest.raises(TypeError, match="required keyword-only argument: 'alias'"):
            CookieAssert()

    def test_init_defaults(self):
        """Tests that default values are set correctly."""
        validator = CookieAssert(alias="test")
        assert validator.alias == "test"
        assert validator.default is ...
        assert validator.is_required is True
        assert validator.gt is None
        assert validator.min_length is None
        assert validator.final_regex is None

    def test_init_with_default_sets_not_required(self):
        """Tests that providing a default value correctly sets is_required=False."""
        validator = CookieAssert(alias="test", default=None)
        assert validator.default is None
        assert validator.is_required is False

    def test_init_required_overrides_default(self):
        """Tests that required=True overrides a default value."""
        validator = CookieAssert(alias="test", default="abc", required=True)
        assert validator.is_required is True

    def test_init_invalid_format_and_regex(self):
        """Tests that using 'format' and 'regex' together raises a ValueError."""
        with pytest.raises(ValueError, match="Cannot use 'format' and 'regex'"):
            CookieAssert(alias="test", format="uuid4", regex=r"abc")

    def test_init_unknown_format(self):
        """Tests that an unknown format key raises a ValueError."""
        with pytest.raises(ValueError, match="Unknown format 'bad-format'"):
            CookieAssert(alias="test", format="bad-format")

    def test_init_format_compiles_regex(self):
        """Tests that a valid 'format' compiles the correct regex pattern."""
        validator = CookieAssert(alias="test", format="uuid4")
        assert validator.final_regex is not None
        assert (
            validator.final_regex.pattern
            == r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-4[a-fA-F0-9]{3}-[89abAB][a-fA-F0-9]{3}-[a-fA-F0-9]{12}$"
        )

    def test_init_pattern_compiles_regex(self):
        """Tests that a custom 'regex' string is compiled."""
        pattern = r"^[a-z]+$"
        validator = CookieAssert(alias="test", regex=pattern)
        assert validator.final_regex is not None
        assert validator.final_regex.pattern == pattern

    def test_init_custom_error_details(self):
        """Tests that custom error messages are stored correctly."""
        validator = CookieAssert(
            alias="test",
            on_required_error_detail="req",
            on_numeric_error_detail="num",
            on_comparison_error_detail="comp",
            on_length_error_detail="len",
            on_pattern_error_detail="pat",
            on_validator_error_detail="val",
        )
        assert validator.err_required == "req"
        assert validator.err_numeric == "num"
        assert validator.err_comparison == "comp"
        assert validator.err_length == "len"
        assert validator.err_pattern == "pat"
        assert validator.err_validator == "val"


@pytest.mark.asyncio
class TestCookieAssertCall:
    """
    Integration tests for the __call__ method using a live test app.
    These tests check that the correct HTTPException is raised.
    """

    async def test_call_valid_cookie(self, client: AsyncClient):
        """Tests the happy path where the cookie is valid and returned."""
        cookies = {"session-id": "valid-cookie-string"}
        response = await client.get("/test-required", cookies=cookies)
        assert response.status_code == 200
        assert response.json() == {"cookie": "valid-cookie-string"}

    async def test_call_required_cookie_missing(self, client: AsyncClient):
        """Tests that a required cookie missing raises a 400 HTTPException."""
        response = await client.get("/test-required", cookies={})
        assert response.status_code == 400
        assert response.json()["detail"] == "Not found"

    async def test_call_not_required_cookie_missing(self, client: AsyncClient):
        """Tests that an optional cookie missing returns the default value."""
        response = await client.get("/test-optional-numeric", cookies={})
        assert response.status_code == 200
        assert response.json() == {"cookie": 0}  # Returns the default=0

    async def test_call_invalid_numeric(self, client: AsyncClient):
        """Tests that a non-numeric value for a numeric rule fails."""
        cookies = {"user-id": "not-a-number"}
        response = await client.get("/test-optional-numeric", cookies=cookies)
        assert response.status_code == 400
        assert response.json()["detail"] == "Not a number"

    async def test_call_invalid_comparison(self, client: AsyncClient):
        """Tests that a numeric value outside gt/lt bounds fails."""
        cookies = {"user-id": "101"}  # Fails lt=100
        response = await client.get("/test-optional-numeric", cookies=cookies)
        assert response.status_code == 400
        assert response.json()["detail"] == "Out of range"

    async def test_call_invalid_length(self, client: AsyncClient):
        """Tests that a value with incorrect length fails."""
        cookies = {"auth-token": "short"}  # Fails min_length=8
        response = await client.get("/test-length", cookies=cookies)
        assert response.status_code == 400
        assert response.json()["detail"] == "Length must be 8"

    async def test_call_invalid_pattern(self, client: AsyncClient):
        """Tests that a value failing a regex fails."""
        cookies = {"promo-code": "lower"}  # Fails regex=r"^[A-Z]{5}$"
        response = await client.get("/test-pattern", cookies=cookies)
        assert response.status_code == 400
        assert response.json()["detail"] == "Must be 5 caps"

    async def test_call_invalid_custom_validator(self, client: AsyncClient):
        """Tests that a custom validator failure raises a 400."""
        cookies = {"user-role": "user"}  # Fails validator=lambda v: v == "admin"
        response = await client.get("/test-custom-validator", cookies=cookies)
        assert response.status_code == 400
        assert response.json()["detail"] == "Not admin"

    async def test_call_no_alias_raises_500(self, mock_request: MagicMock):
        """Tests that an empty/missing alias (misconfiguration) raises a 500."""
        validator = CookieAssert(alias="")  # Misconfigured

        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_request)

        assert exc_info.value.status_code == 500
        assert "must be initialized with an `alias`" in exc_info.value.detail


@pytest.mark.asyncio
class TestCookieAssertLogic:
    """
    Unit tests for the individual _validate_* logic methods.
    These test that the methods raise ValidationError correctly.
    """

    def test_numeric_valid(self):
        validator = CookieAssert(alias="test", gt=0)
        num_val = validator._validate_numeric("10.5")
        assert num_val == 10.5

    def test_numeric_invalid(self):
        validator = CookieAssert(alias="test", gt=0)
        with pytest.raises(ValidationError) as e:
            validator._validate_numeric("ten")
        assert e.value.detail == "Cookie value must be a valid number."

    def test_numeric_no_rules(self):
        """Tests that no numeric rules means no numeric validation."""
        validator = CookieAssert(alias="test", min_length=1)  # No numeric rules
        num_val = validator._validate_numeric("not-a-number")
        assert num_val is None  # Should not validate or return a float

    def test_comparison_valid(self):
        validator = CookieAssert(alias="test", gt=10, le=20)
        try:
            validator._validate_comparison(15.0)
        except ValidationError:
            pytest.fail("Validation failed on valid comparison")

    def test_comparison_fail_gt(self):
        validator = CookieAssert(alias="test", gt=10)
        with pytest.raises(ValidationError) as e:
            validator._validate_comparison(10.0)  # Fails 'gt=10'
        assert e.value.detail == "Cookie value is not in the allowed range."

    def test_comparison_fail_le(self):
        validator = CookieAssert(alias="test", le=20)
        with pytest.raises(ValidationError) as e:
            validator._validate_comparison(20.1)  # Fails 'le=20'
        assert e.value.detail == "Cookie value is not in the allowed range."

    def test_length_valid(self):
        validator = CookieAssert(alias="test", min_length=2, max_length=5)
        try:
            validator._validate_length("abc")
        except ValidationError:
            pytest.fail("Validation failed on valid length")

    def test_length_fail_min(self):
        validator = CookieAssert(alias="test", min_length=5)
        with pytest.raises(ValidationError) as e:
            validator._validate_length("abc")
        assert e.value.detail == "Cookie value has an invalid length."

    def test_length_fail_max(self):
        validator = CookieAssert(alias="test", max_length=2)
        with pytest.raises(ValidationError) as e:
            validator._validate_length("abc")
        assert e.value.detail == "Cookie value has an invalid length."

    def test_pattern_valid(self):
        validator = CookieAssert(alias="test", format="uuid4")
        try:
            validator._validate_pattern("f47ac10b-58cc-4372-a567-0e02b2c3d479")
        except ValidationError:
            pytest.fail("Validation failed on valid pattern")

    def test_pattern_fail(self):
        validator = CookieAssert(alias="test", format="uuid4")
        with pytest.raises(ValidationError) as e:
            validator._validate_pattern("not-a-uuid")
        assert e.value.detail == "Cookie value has an invalid format."

    def test_custom_validator_pass(self):
        validator = CookieAssert(alias="test", validator=lambda v: "good" in v)
        try:
            validator._validate_custom("this is a good value")
        except ValidationError:
            pytest.fail("Custom validator failed on valid value")

    def test_custom_validator_fail(self):
        validator = CookieAssert(alias="test", validator=lambda v: "good" in v)
        with pytest.raises(ValidationError) as e:
            validator._validate_custom("this is a bad value")
        assert e.value.detail == "Cookie failed custom validation."

    def test_custom_validator_raises_exception(self):
        """Tests that an exception from the user's function is caught."""

        def failing_validator(v):
            if v == "fail":
                raise ValueError("User's function crashed")
            return True

        validator = CookieAssert(alias="test", validator=failing_validator)
        with pytest.raises(ValidationError) as e:
            validator._validate_custom("fail")
        assert "User's function crashed" in e.value.detail

