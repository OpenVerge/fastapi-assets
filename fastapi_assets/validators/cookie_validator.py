"""
fastapi-asserts: Cookie Validation Module
========================================

This module provides the `CookieAssert` class, a robust, class-based
dependency for validating FastAPI Cookies with granular error control.
"""

import re
from typing import Any, Callable, Dict, Optional
from fastapi import Request, status, HTTPException

# Import the base classes from the core module
# (Assuming BaseValidator and ValidationError are in a parent/sibling dir)
try:
    from ..core.base_validator import BaseValidator, ValidationError
except ImportError:
    # Fallback for when run as a standalone script
    import abc
    
    class ValidationError(Exception):
        """Custom exception for internal validation failures."""
        def __init__(self, detail: str, status_code: int):
            self.detail = detail
            self.status_code = status_code
            super().__init__(detail)

    class BaseValidator(abc.ABC):
        """Abstract base class for all validators."""
        def __init__(
            self,
            status_code: int = status.HTTP_400_BAD_REQUEST,
            error_detail: Optional[str] = "Validation failed.",
        ):
            self.status_code = status_code
            self.error_detail = error_detail

        def _raise_error(
            self, detail: Optional[str] = None, status_code: Optional[int] = None
        ) -> None:
            """Raises the final HTTPException."""
            raise HTTPException(
                status_code=status_code or self.status_code,
                detail=detail or self.error_detail,
            )


# Pre-built regex patterns for the `format` parameter
PRE_BUILT_PATTERNS: Dict[str, str] = {
    "session_id": r"^[A-Za-z0-9_-]{16,128}$",
    "uuid4": r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-4[a-fA-F0-9]{3}-[89abAB][a-fA-F0-9]{3}-[a-fA-F0-9]{12}$",
    "bearer_token": r"^[Bb]earer [A-Za-z0-9\._~\+\/=-]+$",
    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "datetime": r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|([+-]\d{2}:\d{2}))?$",
}

