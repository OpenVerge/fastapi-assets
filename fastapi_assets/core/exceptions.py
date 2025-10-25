"""Module for custom exceptions."""

from typing import Optional


class ValidationError(Exception):
    """Exception raised for validation errors in FastAPI Assets.

    Attributes:
        detail (str): Description of the validation error.
        status_code (Optional[int]): HTTP status code associated with the error.
    """

    def __init__(self, detail: str, status_code: Optional[int] = None):
        self.detail = detail
        self.status_code = status_code
