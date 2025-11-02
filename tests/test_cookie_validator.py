"""
Unit Tests for the CookieAssert Validator
=========================================

This file contains unit tests for the `CookieAssert` class.
It uses `pytest` and `httpx` to create a test FastAPI application
and send requests to it to validate all behaviors.

To run these tests:
1. Make sure `cookie_validator.py` is in the same directory.
2. pip install pytest httpx fastapi "uvicorn[standard]"
3. Run `pytest -v` in your terminal.
"""

import pytest
import uuid
from typing import Optional
from fastapi import FastAPI, Depends, status
from httpx import AsyncClient

# Import the class to be tested
# (Assumes cookie_validator.py is in the same directory)
try:
    from fastapi_assets.validators.cookie_validator import CookieAssert
except ImportError:
    pytest.skip("Could not import CookieAssert from cookie_validator.py", allow_module_level=True)

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
    if val not in ["admin", "user"]:
        raise ValueError("Role is invalid")
    return True

validate_custom_role = CookieAssert(
    alias="role",
    validator=_custom_check,
    on_validator_error_detail="Invalid role."
)

# Create a minimal FastAPI app for testing
app = FastAPI()

@app.get("/test-required")
async def get_required(session: str = Depends(validate_required_uuid)):
    return {"session": session}

@app.get("/test-optional")
async def get_optional(tracker: Optional[float] = Depends(validate_optional_gt10)):
    # Note: numeric validators return floats
    return {"tracker": tracker}

@app.get("/test-length")
async def get_length(code: str = Depends(validate_length_5)):
    return {"code": code}

@app.get("/test-custom")
async def get_custom(role: str = Depends(validate_custom_role)):
    return {"role": role}

# --- Pytest Fixture ---

@pytest.fixture
async def client():
    """Pytest fixture to create an AsyncClient for the test app."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# --- Test Cases ---

@pytest.mark.asyncio
async def test_required_cookie_missing(client: AsyncClient):
    """Tests that a required cookie raises an error if missing."""
    response = await client.get("/test-required")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Session is required."}

@pytest.mark.asyncio
async def test_required_cookie_invalid_format(client: AsyncClient):
    """Tests that a required cookie fails on invalid format."""
    cookies = {"session-id": "not-a-valid-uuid"}
    response = await client.get("/test-required", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Invalid session format."}

@pytest.mark.asyncio
async def test_required_cookie_valid(client: AsyncClient):
    """Tests that a required cookie passes with valid format."""
    valid_uuid = str(uuid.uuid4())
    cookies = {"session-id": valid_uuid}
    response = await client.get("/test-required", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"session": valid_uuid}

@pytest.mark.asyncio
async def test_optional_cookie_missing(client: AsyncClient):
    """Tests that an optional cookie returns the default (None) if missing."""
    response = await client.get("/test-optional")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"tracker": None}

@pytest.mark.asyncio
async def test_optional_cookie_invalid_comparison(client: AsyncClient):
    """Tests that an optional cookie fails numeric comparison."""
    cookies = {"tracker": "5"} # 5 is not > 10
    response = await client.get("/test-optional", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Tracker must be > 10."}

@pytest.mark.asyncio
async def test_optional_cookie_invalid_numeric(client: AsyncClient):
    """Tests that a numeric cookie fails non-numeric values."""
    cookies = {"tracker": "not-a-number"}
    response = await client.get("/test-optional", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Tracker must be a number."}

@pytest.mark.asyncio
async def test_optional_cookie_valid(client: AsyncClient):
    """Tests that an optional cookie passes with a valid value."""
    cookies = {"tracker": "100"}
    response = await client.get("/test-optional", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"tracker": 100.0} # Note: value is cast to float

@pytest.mark.asyncio
async def test_length_cookie_too_short(client: AsyncClient):
    """Tests min_length validation."""
    cookies = {"code": "1234"} # Length 4, min is 5
    response = await client.get("/test-length", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Code must be 5 chars."}

@pytest.mark.asyncio
async def test_length_cookie_too_long(client: AsyncClient):
    """Tests max_length validation."""
    cookies = {"code": "123456"} # Length 6, max is 5
    response = await client.get("/test-length", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Code must be 5 chars."}

@pytest.mark.asyncio
async def test_length_cookie_valid(client: AsyncClient):
    """Tests valid length validation."""
    cookies = {"code": "12345"}
    response = await client.get("/test-length", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"code": "12345"}

@pytest.mark.asyncio
async def test_custom_validator_fail(client: AsyncClient):
    """Tests custom validator function failure."""
    cookies = {"role": "guest"} # "guest" is not in ["admin", "user"]
    response = await client.get("/test-custom", cookies=cookies)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # Note: custom validator exceptions are appended to the detail
    assert response.json() == {"detail": "Invalid role.: Role is invalid"}

@pytest.mark.asyncio
async def test_custom_validator_pass(client: AsyncClient):
    """Tests custom validator function success."""
    cookies = {"role": "admin"}
    response = await client.get("/test-custom", cookies=cookies)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"role": "admin"}

