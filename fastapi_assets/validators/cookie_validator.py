"""
Module providing the CookieAssert class for validating cookie parameters in FastAPI.
"""

import re
from typing import Any, Callable, Dict, Optional, Pattern

from fastapi import HTTPException, Request, status
from fastapi_assets.core.base_validator import (  # Assuming this path from your structure
    BaseValidator,
    ValidationError,
)

# --- Pre-built Regex Patterns ---

# Regex patterns for common formats, accessible via the 'format' parameter.
PRE_BUILT_PATTERNS: Dict[str, str] = {
    # 3 parts, Base64-URL encoded, separated by dots.
    "jwt": r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*$",
    # Standard UUIDv4. Note the '4' in the third group.
    "uuid4": r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-4[a-fA-F0-9]{3}-[89abAB][a-fA-F0-9]{3}-[a-fA-F0-9]{12}$",
    # Basic email pattern.
    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    # Bearer token format.
    "bearer_token": r"^[Bb]earer [A-Za-z0-9\._~\+\/=-]+$",
    # ISO 8601 Datetime format (e.g., 2025-11-01T15:30:00Z).
    "datetime": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$",
    # A common format for simple session IDs.
    "session_id": r"^[A-Za-z0-9-_]{16,128}$",
}


# --- Validator Class ---


