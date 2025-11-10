"""Module providing the QueryValidator for validating query parameters in FastAPI."""

from typing import Any, Callable, List, Optional, Union
from inspect import Signature, Parameter
from fastapi import Query
from fastapi_assets.core import BaseValidator, ValidationError


class QueryValidator(BaseValidator):
    r"""
    A dependency factory for adding custom validation to FastAPI query parameters.

    This class extends the functionality of FastAPI's `Query()` by adding
    support for `allowed_values` and custom `validators`.

    It acts as a factory: you instantiate it, and then *call* the
    instance inside `Depends()` to get the actual dependency.

    Example:
    .. code-block:: python

        from fastapi import FastAPI, Depends
        from fastapi_assets.request_validators import QueryValidator

        app = FastAPI()

        # 1. Create reusable validator *instances*
        page_validator = QueryValidator(
            "page",
            _type=int,
            default=1,
            ge=1,
            le=100,
        )

        status_validator = QueryValidator(
            "status",
            _type=str,
            allowed_values=["active", "inactive", "pending"],
        )

        sort_validator = QueryValidator(
            "sort",
            _type=str,
            default="name",
            pattern=r"^[a-zA-Z_]+$",
        )

        @app.get("/items/")
        def list_items(
            page: int = Depends(page_validator()),
            status: str = Depends(status_validator()),
            sort: str = Depends(sort_validator()),
        ):
            return {"page": page, "status": status, "sort": sort}
    """

    def __init__(
        self,
        param_name: str,
        _type: type,
        default: Any = ...,
        *,
        # Custom validation rules
        allowed_values: Optional[List[Any]] = None,
        validators: Optional[List[Callable[[Any], Any]]] = None,
        on_custom_validator_error_detail: str = "Custom validation failed.",
        # Standard Query() parameters
        title: Optional[str] = None,
        description: Optional[str] = None,
        gt: Optional[Union[int, float]] = None,
        lt: Optional[Union[int, float]] = None,
        ge: Optional[Union[int, float]] = None,
        le: Optional[Union[int, float]] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        pattern: Optional[str] = None,
        deprecated: Optional[bool] = None,
        **query_kwargs: Any,
    ) -> None:
        """
        Initializes the QueryValidator factory.

        Args:
            param_name: The exact name of the query parameter.
            _type: The Python type for coercion (e.g., int, str, UUID).
            default: Default value for the query parameter.
            allowed_values: List of allowed values.
            validators: List of custom validation functions.
            on_custom_validator_error_detail: Error message for custom validators.
            title: Title for API documentation.
            description: Description for API documentation.
            gt: Value must be greater than this.
            lt: Value must be less than this.
            ge: Value must be greater than or equal to this.
            le: Value must be less than or equal to this.
            min_length: Minimum length for string parameters.
            max_length: Maximum length for string parameters.
            pattern: Regex pattern the parameter must match.
            deprecated: Whether the parameter is deprecated.
            **query_kwargs: Additional arguments passed to FastAPI's Query().
        """
        query_kwargs.setdefault("error_detail", "Query parameter validation failed.")
        query_kwargs.setdefault("status_code", 400)

        super().__init__(
            status_code=query_kwargs["status_code"],
            error_detail=query_kwargs["error_detail"],
            validators=validators,
        )

        self._param_name = param_name
        self._type = _type
        self._allowed_values = allowed_values
        self._on_custom_validator_error_detail = on_custom_validator_error_detail

        self._query_param = Query(
            default,
            title=title,
            description=description,
            deprecated=deprecated,
            gt=gt,
            lt=lt,
            ge=ge,
            le=le,
            min_length=min_length,
            max_length=max_length,
            pattern=pattern,
            **query_kwargs,
        )

    def __call__(self) -> Callable[..., Any]:
        """
        This is the factory method.
        It generates and returns the dependency function
        that FastAPI will use.
        """

        async def dependency(**kwargs: Any) -> Any:
            query_value = kwargs[self._param_name]
            try:
                validated_value = await self._validate(query_value)
                return validated_value
            except ValidationError as e:
                self._raise_error(query_value, status_code=e.status_code, detail=e.detail)
            return None

        sig = Signature(
            [
                Parameter(
                    self._param_name,
                    Parameter.KEYWORD_ONLY,
                    default=self._query_param,
                    annotation=self._type,
                )
            ]
        )

        dependency.__signature__ = sig  # type: ignore
        return dependency

    async def _validate(self, value: Any) -> Any:
        """
        Runs all validation checks on the query parameter value.

        Executes allowed values checking and custom validator checking in sequence.

        Args:
            value: The query parameter value to validate.

        Returns:
            Any: The validated value (unchanged if validation passes).

        Raises:
            ValidationError: If any validation check fails.
        """
        self._validate_allowed_values(value)
        await self._validate_custom(value)
        return value

    def _validate_allowed_values(self, value: Any) -> None:
        """
        Checks if the query parameter value is in the list of allowed values.

        Args:
            value: The value to validate.

        Returns:
            None

        Raises:
            ValidationError: If the value is not in the allowed values list.
        """
        if self._allowed_values is None:
            return

        if value not in self._allowed_values:
            allowed_str = ", ".join(map(str, self._allowed_values))
            detail = f"Value '{value}' is not allowed. Allowed values are: {allowed_str}"
            raise ValidationError(detail=detail, status_code=400)
