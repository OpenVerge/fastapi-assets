"""Base classes for FastAPI validation dependencies."""

import abc
from typing import Any, Callable, Optional, Union
from fastapi import HTTPException
from fastapi_assets.core.exceptions import ValidationError


class BaseValidator(abc.ABC):
    """
    Abstract base class for creating reusable FastAPI validation dependencies.

    This class provides a standardized `__init__` for handling custom error
    messages and status codes. It also provides a protected helper method,
    `_raise_error`, for subclasses to raise consistent `HTTPException`s.

    Subclasses MUST implement the `__call__` method.
    """

    def __init__(
        self,
        *,
        status_code: int = 400,
        error_detail: Union[str, Callable[[Any], str]] = "Validation failed.",
    ):
        """
        Initializes the base validator.

        Args:
            status_code: The default HTTP status code to raise if
                validation fails.
            error_detail: The default error message. Can be a static
                string or a callable that takes the invalid value as its
                argument and returns a dynamic error string.
        """
        self._status_code = status_code
        self._error_detail = error_detail

    def _raise_error(
        self,
        value: Any,
        status_code: Optional[int] = None,
        detail: Optional[Union[str, Callable[[Any], str]]] = None,
    ) -> None:
        """
        Helper method to raise a standardized HTTPException.

        It automatically resolves callable error details.

        Args:
            value: The value that failed validation. This is passed
                to the error_detail callable, if it is one.
            status_code: A specific status code for this failure,
                overriding the instance's default status_code.
            detail: A specific error detail for this failure,
                overriding the instance's default error_detail.
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

                def _validate_logic(self, token: str) -> None:
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
                            value=x_token,
                            detail=e.detail, # Pass specific detail
                            status_code=e.status_code # Pass specific code
                        )

                    # 3. Return the valid value
                    return x_token

        """
        raise NotImplementedError("Subclasses of BaseValidator must implement the __call__ method.")
