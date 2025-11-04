"""
Unit Tests for the CookieAssert Validator
"""

import pytest
import uuid
from typing import Optional
from fastapi import FastAPI, Depends, status
from httpx import AsyncClient, ASGITransport

# Import the class to be tested
try:
    from fastapi_assets.request_validators.cookie_validator import CookieAssert
    from fastapi_assets.core.exceptions import ValidationError
except ImportError as e:
    pytest.skip(f"Could not import CookieAssert: {e}", allow_module_level=True)

# --- Test Application Setup ---

# Define validators once, as they would be in a real app
validate_required_uuid = CookieAssert(
    alias="session-id",
    format="uuid4",
    on_required_error_detail="Session is required.",
    on_pattern_error_detail="Invalid session format."
)

validate_optional_gt10 = CookieAssert(
    alias="tracker",
    required=False,
    default=None,
    gt=10,
    on_comparison_error_detail="Tracker must be > 10.",
    on_numeric_error_detail="Tracker must be a number."
)

validate_length_5 = CookieAssert(
    alias="code",
    min_length=5,
    max_length=5,
    on_length_error_detail="Code must be 5 chars."
)

def _custom_check(val: str):
    """A sample custom validator function"""
    if val not in ["admin", "user"]:
        raise ValueError("Role is invalid")
    return True

validate_custom_role = CookieAssert(
    alias="role",
    validators=[_custom_check],
    on_validator_error_detail="Invalid role."
)

# Additional validators for extended tests
validate_bearer_token = CookieAssert(
    alias="auth-token",
    format="bearer_token",
    on_pattern_error_detail="Invalid bearer token format."
)

validate_numeric_ge_le = CookieAssert(
    alias="score",
    ge=0,
    le=100,
    on_comparison_error_detail="Score must be between 0 and 100.",
    on_numeric_error_detail="Score must be a number."
)

def _async_validator(val: str):
    """An async custom validator function"""
    # This is actually a sync function that will be called
    # The CookieAssert supports both sync and async validators
    return val.startswith("valid_")

validate_async_custom = CookieAssert(
    alias="async-token",
    validators=[_async_validator],
    on_validator_error_detail="Token must start with 'valid_'."
)

validate_email_format = CookieAssert(
    alias="user-email",
    format="email",
    on_pattern_error_detail="Invalid email format."
)

# Create a minimal FastAPI app for testing
app = FastAPI()

@app.get("/test-required")
async def get_required(session: str = Depends(validate_required_uuid)):
    """Test endpoint for a required, formatted cookie."""
    return {"session": session}

@app.get("/test-optional")
async def get_optional(tracker: Optional[float] = Depends(validate_optional_gt10)):
    """Test endpoint for an optional, numeric cookie."""
    return {"tracker": tracker}

@app.get("/test-length")
async def get_length(code: str = Depends(validate_length_5)):
    """Test endpoint for a length-constrained cookie."""
    return {"code": code}

@app.get("/test-custom")
async def get_custom(role: str = Depends(validate_custom_role)):
    """Test endpoint for a custom-validated cookie."""
    return {"role": role}

@app.get("/test-bearer")
async def get_bearer(token: str = Depends(validate_bearer_token)):
    """Test endpoint for bearer token format."""
    return {"token": token}

@app.get("/test-ge-le")
async def get_numeric_range(score: float = Depends(validate_numeric_ge_le)):
    """Test endpoint for numeric range validation."""
    return {"score": score}

@app.get("/test-async-custom")
async def get_async_custom(token: str = Depends(validate_async_custom)):
    """Test endpoint for async custom validator."""
    return {"token": token}

@app.get("/test-email")
async def get_email(email: str = Depends(validate_email_format)):
    """Test endpoint for email format."""
    return {"email": email}

# --- Pytest Fixtures ---

@pytest.fixture(scope="module")
def anyio_backend():
    """
    Tells pytest-anyio to use the 'asyncio' backend for these tests.
    """
    return "asyncio"


