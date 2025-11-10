"""Base classes for FastAPI validation dependencies."""

import abc
from typing import Any, Callable, Optional, Union, List
from fastapi import HTTPException
from fastapi_assets.core.exceptions import ValidationError
import inspect


class BaseValidator(abc.ABC):
    r"""
    Abstract base class for creating reusable FastAPI validation dependencies.

    This class provides a standardized `__init__` for handling custom error
    messages and status codes. It also provides a protected helper method,
    `_raise_error`, for subclasses to raise consistent `HTTPException`s.

    Subclasses MUST implement the `__call__` method.

    .. code-block:: python
        from fastapi import Header
        from fastapi_assets.core.base_validator import BaseValidator, ValidationError
        class MyValidator(BaseValidator):
            def _validate(self, token: str) -> None:
                # This method is testable without FastAPI
                if not token.startswith("sk_"):
                    # Raise the logic-level exception
                    raise ValidationError(detail="Token must start with 'sk_'.")
            def __call__(self, x_token: str = Header(...)):
                try:
                    # 1. Run the pure validation logic
                    self._validate_logic(x_token)
                except ValidationError as e:
                    # 2. Catch logic error and raise HTTP error
                    self._raise_error(
                        detail=e.detail, # Pass specific detail
                        status_code=e.status_code # Pass specific code
                    )
                # 3. Return the valid value
                return x_token
    """

    def __init__(
        self,
        *,
        status_code: int = 400,
        error_detail: Union[str, Callable[[Any], str]] = "Validation failed.",
        validators: Optional[List[Callable]] = None,
    ):
        """
        Initializes the base validator.

        Args:
            status_code: The default HTTP status code to raise if
                validation fails.
            error_detail: The default error message. Can be a static
                string or a callable that takes the invalid value as its
                argument and returns a dynamic error string.
            validators: Optional list of callables for custom validation logic.
        """
        self._status_code = status_code
        self._error_detail = error_detail
        self._custom_validators = validators or []

    def _raise_error(
        self,
        value: Optional[Any] = None,
        status_code: Optional[int] = None,
        detail: Optional[Union[str, Callable[[Any], str]]] = None,
    ) -> None:
        """
        Raises a standardized HTTPException with resolved error detail.

        This helper method handles both static error strings and dynamic error
        callables, automatically resolving them to a final error message before
        raising the HTTPException.

        Args:
            value: The value that failed validation. Passed to the error_detail
                callable if it is callable.
            status_code: A specific HTTP status code for this failure, overriding
                the instance's default status_code.
            detail: A specific error detail message (string or callable) for this
                failure, overriding the instance's default error_detail.

        Returns:
            None

        Raises:
            HTTPException: Always raises with the resolved status code and detail.
        """
        final_status_code = status_code if status_code is not None else self._status_code

        # Use the detail from the raised ValidationError if provided,
        # otherwise fall back to the instance's default.
        error_source = detail if detail else self._error_detail

        final_detail: str
        if callable(error_source):
            final_detail = error_source(value)
        else:
            final_detail = str(error_source)

        raise HTTPException(status_code=final_status_code, detail=final_detail)

    @abc.abstractmethod
    async def _validate(self, value: Any) -> Any:
        """
        Abstract method for pure validation logic.

        Subclasses MUST implement this method to perform the actual
        validation. This method should raise `ValidationError` if
        validation fails.

        Args:
            value: The value to validate.

        Returns:
            The validated value, which can be of any type depending on the validator.
        """
        raise NotImplementedError(
            "Subclasses of BaseValidator must implement the _validate method."
        )

    async def _validate_custom(self, value: Any) -> None:
        """
        Executes all configured custom validator functions.

        Iterates through the list of custom validators, supporting both
        synchronous and asynchronous validator functions. Catches exceptions
        and converts them to ValidationError instances.

        Args:
            value: The value to validate using custom validators.

        Returns:
            None

        Raises:
            ValidationError: If any validator raises an exception or explicitly
                raises ValidationError.
        """
        if self._custom_validators is None:
            return

        for validator_func in self._custom_validators:
            try:
                if inspect.iscoroutinefunction(validator_func):
                    await validator_func(value)
                else:
                    validator_func(value)
            except ValidationError:
                raise  # Re-raise explicit validation errors
            except Exception as e:
                # Catch any other exception from the validator
                detail = f"Custom validation failed. Error: {e}"
                raise ValidationError(detail=detail, status_code=self._status_code)

    @abc.abstractmethod
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Abstract callable entry point for FastAPI's dependency injection.

        Subclasses MUST implement this method. The implementation's
        signature should define the dependency (e.g., using Query, Header).

        **Recommended Pattern:**

        This method should handle the FastAPI dependency and HTTP logic,
        while delegating the pure validation logic to a separate method.
        This makes your logic independently testable.

        .. code-block:: python

            from fastapi import Header

            class MyValidator(BaseValidator):

                async def _validate(self, token: str) -> None:
                    # This method is testable without FastAPI
                    if not token.startswith("sk_"):
                        # Raise the logic-level exception
                        raise ValidationError(detail="Token must start with 'sk_'.")

                def __call__(self, x_token: str = Header(...)):
                    try:
                        # 1. Run the pure validation logic
                        await self._validate(x_token)
                        await self._validate_custom(x_token)
                    except ValidationError as e:
                        # 2. Catch logic error and raise HTTP error
                        self._raise_error(
                            value=x_token,
                            detail=e.detail, # Pass specific detail
                            status_code=e.status_code # Pass specific code
                        )

                    # 3. Return the valid value
                    return x_token

        """
        raise NotImplementedError("Subclasses of BaseValidator must implement the __call__ method.")