class CookieAssert(BaseValidator):
    """
    A class-based dependency to validate FastAPI Cookies with granular control.
    
    This class is instantiated as a re-usable dependency that can be
    injected into FastAPI endpoints using `Depends()`. It provides fine-grained
    validation rules and specific error messages for each rule.

    Example:
        ```python
        from fastapi import FastAPI, Depends
        # from fastapi_assets.validators.cookie_validator import CookieAssert
        
        app = FastAPI()
        
        validate_session = CookieAssert(
            alias="session-id", 
            format="uuid4",
            on_required_error_detail="Invalid or missing session ID.",
            on_pattern_error_detail="Session ID must be a valid UUIDv4."
        )
        
        @app.get("/items/")
        async def read_items(session_id: str = Depends(validate_session)):
            return {"session_id": session_id}
        ```
    """
    def __init__(
        self,
        *,
        # --- Core Parameters ---
        alias: str,
        default: Any = ...,
        required: Optional[bool] = None,

        # --- Validation Rules ---
        gt: Optional[float] = None,
        ge: Optional[float] = None,
        lt: Optional[float] = None,
        le: Optional[float] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        regex: Optional[str] = None,
        pattern: Optional[str] = None,
        format: Optional[str] = None,
        validator: Optional[Callable[[Any], bool]] = None,

        # --- Granular Error Messages ---
        on_required_error_detail: Optional[str] = "Cookie is required.",
        on_numeric_error_detail: Optional[str] = "Cookie value must be a number.",
        on_comparison_error_detail: Optional[str] = "Cookie value fails comparison rules.",
        on_length_error_detail: Optional[str] = "Cookie value fails length constraints.",
        on_pattern_error_detail: Optional[str] = "Cookie has an invalid format.",
        on_validator_error_detail: Optional[str] = "Cookie failed custom validation.",

        # --- Base Error ---
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_detail: Optional[str] = "Cookie validation failed.",
    ):
        """
        Initializes the CookieAssert validator.

        Args:
            alias (str): (Required) The exact, case-sensitive name of the
                         cookie (e.g., "session-id").
            default (Any): The default value to return if the cookie is not
                           present. If not set, `required` defaults to `True`.
            required (bool): Explicitly set to `True` or `False`. Overrides
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
            validator (Optional[Callable]): A custom validation function.
            on_required_error_detail (Optional[str]): Error for missing required cookie.
            on_numeric_error_detail (Optional[str]): Error for float conversion failure.
            on_comparison_error_detail (Optional[str]): Error for gt/ge/lt/le failure.
            on_length_error_detail (Optional[str]): Error for min/max length failure.
            on_pattern_error_detail (Optional[str]): Error for regex/format failure.
            on_validator_error_detail (Optional[str]): Error for custom validator failure.
            status_code (int): The default HTTP status code to raise on failure.
            error_detail (Optional[str]): A generic fallback error message.
            
        Raises:
            ValueError: If `regex`/`pattern` and `format` are used simultaneously.
            ValueError: If an unknown `format` key is provided.
        """
        super().__init__(status_code=status_code, error_detail=error_detail)

        # --- Store Core Parameters ---
        self.alias = alias
        self.default = default
        
        # Determine if required.
        # 1. 'required' kwarg takes precedence
        # 2. If 'required' is not set, it's required *only if* 'default' is not set
        if required is not None:
            self.is_required = required
        else:
            self.is_required = default is ...

        # --- Store Validation Rules ---
        self.gt, self.ge, self.lt, self.le = gt, ge, lt, le
        self.min_length, self.max_length = min_length, max_length
        self.custom_validator = validator

        # --- Store Error Messages ---
        self.err_required = on_required_error_detail
        self.err_numeric = on_numeric_error_detail
        self.err_compare = on_comparison_error_detail
        self.err_length = on_length_error_detail
        self.err_pattern = on_pattern_error_detail
        self.err_validator = on_validator_error_detail

        # --- Handle Regex/Pattern ---
        self.final_regex_str = regex or pattern
        if self.final_regex_str and format:
            raise ValueError("Cannot use 'regex'/'pattern' and 'format' simultaneously.")
        if format:
            if format not in PRE_BUILT_PATTERNS:
                raise ValueError(f"Unknown format: '{format}'. Available: {list(PRE_BUILT_PATTERNS.keys())}")
            self.final_regex_str = PRE_BUILT_PATTERNS[format]
        
        self.final_regex = re.compile(self.final_regex_str) if self.final_regex_str else None

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
                    status_code=500
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

        except ValidationError as e:
            # Convert internal error to HTTPException
            self._raise_error(status_code=e.status_code, detail=str(e.detail))
        except HTTPException:
            # Re-raise HTTPExceptions (like from _raise_error) directly
            raise
        except Exception as e:
            # Catch any other unexpected error during validation
            self._raise_error(
                status_code=500,
                detail=f"An unexpected error occurred during cookie validation: {e}",
            )
        
        # All checks passed, return the value (or its numeric version if possible)
        return numeric_value if numeric_value is not None else cookie_value

    def _validate_numeric(self, value: str) -> Optional[float]:
        """
        Tries to convert value to float. Returns float or None.
        
        This check is only triggered if gt, ge, lt, or le are set.
        
        Raises:
            ValidationError: If conversion to float fails.
        """
        if any(v is not None for v in [self.gt, self.ge, self.lt, self.le]):
            try:
                return float(value)
            except (ValueError, TypeError):
                raise ValidationError(detail=self.err_numeric, status_code=400)
        return None

    def _validate_comparison(self, value: float) -> None:
        """
        Checks gt, ge, lt, le rules against a numeric value.
        
        Raises:
            ValidationError: If any comparison fails.
        """
        if self.gt is not None and not value > self.gt:
            raise ValidationError(detail=self.err_compare, status_code=400)
        if self.ge is not None and not value >= self.ge:
            raise ValidationError(detail=self.err_compare, status_code=400)
        if self.lt is not None and not value < self.lt:
            raise ValidationError(detail=self.err_compare, status_code=400)
        if self.le is not None and not value <= self.le:
            raise ValidationError(detail=self.err_compare, status_code=400)

    def _validate_length(self, value: str) -> None:
        """
        Checks min_length and max_length rules.
        
        Raises:
            ValidationError: If length constraints fail.
        """
        value_len = len(value)
        if self.min_length is not None and value_len < self.min_length:
            raise ValidationError(detail=self.err_length, status_code=400)
        if self.max_length is not None and value_len > self.max_length:
            raise ValidationError(detail=self.err_length, status_code=400)

    def _validate_pattern(self, value: str) -> None:
        """
        Checks regex/format pattern rule.
        
        Raises:
            ValidationError: If the regex pattern does not match.
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
                # Re-raise our own validation error to be caught by __call__
                raise
            except Exception as e:
                # Validator function raising an error is a validation failure
                raise ValidationError(detail=f"{self.err_validator}: {e}", status_code=400)

