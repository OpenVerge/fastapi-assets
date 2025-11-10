"""Tests for the QueryValidator class."""

import pytest
import asyncio
from typing import Any, Callable, List, Optional, Union
from inspect import Signature, Parameter
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.testclient import TestClient
from fastapi_assets.request_validators import QueryValidator
from fastapi_assets.core import ValidationError


def get_app_and_client(validator_instance: QueryValidator) -> tuple[FastAPI, TestClient]:
    """Helper function to create a test app for a given validator."""
    app = FastAPI()

    @app.get("/validate/")
    def validate_endpoint(
        # The key is to call the instance to get the dependency function
        param: Any = Depends(validator_instance()),
    ):
        return {"validated_param": param}

    client = TestClient(app)
    return app, client


def test_standard_query_validation_ge():
    """
    Tests that standard Query params (like 'ge') are enforced by FastAPI
    before our custom validation runs. This should result in a 422 error.
    """
    page_validator = QueryValidator("page", _type=int, default=1, ge=1)
    app, client = get_app_and_client(page_validator)

    # Test valid case
    response = client.get("/validate/?page=5")
    assert response.status_code == 200
    assert response.json() == {"validated_param": 5}

    # Test invalid case (FastAPI's built-in 'ge' validation)
    response = client.get("/validate/?page=0")
    assert response.status_code == 422  # Unprocessable Entity
    assert "greater than or equal to 1" in response.text


def test_standard_query_validation_type_error():
    """
    Tests that FastAPI's type coercion and validation fail first.
    """
    page_validator = QueryValidator("page", _type=int, ge=1)
    app, client = get_app_and_client(page_validator)

    response = client.get("/validate/?page=not-an-integer")
    assert response.status_code == 422
    detail = response.json()["detail"]
    # Check if detail is a list (modern Pydantic v2) or a string (older format)
    if isinstance(detail, list):
        assert any("integer" in str(error.get("msg", "")).lower() for error in detail)
    else:
        assert "integer" in str(detail).lower()


def test_required_parameter_missing():
    """
    Tests that a parameter without a default is correctly marked as required.
    """
    # Note: `default=...` is the default, making it required
    token_validator = QueryValidator("token", _type=str)
    app, client = get_app_and_client(token_validator)

    # Test missing required parameter
    response = client.get("/validate/")
    assert response.status_code == 422
    assert "Field required" in response.text

    # Test providing the parameter
    response = client.get("/validate/?token=abc")
    assert response.status_code == 200
    assert response.json() == {"validated_param": "abc"}


def test_default_value_is_used():
    """
    Tests that the default value is used when the parameter is omitted.
    """
    page_validator = QueryValidator("page", _type=int, default=1, ge=1)
    app, client = get_app_and_client(page_validator)

    response = client.get("/validate/")
    assert response.status_code == 200
    assert response.json() == {"validated_param": 1}


def test_allowed_values_success():
    """
    Tests that a value in the 'allowed_values' list passes validation.
    """
    status_validator = QueryValidator("status", _type=str, allowed_values=["active", "pending"])
    app, client = get_app_and_client(status_validator)

    response_active = client.get("/validate/?status=active")
    assert response_active.status_code == 200
    assert response_active.json() == {"validated_param": "active"}

    response_pending = client.get("/validate/?status=pending")
    assert response_pending.status_code == 200
    assert response_pending.json() == {"validated_param": "pending"}


def test_allowed_values_failure():
    """
    Tests that a value NOT in the 'allowed_values' list fails with a 400.
    """
    status_validator = QueryValidator("status", _type=str, allowed_values=["active", "pending"])
    app, client = get_app_and_client(status_validator)

    response = client.get("/validate/?status=archived")
    assert response.status_code == 400  # Bad Request
    detail = response.json()["detail"]
    assert "Value 'archived' is not allowed" in detail
    assert "Allowed values are: active, pending" in detail


def test_custom_sync_validator_success():
    """
    Tests a passing synchronous custom validator.
    """

    def is_even(v: int):
        if not v % 2 == 0:
            raise ValidationError("Not Even")

    num_validator = QueryValidator("num", _type=int, validators=[is_even])
    app, client = get_app_and_client(num_validator)

    response = client.get("/validate/?num=10")
    assert response.status_code == 200
    assert response.json() == {"validated_param": 10}


def test_custom_sync_validator_failure_with_validation_error():
    """
    Tests a failing synchronous custom validator that raises ValidationError.
    """

    def must_be_even(v: int):
        if v % 2 != 0:
            raise ValidationError(detail="Value must be even.", status_code=400)

    num_validator = QueryValidator("num", _type=int, validators=[must_be_even])
    app, client = get_app_and_client(num_validator)

    response = client.get("/validate/?num=7")
    assert response.status_code == 400
    assert "Value must be even." in response.json()["detail"]


@pytest.mark.asyncio
async def test_custom_async_validator_success():
    """
    Tests a passing asynchronous custom validator.
    """

    async def async_check_pass(v: str):
        await asyncio.sleep(0)
        return v == "valid"

    key_validator = QueryValidator("key", _type=str, validators=[async_check_pass])
    app, client = get_app_and_client(key_validator)

    response = client.get("/validate/?key=valid")
    assert response.status_code == 200
    assert response.json() == {"validated_param": "valid"}


@pytest.mark.asyncio
async def test_custom_async_validator_failure_with_validation_error():
    """
    Tests a failing asynchronous custom validator that raises ValidationError.
    """

    async def async_check_fail(v: str):
        await asyncio.sleep(0)
        if v != "valid":
            raise ValidationError(detail="Key is not valid.", status_code=400)

    key_validator = QueryValidator("key", _type=str, validators=[async_check_fail])
    app, client = get_app_and_client(key_validator)

    response = client.get("/validate/?key=invalid")
    assert response.status_code == 400
    assert "Key is not valid." in response.json()["detail"]


def test_custom_validator_failure_silent():
    """
    Tests a validator that fails by returning 'False' and checks that
    'on_custom_validator_error_detail' is used.
    """

    def silent_fail(v: str):
        if not v == "must-be-this":
            raise ValidationError("Value did not match required string.")

    error_msg = "Value did not match required string."
    key_validator = QueryValidator(
        "key", _type=str, validators=[silent_fail], on_custom_validator_error_detail=error_msg
    )
    app, client = get_app_and_client(key_validator)

    response = client.get("/validate/?key=wrong-string")
    assert response.status_code == 400
    assert error_msg in response.json()["detail"]


def test_validation_order():
    """
    Tests that 'allowed_values' check runs before 'validators'.
    """

    def should_not_be_called(v: str):
        """This validator should fail, but it shouldn't even be reached."""
        if v == "beta":
            raise ValidationError(detail="Custom validator was called.", status_code=400)
        return

    validator = QueryValidator(
        "version",
        _type=str,
        allowed_values=["alpha", "gamma"],  # "beta" is not allowed
        validators=[should_not_be_called],
    )
    app, client = get_app_and_client(validator)

    # This request should fail at the 'allowed_values' check
    response = client.get("/validate/?version=beta")

    # It should be a 400 Bad Request
    assert response.status_code == 400

    # The error detail should be from _validate_allowed_values, NOT the custom validator
    assert "Value 'beta' is not allowed" in response.json()["detail"]
    assert "Custom validator was called" not in response.json()["detail"]
