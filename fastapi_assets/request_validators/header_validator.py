"""HeaderValidator for validating HTTP headers in FastAPI."""

from inspect import Signature, Parameter
import re
from typing import Any, Callable, Dict, List, Optional, Pattern
from fastapi import Header
from fastapi.param_functions import _Unset

from fastapi_assets.core import BaseValidator, ValidationError

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
    A dependency for validating HTTP headers with extended rules.

    Extends FastAPI's `Header` with pattern matching, format validation,
    allowed values, and custom validators, providing granular error control.

    Example:
    .. code-block:: python
        from fastapi import FastAPI, Depends
        from fastapi_assets.request_validators import HeaderValidator

        app = FastAPI()

        def is_valid_api_version(version: str) -> bool:
            # Custom validators must raise ValidationError on failure
            if version not in ["v1", "v2", "v3"]:
                raise ValidationError(detail="Unsupported API version.")

        # Validate required API key header with a specific pattern.
        # HeaderValidator extracts the header from the incoming request automatically.
        api_key_validator = HeaderValidator(
            alias="X-API-Key",
            pattern=r"^[a-zA-Z0-9]{32}$",
            on_required_error_detail="X-API-Key header is missing.",
            on_pattern_error_detail="Invalid API key format."
        )

        # Validate required authorization header with bearer token format.
        # The header is extracted from request.headers by the Header() dependency.
        auth_validator = HeaderValidator(
            alias="Authorization",
            format="bearer_token",
            on_required_error_detail="Authorization header is required.",
            on_pattern_error_detail="Invalid Bearer token format."
        )

        # Validate optional custom header with custom validator and a default.
        # If not provided, the default value "v1" will be used.
        version_validator = HeaderValidator(
            alias="X-API-Version",
            default="v1",
            validators=[is_valid_api_version],
            on_custom_validator_error_detail="Invalid API version."
        )

        @app.get("/secure")
        async def secure_endpoint(
            api_key: str = Depends(api_key_validator),
            auth: str = Depends(auth_validator),
            version: str = Depends(version_validator)
        ):
            # Each dependency automatically extracts and validates the corresponding header,
            # returning the validated value to the endpoint
            return {"message": "Access granted", "version": version}
        ```
    """

    def __init__(
        self,
        default: Any = Undefined,
        *,
        alias: Optional[str] = None,
        convert_underscores: bool = True,
        pattern: Optional[str] = None,
        format: Optional[str] = None,
        allowed_values: Optional[List[str]] = None,
        validators: Optional[List[Callable[[Any], Any]]] = None,
        # Standard Header parameters
        title: Optional[str] = None,
        description: Optional[str] = None,
        # Granular Error Messages
        on_required_error_detail: str = "Required header is missing.",
        on_pattern_error_detail: str = "Header has an invalid format.",
        on_allowed_values_error_detail: str = "Header value is not allowed.",
        on_custom_validator_error_detail: str = "Header failed custom validation.",
        # Base Error
        status_code: int = 400,
        error_detail: str = "Header Validation Failed",
        **header_kwargs: Any,
    ) -> None:
        """
        Initializes the HeaderValidator instance.

        Args:
            default (Any): The default value if the header is not provided.
                If not set (or set to `Undefined`), the header is required.
            alias (Optional[str]): The alias of the header (the actual
                header name, e.g., "X-API-Key").
            convert_underscores (bool): If `True` (default), underscores in
                the variable name will be converted to hyphens in the header name.
            pattern (Optional[str]): A regex pattern string that the header
                value must match.
            format (Optional[str]): A predefined format name (e.g., "uuid4").
                Cannot be used with `pattern`.
            allowed_values (Optional[List[str]]): A list of exact string
                values that are allowed for the header.
            validators (Optional[List[Callable]]): A list of custom validation
                functions (sync or async) that receive the header value.
            title (Optional[str]): A title for the header in OpenAPI docs.
            description (Optional[str]): A description for the header in
                OpenAPI docs.
            on_required_error_detail (str): Error message if header is missing.
            on_pattern_error_detail (str): Error message if pattern/format fails.
            on_allowed_values_error_detail (str): Error message if value not allowed.
            on_custom_validator_error_detail (str): Error message if custom validator fails.
            status_code (int): The default HTTP status code for validation errors.
            error_detail (str): A generic fallback error message.
            **header_kwargs (Any): Additional keyword arguments passed to FastAPI's Header().
        """

        super().__init__(status_code=status_code, error_detail=error_detail, validators=validators)

        # Store "required" status based on the default value
        self._is_required = default is Undefined

        # Store validation rules
        self._allowed_values = allowed_values
        self._custom_validators: list[Callable[..., Any]] = validators or []

        # Store error messages
        self._on_required_error_detail = on_required_error_detail
        self._on_pattern_error_detail = on_pattern_error_detail
        self._on_allowed_values_error_detail = on_allowed_values_error_detail
        self._on_custom_validator_error_detail = on_custom_validator_error_detail

        self._pattern_str: Optional[str] = None
        self._compiled_pattern: Optional[Pattern[str]] = None

        if pattern and format:
            raise ValueError("Cannot specify both 'pattern' and 'format'.")

        if format:
            self._pattern_str = _FORMAT_PATTERNS.get(format)
            if self._pattern_str is None:
                raise ValueError(
                    f"Unknown format '{format}'. Available: {list(_FORMAT_PATTERNS.keys())}"
                )
            # Use IGNORECASE for format matching (e.g., UUIDs)
            self._compiled_pattern = re.compile(self._pattern_str, re.IGNORECASE)
        elif pattern:
            self._pattern_str = pattern
            self._compiled_pattern = re.compile(self._pattern_str)

        # We pass `None` if the header is required (default=Undefined)
        # to bypass FastAPI's default 422, allowing our validator to run
        # and use the custom error message.
        fastapi_header_default = None if self._is_required else default

        self._header_param = Header(
            fastapi_header_default,
            alias=alias,
            convert_underscores=convert_underscores,
            title=title,
            description=description,
            **header_kwargs,
        )

        # Dynamically set the __call__ method's signature so FastAPI recognizes
        # the Header() dependency and injects the header value correctly.
        # This is necessary because we need to pass self._header_param as the default,
        # which isn't available at class definition time.
        self._set_call_signature()

    def _set_call_signature(self) -> None:
        """
        Sets the __call__ method's signature so FastAPI's dependency injection
        system recognizes the Header() parameter and extracts the header value.
        """

        # Create a new signature with self and header_value parameters
        # The header_value parameter has self._header_param as its default
        # so FastAPI will use Header() to extract it from the request
        sig = Signature(
            [
                Parameter("self", Parameter.POSITIONAL_OR_KEYWORD),
                Parameter(
                    "header_value",
                    Parameter.KEYWORD_ONLY,
                    default=self._header_param,
                    annotation=Optional[str],
                ),
            ]
        )

        # Set the signature on the underlying function, not the bound method
        # Access the function object from the method
        self.__call__.__func__.__signature__ = sig  # type: ignore

    async def __call__(self, header_value: Optional[str] = None) -> Optional[str]:
        """
        FastAPI dependency entry point for header validation.

        FastAPI automatically injects the header value by recognizing the
        Header() dependency in the method signature (set via _set_call_signature).
        This method then validates the extracted header value and returns it
        or raises an HTTPException with a custom error message.

        Args:
            header_value: The header value extracted from the request by FastAPI.
                         Will be None if the header is not present.

        Returns:
            Optional[str]: The validated header value, or None if the header is
                          optional and not present.

        Raises:
            HTTPException: If validation fails, with the configured status code
                          and error message.
        """
        try:
            # Validate the header value (which FastAPI injected via Header())
            return await self._validate(header_value)
        except ValidationError as e:
            # Convert our internal error to an HTTPException
            self._raise_error(status_code=e.status_code, detail=str(e.detail))
            return None  # pragma: no cover (unreachable)

    async def _validate(self, value: Optional[str]) -> Optional[str]:
        """
        Runs all configured validation checks on the header value.

        Checks if the header is required, validates allowed values, pattern matching,
        and custom validators in sequence.

        Args:
            value: The header value to validate (None if not present).

        Returns:
            Optional[str]: The validated header value, or None if optional and not present.

        Raises:
            ValidationError: If any validation check fails.
        """
        # 1. Check if required and not present
        self._validate_required(value)

        # 2. If optional and not present, return None
        # (It passed _validate_required, so if value is None, it's optional)
        if value is None:
            return None

        # 3. Run all other validations on the present value
        self._validate_allowed_values(value)
        self._validate_pattern(value)
        await self._validate_custom(value)

        return value

    def _validate_required(self, value: Optional[str]) -> None:
        """
        Checks if the header is present when required.

        Args:
            value: The header value (None if not present).

        Returns:
            None

        Raises:
            ValidationError: If the header is required but missing or empty.
        """
        if self._is_required and (value is None or value == ""):
            raise ValidationError(
                detail=self._on_required_error_detail, status_code=self._status_code
            )

    def _validate_allowed_values(self, value: str) -> None:
        """
        Checks if the header value is in the list of allowed values.

        Args:
            value: The header value to validate.

        Returns:
            None

        Raises:
            ValidationError: If the value is not in the allowed list.
        """
        if self._allowed_values is None:
            return

        if value not in self._allowed_values:
            detail = (
                f"{self._on_allowed_values_error_detail} "
                f"Allowed values are: {', '.join(self._allowed_values)}"
            )
            raise ValidationError(detail=detail, status_code=self._status_code)

    def _validate_pattern(self, value: str) -> None:
        """
        Checks if the header value matches the configured regex pattern.

        Args:
            value: The header value to validate.

        Returns:
            None

        Raises:
            ValidationError: If the value doesn't match the pattern.
        """
        if self._compiled_pattern is None:
            return

        if not self._compiled_pattern.fullmatch(value):
            raise ValidationError(
                detail=self._on_pattern_error_detail, status_code=self._status_code
            )