class CookieAssert(BaseValidator):
    """
    A class-based dependency for validating cookies in FastAPI.

    This class enhances FastAPI's built-in `Cookie()` by providing granular,
    per-rule error messages and convenient pre-built validation formats.

    It is designed to be instantiated as a dependency that is injected
    into your path operation functions.

    Raises:
        ValueError: On __init__ if configuration is invalid (e.g.,
                    using 'format' and 'regex' simultaneously).
        HTTPException: On __call__ if any validation rule fails.

    Example:
        ```python
        from fastapi import FastAPI
        from fastapi_assets.validators.cookie_validator import CookieAssert

        app = FastAPI()

        # Define a reusable validator for a required session ID
        validate_session = CookieAssert(
            alias="session-id",
            required=True,
            format="uuid4",
            on_required_error_detail="Session cookie is missing.",
            on_pattern_error_detail="Invalid session ID format."
        )

        @app.get("/user/me")
        async def get_user_me(session: str = Depends(validate_session)):
            # This code only runs if the cookie is present and valid
            return {"session_id": session}
        ```
    """

    def __init__(
        self,
        *,
        alias: str,
        default: Any = ...,
        required: Optional[bool] = None,
        # Numeric validation
        gt: Optional[float] = None,
        ge: Optional[float] = None,
        lt: Optional[float] = None,
        le: Optional[float] = None,
        # Length validation
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        # Pattern validation
        regex: Optional[str] = None,
        format: Optional[str] = None,
        # Custom validation
        validator: Optional[Callable[[Any], bool]] = None,
        # Error messages
        on_required_error_detail: Optional[str] = None,
        on_numeric_error_detail: Optional[str] = None,
        on_comparison_error_detail: Optional[str] = None,
        on_length_error_detail: Optional[str] = None,
        on_pattern_error_detail: Optional[str] = None,
        on_validator_error_detail: Optional[str] = None,
    ):
        """
        Initializes the CookieAssert validator.

        Args:
            alias (str): The exact name (key) of the cookie. This is required.
            default (Any, optional): The default value if the cookie is not
                present. If '...' (Ellipsis), the cookie is required.
            required (Optional[bool], optional): Explicitly mark the cookie as
                required (True) or not (False). Overrides 'default'.
            gt (Optional[float], optional): Value must be "greater than".
            ge (Optional[float], optional): Value must be "greater than or equal to".
            lt (Optional[float], optional): Value must be "less than".
            le (Optional[float], optional): Value must be "less than or equal to".
            min_length (Optional[int], optional): String must be at least this long.
            max_length (Optional[int], optional): String must be at most this long.
            regex (Optional[str], optional): A custom regex pattern to match.
            format (Optional[str], optional): Name of a pre-built regex
                pattern (e.g., "uuid4", "email").
            validator (Optional[Callable[[Any], bool]], optional): A custom
                function that receives the value and returns True if valid.
            on_required_error_detail (Optional[str], optional): Custom error
                message if a required cookie is missing.
            on_numeric_error_detail (Optional[str], optional): Custom error
                message if the value is not a valid number.
            on_comparison_error_detail (Optional[str], optional): Custom error
                message if numeric comparisons (gt, lt) fail.
            on_length_error_detail (Optional[str], optional): Custom error
                message if length validation (min_length, max_length) fails.
            on_pattern_error_detail (Optional[str], optional): Custom error
                message if regex/format validation fails.
            on_validator_error_detail (Optional[str], optional): Custom error
                message if the custom 'validator' function fails.
        """
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_detail="Cookie validation failed.",
        )

        # Store required params
        self.alias = alias
        self.default = default

        # Determine if the cookie is required
        if required is True:
            self.is_required = True
        elif required is False:
            self.is_required = False
        else:
            # If 'required' is not set, infer from 'default'
            self.is_required = default is ...

        # Store numeric validation rules
        self.gt = gt
        self.ge = ge
        self.lt = lt
        self.le = le

        # Store length validation rules
        self.min_length = min_length
        self.max_length = max_length

        # Store custom validator
        self.custom_validator = validator

        # Store specific error details
        self.err_required = (
            on_required_error_detail or "Cookie is required."
        )
        self.err_numeric = (
            on_numeric_error_detail or "Cookie value must be a valid number."
        )
        self.err_comparison = (
            on_comparison_error_detail or "Cookie value is not in the allowed range."
        )
        self.err_length = (
            on_length_error_detail or "Cookie value has an invalid length."
        )
        self.err_pattern = (
            on_pattern_error_detail or "Cookie value has an invalid format."
        )
        self.err_validator = (
            on_validator_error_detail or "Cookie failed custom validation."
        )

        # --- Compile Regex ---
        if format and regex:
            raise ValueError("Cannot use 'format' and 'regex' simultaneously.")

        self.final_regex: Optional[Pattern] = None
        self.final_regex_str = regex or PRE_BUILT_PATTERNS.get(format)

        if self.final_regex_str:
            if (
                format
                and format not in PRE_BUILT_PATTERNS
            ):
                raise ValueError(
                    f"Unknown format '{format}'. Available formats: "
                    f"{list(PRE_BUILT_PATTERNS.keys())}"
                )
            self.final_regex = re.compile(self.final_regex_str)

    async def __call__(self, request: Request) -> Optional[Any]:
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
            Optional[Any]: The validated cookie value. This will be a `float`
                           if numeric comparisons were used, otherwise a `str`.
                           Returns `None` or the `default` value if not required
                           and not present.
        """
        try:
            # 0. Check for misconfiguration
            if not self.alias:
                raise ValidationError(
                    detail="Internal Server Error: `CookieAssert` must be initialized with an `alias`.",
                    status_code=500,
                )

            cookie_value = request.cookies.get(self.alias)

            # 1. Check for required
            if cookie_value is None:
                if self.is_required:
                    raise ValidationError(detail=self.err_required, status_code=400)
                # Not required and not present, return default
                return self.default if self.default is not ... else None

            # 2. Check numeric and comparison (if rules exist)
            numeric_value = self._validate_numeric(cookie_value)
            if numeric_value is not None:
                self._validate_comparison(numeric_value)

            # 3. Check length (if rules exist)
            self._validate_length(cookie_value)

            # 4. Check pattern (if rule exists)
            self._validate_pattern(cookie_value)

            # 5. Check custom validator (if rule exists)
            self._validate_custom(cookie_value)

            # All checks passed, return the validated value
            return numeric_value if numeric_value is not None else cookie_value

        except ValidationError as e:
            # This is our controlled validation error
            self._raise_error(
                value=cookie_value,
                status_code=e.status_code,
                detail=e.detail,
            )
        except HTTPException:
            # Re-raise HTTPExceptions (e.g., from _raise_error) directly
            raise
        except Exception as e:
            # This is an unexpected server error
            self._raise_error(
                status_code=500,
                detail=f"An unexpected error occurred during cookie validation: {e}",
            )

    # --- Validation Helper Methods ---

    def _validate_numeric(self, value: str) -> Optional[float]:
        """
        Checks if value is numeric, if rules (gt, ge, lt, le) exist.

        Raises:
            ValidationError: If rules exist and value is not a valid number.
        """
        # Only validate as a number if comparison rules are set
        if any(v is not None for v in [self.gt, self.ge, self.lt, self.le]):
            try:
                return float(value)
            except (ValueError, TypeError):
                raise ValidationError(detail=self.err_numeric, status_code=400)
        return None

    def _validate_comparison(self, value: float) -> None:
        """
        Runs numeric comparison checks (gt, ge, lt, le).

        Raises:
            ValidationError: If any comparison fails.
        """
        if self.gt is not None and not value > self.gt:
            raise ValidationError(detail=self.err_comparison, status_code=400)
        if self.ge is not None and not value >= self.ge:
            raise ValidationError(detail=self.err_comparison, status_code=400)
        if self.lt is not None and not value < self.lt:
            raise ValidationError(detail=self.err_comparison, status_code=400)
        if self.le is not None and not value <= self.le:
            raise ValidationError(detail=self.err_comparison, status_code=400)

    def _validate_length(self, value: str) -> None:
        """
        Runs string length checks (min_length, max_length).

        Raises:
            ValidationError: If length is outside the bounds.
        """
        value_len = len(value)
        if self.min_length is not None and value_len < self.min_length:
            raise ValidationError(detail=self.err_length, status_code=400)
        if self.max_length is not None and value_len > self.max_length:
            raise ValidationError(detail=self.err_length, status_code=400)

    def _validate_pattern(self, value: str) -> None:
        """
        Runs regex pattern matching.

        Raises:
            ValidationError: If the pattern does not match.
        """
        if self.final_regex and not self.final_regex.search(value):
            raise ValidationError(detail=self.err_pattern, status_code=400)

    def _validate_custom(self, value: str) -> None:
        """
        Runs the custom validator function.

        Raises:
            ValidationError: If the function returns False or raises an Exception.
        """
        if self.custom_validator:
            try:
                if not self.custom_validator(value):
                    raise ValidationError(detail=self.err_validator, status_code=400)
            except ValidationError:
                # Re-raise our own validation errors
                raise
            except Exception as e:
                # Wrap any other exception
                raise ValidationError(
                    detail=f"{self.err_validator}: {e}", status_code=400
                )

