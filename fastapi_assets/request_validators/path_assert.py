"""Module providing the PathValidator for validating path parameters in FastAPI."""
import re
from typing import Any, Callable, List, Optional, Union
from fastapi import Path
from fastapi_assets.core.base_validator import BaseValidator, ValidationError


class PathValidator(BaseValidator):
    r"""
    A general-purpose dependency for validating path parameters in FastAPI.

    It validates path parameters with additional constraints like allowed values,
    regex patterns, string length checks, numeric bounds, and custom validators.

    .. code-block:: python
        from fastapi import FastAPI
        from fastapi_assets.validators.path_validator import PathValidator

        app = FastAPI()

        # Create reusable validators
        item_id_validator = PathValidator(
            gt=0,
            lt=1000,
            on_error_detail="Item ID must be between 1 and 999"
        )

        username_validator = PathValidator(
            min_length=5,
            max_length=15,
            pattern=r"^[a-zA-Z0-9]+$",
            on_error_detail="Username must be 5-15 alphanumeric characters"
        )

        @app.get("/items/{item_id}")
        def get_item(item_id: int = item_id_validator):
            return {"item_id": item_id}

        @app.get("/users/{username}")
        def get_user(username: str = username_validator):
            return {"username": username}
    """

    def __init__(
        self,
        default: Any = ...,
        *,
        allowed_values: Optional[List[Any]] = None,
        pattern: Optional[str] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        gt: Optional[Union[int, float]] = None,
        lt: Optional[Union[int, float]] = None,
        ge: Optional[Union[int, float]] = None,
        le: Optional[Union[int, float]] = None,
        validator: Optional[Callable[[Any], bool]] = None,
        on_error_detail: Optional[Union[str, Callable[[Any], str]]] = None,
        # Standard Path() parameters
        title: Optional[str] = None,
        description: Optional[str] = None,
        alias: Optional[str] = None,
        deprecated: Optional[bool] = None,
        **path_kwargs
    ):
        """
        Initializes the PathValidator.

        Args:
            default: Default value for the path parameter (usually ... for required).
            allowed_values: List of allowed values for the parameter.
            pattern: Regex pattern the parameter must match (for strings).
            min_length: Minimum length for string parameters.
            max_length: Maximum length for string parameters.
            gt: Value must be greater than this (for numeric parameters).
            lt: Value must be less than this (for numeric parameters).
            ge: Value must be greater than or equal to this.
            le: Value must be less than or equal to this.
            validator: Custom validation function that takes the value and returns bool.
            on_error_detail: Custom error message for validation failures.
            title: Title for API documentation.
            description: Description for API documentation.
            alias: Alternative parameter name.
            deprecated: Whether the parameter is deprecated.
            **path_kwargs: Additional arguments passed to FastAPI's Path().
        """
        # Call super() with default error handling
        super().__init__(
            status_code=400,
            error_detail=on_error_detail or "Path parameter validation failed."
        )

        # Store validation rules
        self._allowed_values = allowed_values
        self._pattern = re.compile(pattern) if pattern else None
        self._min_length = min_length
        self._max_length = max_length
        self._gt = gt
        self._lt = lt
        self._ge = ge
        self._le = le
        self._custom_validator = validator

        # Store the underlying FastAPI Path parameter
        # This preserves all standard Path() features (title, description, etc.)
        self._path_param = Path(
            default,
            title=title,
            description=description,
            alias=alias,
            deprecated=deprecated,
            gt=gt,
            lt=lt,
            ge=ge,
            le=le,
            **path_kwargs
        )

    def __call__(self, value: Any = None) -> Any:
        """
        FastAPI dependency entry point for path validation.

        Args:
            value: The path parameter value extracted from the URL.

        Returns:
            The validated path parameter value.

        Raises:
            HTTPException: If validation fails.
        """
        # If value is None, it means FastAPI will inject the actual path parameter
        # This happens because FastAPI handles the Path() dependency internally
        if value is None:
            # Return a dependency that FastAPI will use
            async def dependency(param_value: Any = self._path_param):
                return self._validate(param_value)
            return dependency

        # If value is provided (for testing), validate directly
        return self._validate(value)

    def _validate(self, value: Any) -> Any:
        """
        Runs all validation checks on the parameter value.

        Args:
            value: The path parameter value to validate.

        Returns:
            The validated value.

        Raises:
            HTTPException: If any validation check fails.
        """
        try:
            self._validate_allowed_values(value)
            self._validate_pattern(value)
            self._validate_length(value)
            self._validate_numeric_bounds(value)
            self._validate_custom(value)
        except ValidationError as e:
            # Convert ValidationError to HTTPException
            self._raise_error(
                value=value,
                status_code=e.status_code,
                detail=str(e.detail)
            )

        return value

    def _validate_allowed_values(self, value: Any) -> None:
        """
        Checks if the value is in the list of allowed values.

        Args:
            value: The parameter value to check.

        Raises:
            ValidationError: If the value is not in allowed_values.
        """
        if self._allowed_values is None:
            return  # No validation rule set

        if value not in self._allowed_values:
            detail = (
                f"Value '{value}' is not allowed. "
                f"Allowed values are: {', '.join(map(str, self._allowed_values))}"
            )
            raise ValidationError(detail=detail, status_code=400)

    def _validate_pattern(self, value: Any) -> None:
        """
        Checks if the string value matches the required regex pattern.

        Args:
            value: The parameter value to check.

        Raises:
            ValidationError: If the value doesn't match the pattern.
        """
        if self._pattern is None:
            return  # No validation rule set

        if not isinstance(value, str):
            return  # Pattern validation only applies to strings

        if not self._pattern.match(value):
            detail = (
                f"Value '{value}' does not match the required pattern: "
                f"{self._pattern.pattern}"
            )
            raise ValidationError(detail=detail, status_code=400)

    def _validate_length(self, value: Any) -> None:
        """
        Checks if the string length is within the specified bounds.

        Args:
            value: The parameter value to check.

        Raises:
            ValidationError: If the length is out of bounds.
        """
        if not isinstance(value, str):
            return  # Length validation only applies to strings

        value_len = len(value)

        if self._min_length is not None and value_len < self._min_length:
            detail = (
                f"Value '{value}' is too short. "
                f"Minimum length is {self._min_length} characters."
            )
            raise ValidationError(detail=detail, status_code=400)

        if self._max_length is not None and value_len > self._max_length:
            detail = (
                f"Value '{value}' is too long. "
                f"Maximum length is {self._max_length} characters."
            )
            raise ValidationError(detail=detail, status_code=400)

    def _validate_numeric_bounds(self, value: Any) -> None:
        """
        Checks if numeric values satisfy gt, lt, ge, le constraints.

        Args:
            value: The parameter value to check.

        Raises:
            ValidationError: If the value is out of the specified bounds.
        """
        if not isinstance(value, (int, float)):
            return  # Numeric validation only applies to numbers

        if self._gt is not None and value <= self._gt:
            detail = f"Value must be greater than {self._gt}"
            raise ValidationError(detail=detail, status_code=400)

        if self._lt is not None and value >= self._lt:
            detail = f"Value must be less than {self._lt}"
            raise ValidationError(detail=detail, status_code=400)

        if self._ge is not None and value < self._ge:
            detail = f"Value must be greater than or equal to {self._ge}"
            raise ValidationError(detail=detail, status_code=400)

        if self._le is not None and value > self._le:
            detail = f"Value must be less than or equal to {self._le}"
            raise ValidationError(detail=detail, status_code=400)

    def _validate_custom(self, value: Any) -> None:
        """
        Runs a custom validation function if provided.

        Args:
            value: The parameter value to check.

        Raises:
            ValidationError: If the custom validator returns False or raises an exception.
        """
        if self._custom_validator is None:
            return  # No custom validator set

        try:
            if not self._custom_validator(value):
                detail = f"Custom validation failed for value '{value}'"
                raise ValidationError(detail=detail, status_code=400)
        except Exception as e:
            # If the validator itself raises an exception, catch it
            detail = f"Custom validation error: {str(e)}"
            raise ValidationError(detail=detail, status_code=400)