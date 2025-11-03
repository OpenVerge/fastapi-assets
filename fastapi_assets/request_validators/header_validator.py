"""HeaderValidator for validating HTTP headers in FastAPI."""

import re
from typing import Any, Callable, Dict, List, Optional, Union, Pattern
from fastapi_assets.core.base_validator import BaseValidator, ValidationError
from fastapi import Header
from fastapi.param_functions import _Unset

Undefined = _Unset


# Predefined format patterns for common header validation use cases
_FORMAT_PATTERNS: Dict[str, str] = {
    "uuid4": r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "bearer_token": r"^Bearer [a-zA-Z0-9\-._~+/]+=*$",
    "datetime": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$",
    "alphanumeric": r"^[a-zA-Z0-9]+$",
    "api_key": r"^[a-zA-Z0-9]{32,}$",
}


class HeaderValidator(BaseValidator):
    r"""
    A general-purpose dependency for validating HTTP request headers in FastAPI.

    It extends FastAPI's built-in Header with additional validation capabilities
    including pattern matching, format validation, allowed values, and custom validators.

    .. code-block:: python
        from fastapi import FastAPI
        from fastapi_assets.request_validators.header_validator import HeaderValidator

        app = FastAPI()

        # Validate API key header with pattern
        api_key_validator = HeaderValidator(
            alias="X-API-Key",
            pattern=r"^[a-zA-Z0-9]{32}$",
            required=True,
            on_error_detail="Invalid API key format"
        )

        # Validate authorization header with bearer token format
        auth_validator = HeaderValidator(
            alias="Authorization",
            format="bearer_token",
            required=True
        )

        # Validate custom header with allowed values
        version_validator = HeaderValidator(
            alias="X-API-Version",
            allowed_values=["v1", "v2", "v3"],
            required=False,
            default="v1"
        )

        @app.get("/secure")
        def secure_endpoint(
            api_key: str = api_key_validator,
            auth: str = auth_validator,
            version: str = version_validator
        ):
            return {"message": "Access granted", "version": version}
    """

    def __init__(
        self,
        default: Any = Undefined,
        *,
        required: Optional[bool] = True,
        alias: Optional[str] = None,
        convert_underscores: bool = True,
        pattern: Optional[str] = None,
        format: Optional[str] = None,
        allowed_values: Optional[List[str]] = None,
        validator: Optional[Callable[[str], bool]] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        **header_kwargs: Any,
    ) -> None:
        """
        Initializes the HeaderValidator instance.

        Args:
            default (Any): The default value if the header is not provided.
            required Optional[bool]: Explicitly set if the header is not required.
            alias (Optional[str]): The alias of the header. This is the actual
                header name (e.g., "X-API-Key").
            convert_underscores (bool): If `True` (default), underscores in
                the variable name will be converted to hyphens in the header name.
            pattern (Optional[str]): A regex pattern string that the header
                value must match.
            format (Optional[str]): A predefined format name (e.g., "uuid4",
                "email", "bearer_token") that the header value must match.
                Cannot be used with `pattern`.
            allowed_values (Optional[List[str]]): A list of exact string
                values that are allowed for the header.
            validator (Optional[Callable[[str], bool]]): A custom callable that
                receives the header value and returns `True` if valid, or
                `False` (or raises an Exception) if invalid.
            title (Optional[str]): A title for the header in OpenAPI docs.
            description (Optional[str]): A description for the header in
                OpenAPI docs.
            **header_kwargs (Any): Additional keyword arguments passed to the
                parent `BaseValidator` (for error handling) and the
                underlying `fastapi.Header` dependency.
                Includes `status_code` (default 400) and `error_detail`
                (default "Header Validation Failed") for error responses.

        Raises:
            ValueError: If both `pattern` and `format` are specified, or if
                an unknown `format` name is provided.
        """
        header_kwargs["status_code"] = header_kwargs.get("status_code", 400)
        header_kwargs["error_detail"] = header_kwargs.get(
            "error_detail", "Header Validation Failed"
        )
        # Call super() with default error handling
        super().__init__(**header_kwargs)

        self._required = required

        # Store validation rules
        self._allowed_values = allowed_values
        self._custom_validator = validator

        # Define type hints for attributes
        self._pattern: Optional[Pattern[str]] = None
        self._format_name: Optional[str] = None

        # Handle pattern and format keys
        if pattern and format:
            raise ValueError("Cannot specify both 'pattern' and 'format'. Choose one.")

        if format:
            if format not in _FORMAT_PATTERNS:
                raise ValueError(
                    f"Unknown format '{format}'. "
                    f"Available formats: {', '.join(_FORMAT_PATTERNS.keys())}"
                )
            self._pattern = re.compile(_FORMAT_PATTERNS[format], re.IGNORECASE)
            self._format_name = format
        elif pattern:
            self._pattern = re.compile(pattern)
            self._format_name = None
        else:
            self._pattern = None
            self._format_name = None

        # Store the underlying FastAPI Header parameter
        self._header_param = Header(
            default,
            alias=alias,
            convert_underscores=convert_underscores,
            title=title,
            description=description,
            **header_kwargs,
        )

    def __call__(self, header_value: Optional[str] = None) -> Any:
        """
        FastAPI dependency entry point for header validation.

        Args:
            header_value: The header value extracted from the request.

        Returns:
            The validated header value.

        Raises:
            HTTPException: If validation fails.
        """
        # If value is None, return a dependency that FastAPI will use
        if header_value is None:

            def dependency(value: Optional[str] = self._header_param) -> Optional[str]:
                return self._validate(value)

            return dependency

        # If value is provided (for testing), validate directly
        return self._validate(header_value)

    def _validate(self, value: Optional[str]) -> Optional[str]:
        """
        Runs all validation checks on the header value.

        Args:
            value: The header value to validate.

        Returns:
            The validated value.

        Raises:
            HTTPException: If any validation check fails.
        """
        try:
            self._validate_required(value)
        except ValidationError as e:
            self._raise_error(value=value, status_code=e.status_code, detail=str(e.detail))
        if value is None or value == "":
            return value or ""
        try:
            self._validate_allowed_values(value)
            self._validate_pattern(value)
            self._validate_custom(value)

        except ValidationError as e:
            # Convert ValidationError to HTTPException
            self._raise_error(value=value, status_code=e.status_code, detail=str(e.detail))

        return value

    def _validate_required(self, value: Optional[str]) -> None:
        """
        Checks if the header is present when required.

        Args:
            value: The header value to check.

        Raises:
            ValidationError: If the header is required but missing.
        """
        if self._required and (value is None or value == ""):
            detail = "Required header is missing."
            if callable(detail):
                detail_str = detail(value)
            else:
                detail_str = str(detail)

            raise ValidationError(detail=detail_str, status_code=400)

    def _validate_allowed_values(self, value: str) -> None:
        """
        Checks if the value is in the list of allowed values.

        Args:
            value: The header value to check.

        Raises:
            ValidationError: If the value is not in allowed_values.
        """
        if self._allowed_values is None:
            return  # No validation rule set

        if value not in self._allowed_values:
            detail = (
                f"Header value '{value}' is not allowed. "
                f"Allowed values are: {', '.join(self._allowed_values)}"
            )
            raise ValidationError(detail=detail, status_code=400)

    def _validate_pattern(self, value: str) -> None:
        """
        Checks if the header value matches the required regex pattern.

        Args:
            value: The header value to check.

        Raises:
            ValidationError: If the value doesn't match the pattern.
        """
        if self._pattern is None:
            return  # No validation rule set

        if not self._pattern.match(value):
            if self._format_name:
                detail = f"Header value does not match the required format: '{self._format_name}'"
            else:
                detail = (
                    f"Header value '{value}' does not match the required pattern: "
                    f"{self._pattern.pattern}"
                )
            raise ValidationError(detail=detail, status_code=400)

    def _validate_custom(self, value: str) -> None:
        """
        Runs a custom validation function if provided.

        Args:
            value: The header value to check.

        Raises:
            ValidationError: If the custom validator returns False or raises an exception.
        """
        if self._custom_validator is None:
            return  # No custom validator set

        try:
            if not self._custom_validator(value):
                detail = f"Custom validation failed for header value '{value}'"
                raise ValidationError(detail=detail, status_code=400)
        except Exception as e:
            # If the validator itself raises an exception, catch it
            detail = f"Custom validation error: {str(e)}"
            raise ValidationError(detail=detail, status_code=400)
