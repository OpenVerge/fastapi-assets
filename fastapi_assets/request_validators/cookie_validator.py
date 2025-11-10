"""FastAPI cookie validation with reusable dependencies."""

import inspect
import re
from typing import Any, Callable, Dict, List, Optional, Union
from fastapi import Request, status
from fastapi_assets.core import BaseValidator, ValidationError


# Pre-built regex patterns for the `format` parameter
PRE_BUILT_PATTERNS: Dict[str, str] = {
    "session_id": r"^[A-Za-z0-9_-]{16,128}$",
    "uuid4": r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-4[a-fA-F0-9]{3}-[89abAB][a-fA-F0-9]{3}-[a-fA-F0-9]{12}$",
    "bearer_token": r"^[Bb]earer [A-Za-z0-9\._~\+\/=-]+$",
    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "datetime": r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|([+-]\d{2}:\d{2}))?$",
}


class CookieValidator(BaseValidator):
    """
    A class-based dependency to validate FastAPI Cookies with granular control.

    This class is instantiated as a re-usable dependency that can be
    injected into FastAPI endpoints using `Depends()`. It provides fine-grained
    validation rules and specific error messages for each rule.

    Example:
        ```python
        from fastapi import FastAPI, Depends
        from fastapi_assets.core import ValidationError
        from fastapi_assets.request_validators import CookieValidator

        app = FastAPI()

        def is_whitelisted(user_id: str) -> None:
            # Logic to check if user_id is in a whitelist.
            # Custom validators must raise ValidationError on failure.
            if user_id not in {"user_1", "user_2"}:
                raise ValidationError("User is not whitelisted.")

        # Create validators that will extract cookies from the incoming request
        validate_session = CookieValidator(
            "session-id",  # Cookie name to extract from request.cookies
            format="uuid4",
            on_required_error_detail="Invalid or missing session ID.",
            on_pattern_error_detail="Session ID must be a valid UUIDv4."
        )

        validate_user = CookieValidator(
            "user-id",  # Cookie name to extract from request.cookies
            min_length=6,
            validators=[is_whitelisted],
            on_length_error_detail="User ID must be at least 6 characters.",
            on_validator_error_detail="User is not whitelisted."
        )

        @app.get("/items/")
        async def read_items(session_id: str = Depends(validate_session)):
            # validate_session extracts the "session-id" cookie from the request,
            # validates it, and returns the validated value
            return {"session_id": session_id}

        @app.get("/users/me")
        async def read_user(user_id: str = Depends(validate_user)):
            # validate_user extracts the "user-id" cookie from the request,
            # validates it (including length and custom validators), and returns it
            return {"user_id": user_id}
        ```
    """

    def __init__(
        self,
        alias: str,
        *,
        # Core Parameters
        default: Any = ...,
        required: Optional[bool] = None,
        # Validation Rules
        gt: Optional[float] = None,
        ge: Optional[float] = None,
        lt: Optional[float] = None,
        le: Optional[float] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        regex: Optional[str] = None,
        pattern: Optional[str] = None,
        format: Optional[str] = None,
        validators: Optional[List[Callable[[Any], Any]]] = None,
        # Granular Error Messages
        on_required_error_detail: str = "Cookie is required.",
        on_numeric_error_detail: str = "Cookie value must be a number.",
        on_comparison_error_detail: str = "Cookie value fails comparison rules.",
        on_length_error_detail: str = "Cookie value fails length constraints.",
        on_pattern_error_detail: str = "Cookie has an invalid format.",
        on_validator_error_detail: str = "Cookie failed custom validation.",
        # Base Error
        status_code: int = 400,
        error_detail: str = "Cookie validation failed.",
    ) -> None:
        """
        Initializes the CookieAssert validator.

        Args:
            alias (str): (Required) The exact, case-sensitive name of the
                         cookie (e.g., "session-id").
            default (Any): The default value to return if the cookie is not
                           present. If not set, `required` defaults to `True`.
            required (Optional[bool]): Explicitly set to `True` or `False`. Overrides
                                     `default` for determining if a cookie is required.
            gt (Optional[float]): "Greater than" numeric comparison.
            ge (Optional[float]): "Greater than or equal to" numeric comparison.
            lt (Optional[float]): "Less than" numeric comparison.
            le (Optional[float]): "Less than or equal to" numeric comparison.
            min_length (Optional[int]): Minimum string length.
            max_length (Optional[int]): Maximum string length.
            regex (Optional[str]): Custom regex pattern.
            pattern (Optional[str]): Alias for `regex`.
            format (Optional[str]): A key from `PRE_BUILT_PATTERNS` (e.g., "uuid4").
            validators (Optional[List[Callable]]): A list of custom validation
                                                  functions (sync or async).
            on_required_error_detail (str): Error for missing required cookie.
            on_numeric_error_detail (str): Error for float conversion failure.
            on_comparison_error_detail (str): Error for gt/ge/lt/le failure.
            on_length_error_detail (str): Error for min/max length failure.
            on_pattern_error_detail (str): Error for regex/format failure.
            on_validator_error_detail (str): Error for custom validator failure.
            status_code (int): The default HTTP status code to raise on failure.
            error_detail (str): A generic fallback error message.

        Raises:
            ValueError: If `regex`/`pattern` and `format` are used simultaneously.
            ValueError: If an unknown `format` key is provided.
        """
        super().__init__(status_code=status_code, error_detail=error_detail, validators=validators)

        # Store Core Parameters
        self.alias = alias
        self.default = default

        if required is not None:
            self.is_required = required  # Use explicit value if provided
        else:
            # Infer from default only if 'required' was not set
            self.is_required = default is ...

        # Store Validation Rules
        self.gt: Optional[float] = gt
        self.ge: Optional[float] = ge
        self.lt: Optional[float] = lt
        self.le: Optional[float] = le
        self.min_length: Optional[int] = min_length
        self.max_length: Optional[int] = max_length
        self.custom_validators = validators

        # Store Error Messages
        self.err_required: str = on_required_error_detail
        self.err_numeric: str = on_numeric_error_detail
        self.err_compare: str = on_comparison_error_detail
        self.err_length: str = on_length_error_detail
        self.err_pattern: str = on_pattern_error_detail
        self.err_validator: str = on_validator_error_detail

        # Handle Regex/Pattern
        self.final_regex_str: Optional[str] = regex or pattern
        if self.final_regex_str and format:
            raise ValueError("Cannot use 'regex'/'pattern' and 'format' simultaneously.")
        if format:
            if format not in PRE_BUILT_PATTERNS:
                raise ValueError(
                    f"Unknown format: '{format}'. Available: {list(PRE_BUILT_PATTERNS.keys())}"
                )
            self.final_regex_str = PRE_BUILT_PATTERNS[format]

        self.final_regex: Optional[re.Pattern[str]] = (
            re.compile(self.final_regex_str) if self.final_regex_str else None
        )

    def _validate_numeric(self, value: str) -> Optional[float]:
        """
        Tries to convert value to float. Returns float or None.

        This check is only triggered if gt, ge, lt, or le are set.
        Args:
            value (str): The cookie value to convert.
        Returns:
            Optional[float]: The converted float value, or None if numeric checks
                             are not applicable.
        Raises:
            ValidationError: If conversion to float fails.
        """
        if any(v is not None for v in [self.gt, self.ge, self.lt, self.le]):
            try:
                return float(value)
            except (ValueError, TypeError):
                raise ValidationError(
                    detail=self.err_numeric,
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        return None

    def _validate_comparison(self, value: float) -> None:
        """
        Checks gt, ge, lt, le rules against a numeric value.

        Args:
            value (float): The numeric value to compare.
        Returns:
            None
        Raises:
            ValidationError: If any comparison fails.
        """
        if self.gt is not None and not value > self.gt:
            raise ValidationError(
                detail=self.err_compare,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if self.ge is not None and not value >= self.ge:
            raise ValidationError(
                detail=self.err_compare,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if self.lt is not None and not value < self.lt:
            raise ValidationError(
                detail=self.err_compare,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if self.le is not None and not value <= self.le:
            raise ValidationError(
                detail=self.err_compare,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    def _validate_length(self, value: str) -> None:
        """
        Checks min_length and max_length rules.

        Args:
            value (str): The cookie value to check.

        Returns:
            None

        Raises:
            ValidationError: If length constraints fail.
        """
        value_len = len(value)
        if self.min_length is not None and value_len < self.min_length:
            raise ValidationError(
                detail=self.err_length,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if self.max_length is not None and value_len > self.max_length:
            raise ValidationError(
                detail=self.err_length,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    def _validate_pattern(self, value: str) -> None:
        """
        Checks regex/format pattern rule.
        Args:
            value (str): The cookie value to check.
        Returns:
            None

        Raises:
            ValidationError: If the regex pattern does not match.
        """
        if self.final_regex and not self.final_regex.search(value):
            raise ValidationError(
                detail=self.err_pattern,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    async def _validate(self, cookie_value: Optional[str]) -> Union[float, str, None]:
        """
        Pure validation logic (testable without FastAPI).

        This async method runs all validation checks in order.

        Args:
            cookie_value: The cookie value to validate.

        Returns:
            Union[float, str, None]: The validated value (float if numeric,
            str otherwise, or None if not required).

        Raises:
            ValidationError: If any validation check fails.
        """
        # 1. Check for required
        if cookie_value is None:
            if self.is_required:
                raise ValidationError(
                    detail=self.err_required,
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            return self.default if self.default is not ... else None

        # 2. Check numeric and comparison
        numeric_value = self._validate_numeric(cookie_value)
        if numeric_value is not None:
            self._validate_comparison(numeric_value)

        # 3. Check length
        self._validate_length(cookie_value)

        # 4. Check pattern
        self._validate_pattern(cookie_value)

        # 5. Check custom validators (both sync and async)
        await self._validate_custom(cookie_value)

        # Return the float value if numeric checks were run,
        # otherwise return the original string value.
        return numeric_value if numeric_value is not None else cookie_value

    async def __call__(self, request: Request) -> Union[float, str, None]:
        """
        FastAPI dependency entry point.

        This method is called by FastAPI's dependency injection system.
        It retrieves the cookie from the request and runs all validation logic.

        Args:
            request (Request): The incoming FastAPI request object.

        Raises:
            HTTPException: If any validation fails, this is raised with
                           the specific status code and detail message.

        Returns:
            Union[float, str, None]: The validated cookie value. This will be a
            `float` if numeric comparisons were used, otherwise a `str`.
            Returns `None` or the `default` value if not required and not present.
        """
        try:
            # Extract cookie value from request
            cookie_value: Optional[str] = request.cookies.get(self.alias)
            # Run all validation logic
            return await self._validate(cookie_value)

        except ValidationError as e:
            # Convert validation error to HTTP exception
            self._raise_error(detail=e.detail, status_code=e.status_code)
            return None  # pragma: no cover
