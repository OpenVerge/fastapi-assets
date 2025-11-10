"""
Test suite for the PathValidator class.
"""

import pytest
import asyncio
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from typing import Any, Callable, List


class MockValidationError(Exception):
    """Minimal mock of the custom ValidationError."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class MockBaseValidator:
    """
    Minimal mock of the BaseValidator to provide
    the methods PathValidator inherits.
    """

    def __init__(
        self, status_code: int, error_detail: str, validators: List[Callable] | None = None
    ):
        self._status_code = status_code
        self._error_detail = error_detail
        self._custom_validators = validators or []

    async def _validate_custom(self, value: Any) -> None:
        """Mock implementation of custom validator runner."""
        for validator in self._custom_validators:
            try:
                if asyncio.iscoroutinefunction(validator):
                    await validator(value)
                else:
                    validator(value)
            except Exception as e:
                # Raise the specific error PathValidator expects
                raise MockValidationError(detail=str(e), status_code=400) from e

    def _raise_error(self, value: Any, status_code: int, detail: str) -> None:
        """Mock implementation of the error raiser."""
        raise HTTPException(status_code=status_code, detail=detail)


#  Patch the imports in the module to be tested
# This is a professional testing pattern to inject mocks
import sys
import unittest.mock

# Create mock modules
mock_core_module = unittest.mock.MagicMock()
mock_core_module.BaseValidator = MockBaseValidator
mock_core_module.ValidationError = MockValidationError

# Add the mock module to sys.modules
# This ensures that when 'path_validator' imports from 'fastapi_assets.core',
# it gets our mock classes.
sys.modules["fastapi_assets.core"] = mock_core_module

# Now we can safely import the class to be tested
from fastapi_assets.request_validators import PathValidator

#
#                   Test Cases
#


def test_standard_path_validation_numeric():
    """
    Tests that standard validations (gt, lt) from fastapi.Path
    are correctly applied and that type coercion works.
    """
    app = FastAPI()
    item_id_validator = PathValidator("item_id", _type=int, gt=0, lt=10)

    @app.get("/items/{item_id}")
    def get_item(item_id: int = Depends(item_id_validator())):
        # We also check the type to ensure coercion from string happened
        return {"item_id": item_id, "type": str(type(item_id))}

    client = TestClient(app)

    # 1. Success case
    response = client.get("/items/5")
    assert response.status_code == 200
    assert response.json() == {"item_id": 5, "type": "<class 'int'>"}

    # 2. Failure case (gt)
    response = client.get("/items/0")
    assert response.status_code == 422  # Pydantic validation error
    assert "greater than 0" in response.text

    # 3. Failure case (lt)
    response = client.get("/items/10")
    assert response.status_code == 422
    assert "less than 10" in response.text

    # 4. Failure case (type coercion)
    response = client.get("/items/abc")
    assert response.status_code == 422
    assert "Input should be a valid integer" in response.text


def test_standard_path_validation_string():
    """
    Tests that standard string validations (min_length, max_length, pattern)
    from fastapi.Path are correctly applied.
    """
    app = FastAPI()
    username_validator = PathValidator(
        "username",
        _type=str,
        min_length=3,
        max_length=5,
        pattern=r"^[a-z]+$",  # only lowercase letters
    )

    @app.get("/users/{username}")
    def get_user(username: str = Depends(username_validator())):
        return {"username": username}

    client = TestClient(app)

    # 1. Success case
    response = client.get("/users/abc")
    assert response.status_code == 200
    assert response.json() == {"username": "abc"}

    # 2. Failure case (min_length)
    response = client.get("/users/ab")
    assert response.status_code == 422
    assert "at least 3 characters" in response.text

    # 3. Failure case (max_length)
    response = client.get("/users/abcdef")
    assert response.status_code == 422
    assert "at most 5 characters" in response.text

    # 4. Failure case (pattern)
    response = client.get("/users/123")
    assert response.status_code == 422
    assert "String should match pattern" in response.text


def test_custom_validation_allowed_values():
    """
    Tests the custom 'allowed_values' feature of PathValidator.
    """
    app = FastAPI()
    mode_validator = PathValidator("mode", _type=str, allowed_values=["read", "write"])

    @app.get("/modes/{mode}")
    def get_mode(mode: str = Depends(mode_validator())):
        return {"mode": mode}

    client = TestClient(app)

    # 1. Success cases
    response_read = client.get("/modes/read")
    assert response_read.status_code == 200
    assert response_read.json() == {"mode": "read"}

    response_write = client.get("/modes/write")
    assert response_write.status_code == 200
    assert response_write.json() == {"mode": "write"}

    # 2. Failure case
    response = client.get("/modes/admin")
    # This fails our custom check, which raises an HTTPException
    # based on the (mocked) _raise_error method.
    assert response.status_code == 400
    assert "Value 'admin' is not allowed" in response.text
    assert "Allowed values are: read, write" in response.text


def test_custom_validation_validators_list():
    """
    Tests the custom 'validators' list with both sync and async functions.
    """

    #  Custom validator functions for this test
    def must_be_even(value: int):
        """Sync validator."""
        if value % 2 != 0:
            raise ValueError("Value must be even")

    async def must_be_multiple_of_three(value: int):
        """Async validator."""
        await asyncio.sleep(0)  # Simulate async work
        if value % 3 != 0:
            raise Exception("Value must be a multiple of three")

    # -

    app = FastAPI()
    custom_num_validator = PathValidator(
        "num", _type=int, validators=[must_be_even, must_be_multiple_of_three]
    )

    @app.get("/nums/{num}")
    def get_num(num: int = Depends(custom_num_validator())):
        return {"num": num}

    client = TestClient(app)

    # 1. Success case (passes both validators)
    response = client.get("/nums/6")
    assert response.status_code == 200
    assert response.json() == {"num": 6}

    # 2. Failure case (fails sync validator)
    response = client.get("/nums/9")
    assert response.status_code == 400
    assert "Value must be even" in response.text

    # 3. Failure case (fails async validator)
    response = client.get("/nums/4")
    assert response.status_code == 400
    assert "Value must be a multiple of three" in response.text


def test_validator_isolation():
    """
    Tests that multiple PathValidator instances on the same app
    do not interfere with each other's signatures. This is the
    most critical test given the history of bugs.
    """
    app = FastAPI()

    # 1. Define two different validators
    item_id_validator = PathValidator("item_id", _type=int, gt=10)
    username_validator = PathValidator("username", _type=str, min_length=5)

    # 2. Define two separate endpoints
    @app.get("/items/{item_id}")
    def get_item(item_id: int = Depends(item_id_validator())):
        return {"item_id": item_id}

    @app.get("/users/{username}")
    def get_user(username: str = Depends(username_validator())):
        return {"username": username}

    client = TestClient(app)

    # 3. Test both endpoints successfully
    response_item = client.get("/items/11")
    assert response_item.status_code == 200
    assert response_item.json() == {"item_id": 11}

    response_user = client.get("/users/administrator")
    assert response_user.status_code == 200
    assert response_user.json() == {"username": "administrator"}

    # 4. Test failure on the *first* endpoint
    response_item_fail = client.get("/items/5")
    assert response_item_fail.status_code == 422
    # CRITICAL: Error must be about 'item_id', not 'username'
    assert "item_id" in response_item_fail.text
    assert "greater than 10" in response_item_fail.text
    assert "username" not in response_item_fail.text

    # 5. Test failure on the *second* endpoint
    response_user_fail = client.get("/users/adm")
    assert response_user_fail.status_code == 422
    assert "username" in response_user_fail.text
    assert "at least 5 characters" in response_user_fail.text
    assert "item_id" not in response_user_fail.text