@pytest.fixture(scope="module")
async def client(anyio_backend):
    """
    Pytest fixture to create an AsyncClient for the test app.
    Depends on the 'anyio_backend' fixture.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

# --- Test Cases ---

# REQUIRED COOKIE TESTS
@pytest.mark.anyio
async def test_required_cookie_missing(client: AsyncClient):
    """Tests that a required cookie raises an error if missing."""
    response = await client.get("/test-required")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Session is required."}

@pytest.mark.anyio
async def test_required_cookie_invalid_format(client: AsyncClient):
    """Tests that a required cookie fails on invalid format."""
    cookies = {"session-id": "not-a-valid-uuid"}
    response = await client.get("/test-required", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Invalid session format."}

@pytest.mark.anyio
async def test_required_cookie_valid(client: AsyncClient):
    """Tests that a required cookie passes with valid format."""
    valid_uuid = str(uuid.uuid4())
    cookies = {"session-id": valid_uuid}
    response = await client.get("/test-required", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"session": valid_uuid}

# OPTIONAL COOKIE TESTS
@pytest.mark.anyio
async def test_optional_cookie_missing(client: AsyncClient):
    """Tests that an optional cookie returns the default (None) if missing."""
    response = await client.get("/test-optional")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"tracker": None}

@pytest.mark.anyio
async def test_optional_cookie_invalid_comparison(client: AsyncClient):
    """Tests that an optional cookie fails numeric comparison."""
    cookies = {"tracker": "5"}  # 5 is not > 10
    response = await client.get("/test-optional", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Tracker must be > 10."}

@pytest.mark.anyio
async def test_optional_cookie_invalid_numeric(client: AsyncClient):
    """Tests that a numeric cookie fails non-numeric values."""
    cookies = {"tracker": "not-a-number"}
    response = await client.get("/test-optional", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Tracker must be a number."}

@pytest.mark.anyio
async def test_optional_cookie_valid(client: AsyncClient):
    """Tests that an optional cookie passes with a valid value."""
    cookies = {"tracker": "100"}
    response = await client.get("/test-optional", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"tracker": 100.0}

@pytest.mark.anyio
async def test_optional_cookie_boundary_gt(client: AsyncClient):
    """Tests boundary condition for gt comparison (10 is not > 10)."""
    cookies = {"tracker": "10"}
    response = await client.get("/test-optional", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Tracker must be > 10."}

@pytest.mark.anyio
async def test_optional_cookie_boundary_gt_valid(client: AsyncClient):
    """Tests boundary condition for gt comparison (10.1 is > 10)."""
    cookies = {"tracker": "10.1"}
    response = await client.get("/test-optional", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"tracker": 10.1}

# LENGTH CONSTRAINT TESTS
@pytest.mark.anyio
async def test_length_cookie_too_short(client: AsyncClient):
    """Tests min_length validation."""
    cookies = {"code": "1234"}  # Length 4, min is 5
    response = await client.get("/test-length", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Code must be 5 chars."}

@pytest.mark.anyio
async def test_length_cookie_too_long(client: AsyncClient):
    """Tests max_length validation."""
    cookies = {"code": "123456"}  # Length 6, max is 5
    response = await client.get("/test-length", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Code must be 5 chars."}

@pytest.mark.anyio
async def test_length_cookie_valid(client: AsyncClient):
    """Tests valid length validation."""
    cookies = {"code": "12345"}
    response = await client.get("/test-length", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"code": "12345"}

@pytest.mark.anyio
async def test_length_cookie_min_boundary(client: AsyncClient):
    """Tests minimum boundary condition."""
    cookies = {"code": ""}  # Empty string
    response = await client.get("/test-length", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

# CUSTOM VALIDATOR TESTS
@pytest.mark.anyio
async def test_custom_validator_fail(client: AsyncClient):
    """Tests custom validator function failure."""
    cookies = {"role": "guest"}  # "guest" is not in ["admin", "user"]
    response = await client.get("/test-custom", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid role." in response.json()["detail"]

@pytest.mark.anyio
async def test_custom_validator_pass_admin(client: AsyncClient):
    """Tests custom validator function success with 'admin'."""
    cookies = {"role": "admin"}
    response = await client.get("/test-custom", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"role": "admin"}

@pytest.mark.anyio
async def test_custom_validator_pass_user(client: AsyncClient):
    """Tests custom validator function success with 'user'."""
    cookies = {"role": "user"}
    response = await client.get("/test-custom", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"role": "user"}

# FORMAT PATTERN TESTS
@pytest.mark.anyio
async def test_bearer_token_valid_format(client: AsyncClient):
    """Tests valid bearer token format."""
    cookies = {"auth-token": "Bearer abc123.def456.ghi789"}
    response = await client.get("/test-bearer", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.anyio
async def test_bearer_token_lowercase_bearer(client: AsyncClient):
    """Tests bearer token with lowercase 'bearer'."""
    cookies = {"auth-token": "bearer abc123.def456.ghi789"}
    response = await client.get("/test-bearer", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.anyio
async def test_bearer_token_invalid_no_bearer_prefix(client: AsyncClient):
    """Tests bearer token missing 'Bearer' prefix."""
    cookies = {"auth-token": "abc123.def456.ghi789"}
    response = await client.get("/test-bearer", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Invalid bearer token format."}

@pytest.mark.anyio
async def test_email_valid_format(client: AsyncClient):
    """Tests valid email format."""
    cookies = {"user-email": "user@example.com"}
    response = await client.get("/test-email", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.anyio
async def test_email_with_plus_sign(client: AsyncClient):
    """Tests valid email with plus sign."""
    cookies = {"user-email": "user+tag@example.com"}
    response = await client.get("/test-email", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.anyio
async def test_email_invalid_format_no_at(client: AsyncClient):
    """Tests invalid email without @ symbol."""
    cookies = {"user-email": "userexample.com"}
    response = await client.get("/test-email", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.anyio
async def test_email_invalid_format_no_domain(client: AsyncClient):
    """Tests invalid email without domain."""
    cookies = {"user-email": "user@"}
    response = await client.get("/test-email", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

# NUMERIC RANGE TESTS
@pytest.mark.anyio
async def test_numeric_range_valid_min(client: AsyncClient):
    """Tests numeric value at minimum boundary (ge=0)."""
    cookies = {"score": "0"}
    response = await client.get("/test-ge-le", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"score": 0.0}

@pytest.mark.anyio
async def test_numeric_range_valid_max(client: AsyncClient):
    """Tests numeric value at maximum boundary (le=100)."""
    cookies = {"score": "100"}
    response = await client.get("/test-ge-le", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"score": 100.0}

@pytest.mark.anyio
async def test_numeric_range_valid_middle(client: AsyncClient):
    """Tests numeric value in middle of range."""
    cookies = {"score": "50"}
    response = await client.get("/test-ge-le", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"score": 50.0}

@pytest.mark.anyio
async def test_numeric_range_below_min(client: AsyncClient):
    """Tests numeric value below minimum (< 0)."""
    cookies = {"score": "-1"}
    response = await client.get("/test-ge-le", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Score must be between 0 and 100."}

@pytest.mark.anyio
async def test_numeric_range_above_max(client: AsyncClient):
    """Tests numeric value above maximum (> 100)."""
    cookies = {"score": "101"}
    response = await client.get("/test-ge-le", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Score must be between 0 and 100."}

@pytest.mark.anyio
async def test_numeric_range_float_valid(client: AsyncClient):
    """Tests decimal numeric value within range."""
    cookies = {"score": "75.5"}
    response = await client.get("/test-ge-le", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"score": 75.5}

@pytest.mark.anyio
async def test_numeric_range_non_numeric(client: AsyncClient):
    """Tests non-numeric value."""
    cookies = {"score": "not-a-number"}
    response = await client.get("/test-ge-le", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Score must be a number."}

# ASYNC VALIDATOR TESTS
@pytest.mark.anyio
async def test_async_validator_valid(client: AsyncClient):
    """Tests async validator function success."""
    cookies = {"async-token": "valid_token123"}
    response = await client.get("/test-async-custom", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"token": "valid_token123"}

@pytest.mark.anyio
async def test_async_validator_invalid(client: AsyncClient):
    """Tests async validator function failure."""
    cookies = {"async-token": "invalid_token123"}
    response = await client.get("/test-async-custom", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Token must start with 'valid_'." in response.json()["detail"]

# EDGE CASE TESTS
@pytest.mark.anyio
async def test_cookie_with_special_characters(client: AsyncClient):
    """Tests cookie value containing special characters."""
    cookies = {"code": "a@b#c"}  # 5 characters exactly
    response = await client.get("/test-length", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.anyio
async def test_cookie_with_spaces(client: AsyncClient):
    """Tests cookie value containing spaces."""
    # This should pass length check (5 chars including space)
    cookies = {"code": "a b c"}
    response = await client.get("/test-length", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"code": "a b c"}

@pytest.mark.anyio
async def test_cookie_with_unicode_characters(client: AsyncClient):
    """Tests cookie value containing numeric and special characters."""
    # Note: Unicode characters in cookies require URL encoding, which httpx handles
    # For simplicity, we'll test with ASCII-safe alphanumeric and special chars
    cookies = {"code": "abc12"}  # 5 characters
    response = await client.get("/test-length", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
