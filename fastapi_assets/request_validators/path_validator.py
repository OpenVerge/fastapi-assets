"""Module providing the PathValidator for validating path parameters in FastAPI."""

from typing import Any, Callable, List, Optional, Union
from inspect import Signature, Parameter
from fastapi import Path
from fastapi_assets.core import BaseValidator, ValidationError


class PathValidator(BaseValidator):
    r"""
    A dependency factory for adding custom validation to FastAPI path parameters.

    This class extends the functionality of FastAPI's `Path()` by adding
    support for `allowed_values` and custom `validators`.

    It acts as a factory: you instantiate it, and then *call* the
    instance inside `Depends()` to get the actual dependency.

    Example:
    .. code-block:: python

        from fastapi import FastAPI, Depends
        from fastapi_assets.request_validators import PathValidator

        app = FastAPI()

        # 1. Create reusable validator *instances*
        item_id_validator = PathValidator(
            "item_id",
            _type=int,
            gt=0,
            lt=1000,
        )

        username_validator = PathValidator(
            "username",
            _type=str,
            min_length=5,
            max_length=15,
            pattern=r"^[a-zA-Z0-9]+$",
        )

        @app.get("/items/{item_id}")
        def get_item(item_id: int = Depends(item_id_validator())):
            return {"item_id": item_id}

        @app.get("/users/{username}")
        def get_user(username: str = Depends(username_validator())):
            return {"username": username}
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
        # Standard Path() parameters
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
        **path_kwargs: Any,
    ) -> None:
        """
        Initializes the PathValidator factory.

        Args:
            param_name: The exact name of the path parameter.
            _type: The Python type for coercion (e.g., int, str, UUID).
            default: Default value for the path parameter.
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
            **path_kwargs: Additional arguments passed to FastAPI's Path().
        """
        path_kwargs.setdefault("error_detail", "Path parameter validation failed.")
        path_kwargs.setdefault("status_code", 400)

        super().__init__(
            status_code=path_kwargs["status_code"],
            error_detail=path_kwargs["error_detail"],
            validators=validators,
        )

        self._param_name = param_name
        self._type = _type
        self._allowed_values = allowed_values
        self._on_custom_validator_error_detail = on_custom_validator_error_detail

        self._path_param = Path(
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
            **path_kwargs,
        )

    def __call__(self) -> Callable[..., Any]:
        """
        This is the factory method.
        It generates and returns the dependency function
        that FastAPI will use.
        """

        async def dependency(**kwargs: Any) -> Any:
            path_value = kwargs[self._param_name]
            try:
                validated_value = await self._validate(path_value)
                return validated_value
            except ValidationError as e:
                self._raise_error(path_value, status_code=e.status_code, detail=e.detail)
            return None

        sig = Signature(
            [
                Parameter(
                    self._param_name,
                    Parameter.KEYWORD_ONLY,
                    default=self._path_param,
                    annotation=self._type,
                )
            ]
        )

        dependency.__signature__ = sig  # type: ignore
        return dependency

    async def _validate(self, value: Any) -> Any:
        """
        Runs all validation checks on the path parameter value.

        Executes allowed values checking and custom validator checking in sequence.

        Args:
            value: The path parameter value to validate.

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
        Checks if the path parameter value is in the list of allowed values.

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
