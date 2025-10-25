"""Tests for the BaseValidator abstract base class."""

import pytest
from fastapi import HTTPException
from typing import Any, Callable
from fastapi_assets.core.base_validator import BaseValidator
from fastapi_assets.core.exceptions import ValidationError


# --- Test Setup ---


class _MockValidator(BaseValidator):
    """
    A minimal concrete implementation of BaseValidator for testing.

    This class exists only to allow instantiation of the abstract
    BaseValidator so its concrete methods (__init__, _raise_error)
    can be unit tested.
    """

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Minimal implementation to satisfy the abstract contract."""
        pass

    def public_raise_error(
        self,
        value: Any,
        status_code: int | None = None,
        detail: str | Callable[[Any], str] | None = None,
    ) -> None:
        """
        A public wrapper to call the protected _raise_error method.
        """
        self._raise_error(value=value, status_code=status_code, detail=detail)


# --- Test Cases ---


def test_cannot_instantiate_abstract_class() -> None:
    """
    Verifies that the BaseValidator class cannot be instantiated directly.
    """
    with pytest.raises(TypeError) as exc_info:
        BaseValidator()

    assert "Can't instantiate abstract class BaseValidator" in str(exc_info.value)


def test_init_sets_defaults() -> None:
    """
    Tests that the __init__ method correctly sets the default
    status code and error detail when no arguments are provided.
    """
    validator = _MockValidator()

    assert validator._status_code == 400
    assert validator._error_detail == "Validation failed."


def test_init_sets_custom_values() -> None:
    """
    Tests that the __init__ method correctly stores custom
    status code and error detail arguments.
    """
    custom_detail = "This is a custom error."
    custom_callable = lambda v: f"Custom value {v}"

    # Test with string detail
    validator_str = _MockValidator(status_code=404, error_detail=custom_detail)
    assert validator_str._status_code == 404
    assert validator_str._error_detail == custom_detail

    # Test with callable detail
    validator_callable = _MockValidator(status_code=422, error_detail=custom_callable)
    assert validator_callable._status_code == 422
    assert validator_callable._error_detail == custom_callable


def test_raise_error_uses_instance_defaults() -> None:
    """
    Tests that _raise_error uses the status_code and error_detail
    from the validator's instance when no overrides are provided.
    """
    validator = _MockValidator(status_code=401, error_detail="Auth error.")

    with pytest.raises(HTTPException) as exc_info:
        validator.public_raise_error(value="test_value")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Auth error."


def test_raise_error_with_callable_default_detail() -> None:
    """
    Tests that _raise_error correctly resolves a callable
    error_detail stored on the instance, passing the 'value' to it.
    """
    dynamic_detail = lambda v: f"The value '{v}' is invalid."
    validator = _MockValidator(status_code=422, error_detail=dynamic_detail)

    with pytest.raises(HTTPException) as exc_info:
        validator.public_raise_error(value="bad_input")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "The value 'bad_input' is invalid."


def test_raise_error_with_overrides() -> None:
    """
    Tests that arguments passed directly to _raise_error
    (status_code, detail) take precedence over instance defaults.
    """
    # Setup instance defaults
    validator = _MockValidator(status_code=400, error_detail="This should be overridden.")

    override_detail = "This is the override."

    with pytest.raises(HTTPException) as exc_info:
        validator.public_raise_error(value="test_value", status_code=403, detail=override_detail)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == override_detail


def test_raise_error_with_callable_detail_override() -> None:
    """
    Tests that a callable 'detail' passed directly to _raise_error
    is used and correctly resolved.
    """
    validator = _MockValidator(status_code=400, error_detail="This should be overridden.")

    override_callable = lambda v: f"Callable override received: '{v}'"

    with pytest.raises(HTTPException) as exc_info:
        validator.public_raise_error(
            value="data_for_callable", status_code=500, detail=override_callable
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Callable override received: 'data_for_callable'"


def test_raise_error_status_code_override_only() -> None:
    """
    Tests that overriding only the status_code still uses
    the default error_detail from the instance.
    """
    validator = _MockValidator(status_code=400, error_detail="Default detail.")

    with pytest.raises(HTTPException) as exc_info:
        validator.public_raise_error(value="test", status_code=401)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Default detail."


def test_raise_error_detail_override_only() -> None:
    """
    Tests that overriding only the detail still uses
    the default status_code from the instance.
    """
    validator = _MockValidator(status_code=400, error_detail="Default detail.")

    with pytest.raises(HTTPException) as exc_info:
        validator.public_raise_error(value="test", detail="Override detail.")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Override detail."


def test_raise_error_with_falsy_detail_override_falls_back() -> None:
    """
    Tests that if a 'detail' override is provided but is a
    falsy value (like an empty string), _raise_error
    correctly falls back to the instance's default error_detail.

    This tests the `if detail else self._error_detail` logic.
    """
    validator = _MockValidator(status_code=400, error_detail="This is the default.")

    with pytest.raises(HTTPException) as exc_info:
        validator.public_raise_error(
            value="test",
            detail="",  # Falsy override
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "This is the default."
