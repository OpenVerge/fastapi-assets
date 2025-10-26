"""Module for custom exceptions."""


class ValidationError(Exception):
    """Exception raised for validation errors in FastAPI Assets.

    Attributes:
        detail (str): Description of the validation error.
        status_code (int): HTTP status code associated with the error.
    """

    def __init__(self, detail: str = "Validation Error", status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
