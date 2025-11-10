"""Module providing the FileValidator for validating uploaded files in FastAPI."""

import re
from typing import Any, Callable, List, Optional, Union
from fastapi_assets.core.base_validator import BaseValidator, ValidationError
from fastapi import File, UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi_assets.validators.utils import (
    _check_size_bounds,
    _parse_size_to_bytes,
    _match_content_type,
    _get_streamed_size,
)

# FileValidator Implementation

_SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*([KMGT]?B)", re.IGNORECASE)
_SIZE_UNITS = {
    "B": 1,
    "KB": 1024,
    "MB": 1024**2,
    "GB": 1024**3,
    "TB": 1024**4,
}


class FileValidator(BaseValidator):
    r"""
    A general-purpose dependency for validating `UploadFile` objects.

    It efficiently checks file size (using `Content-Length` or streaming),
    MIME type, and filename.

    .. code-block:: python
        from fastapi import FastAPI, UploadFile, Depends
        from fastapi_assets.validators import FileValidator

        app = FastAPI()

        file_validator = FileValidator(
            max_size="10MB",
            min_size="1KB",
            content_types=["image/*", "application/pdf"],
            filename_pattern=r"^[\w,\s-]+\.[A-Za-z]{3,4}$",
            on_size_error_detail="File size is not within the allowed range.",
            on_type_error_detail="Unsupported file type uploaded.",
            on_filename_error_detail="Filename does not match the required pattern."
        )

        @app.post("/upload/")
        async def upload_file(file: UploadFile = Depends(file_validator)):
            return {"filename": file.filename}
    """

    _DEFAULT_CHUNK_SIZE = 65_536  # 64KB

    def __init__(
        self,
        *,
        max_size: Optional[Union[str, int]] = None,
        min_size: Optional[Union[str, int]] = None,
        content_types: Optional[List[str]] = None,
        filename_pattern: Optional[str] = None,
        on_size_error_detail: Optional[Union[str, Callable[[Any], str]]] = None,
        on_type_error_detail: Optional[Union[str, Callable[[Any], str]]] = None,
        on_filename_error_detail: Optional[Union[str, Callable[[Any], str]]] = None,
        validators: Optional[List[Callable]] = None,
        **kwargs: Any,
    ):
        """
        Initializes the FileValidator.

        Args:
            max_size: Maximum allowed file size (e.g., "10MB", 1024).
            min_size: Minimum allowed file size (e.g., "1KB").
            content_types: A list of allowed MIME types (e.g., ["image/jpeg", "image/*"]).
            filename_pattern: A regex pattern to validate the filename.
            on_size_error_detail: Custom error message for size validation failures.
            on_type_error_detail: Custom error message for content-type failures.
            on_filename_error_detail: Custom error message for filename pattern failures.
            **kwargs: Additional arguments for the BaseValidator.
        """
        # Call super() with a generic default, which will be overridden
        # by the specific error handlers.
        kwargs["error_detail"] = kwargs.get("error_detail", "File validation failed.")
        kwargs["status_code"] = 400
        super().__init__(
            error_detail=kwargs["error_detail"],
            status_code=kwargs["status_code"],
            validators=validators,
        )

        # Parse sizes once
        self._max_size = (
            _parse_size_to_bytes(max_size, size_pattern=_SIZE_PATTERN, size_units=_SIZE_UNITS)
            if max_size
            else None
        )
        self._min_size = (
            _parse_size_to_bytes(min_size, size_pattern=_SIZE_PATTERN, size_units=_SIZE_UNITS)
            if min_size
            else None
        )

        # Store other validation rules
        self._content_types = content_types
        self._filename_regex = re.compile(filename_pattern) if filename_pattern else None

        # Store specific error details
        self._size_error_detail = on_size_error_detail
        self._type_error_detail = on_type_error_detail
        self._filename_error_detail = on_filename_error_detail

    async def __call__(self, file: UploadFile = File(...)) -> StarletteUploadFile:
        """
        FastAPI dependency entry point for file validation.

        Runs all configured validation checks on the uploaded file (content type,
        filename, size, and custom validators) and returns the validated file
        after rewinding it so the endpoint can read it from the beginning.

        Args:
            file: The uploaded file to validate.

        Returns:
            StarletteUploadFile: The validated UploadFile object, rewound to the start.

        Raises:
            HTTPException: If any validation check fails.
        """
        try:
            await self._validate(file=file)
        except ValidationError as e:
            # Our custom validation exception, convert to HTTPException
            self._raise_error(status_code=e.status_code, detail=str(e.detail))
        except Exception as e:
            # Catch any other unexpected error during validation
            await file.close()
            self._raise_error(
                status_code=400,
                detail="An unexpected error occurred during file validation.",
            )

        # CRITICAL: Rewind the file stream after reading it so that
        # the endpoint can read it from the beginning.
        await file.seek(0)
        return file

    async def _validate(self, file: UploadFile) -> None:
        """
        Runs all file validation checks in sequence.

        Executes content-type, filename, size, and custom validator checks
        on the uploaded file.

        Args:
            file: The uploaded file to validate.

        Returns:
            None

        Raises:
            ValidationError: If any validation check fails.
        """
        self._validate_content_type(file)
        self._validate_filename(file)
        await self._validate_size(file=file)
        await self._validate_custom(value=file)

    def _validate_content_type(self, file: UploadFile) -> None:
        """
        Validates that the file's MIME type is in the allowed list.

        Checks the file's Content-Type against the configured allowed types,
        supporting wildcard patterns (e.g., "image/*").

        Args:
            file: The uploaded file to validate.

        Returns:
            None

        Raises:
            ValidationError: If the content type is not in the allowed list.
        """
        if not self._content_types:
            return  # No validation rule set

        file_type = file.content_type
        if file_type is None or not _match_content_type(file_type, self._content_types):
            detail = self._type_error_detail or (
                f"File has an unsupported media type: '{file_type}'. "
                f"Allowed types are: {', '.join(self._content_types)}"
            )
            # Use 415 for Unsupported Media Type
            raise ValidationError(detail=str(detail), status_code=415)

    def _validate_filename(self, file: UploadFile) -> None:
        """
        Validates that the filename matches the configured regex pattern.

        Args:
            file: The uploaded file to validate.

        Returns:
            None

        Raises:
            ValidationError: If the filename doesn't match the pattern or is missing.
        """
        if not self._filename_regex:
            return  # No validation rule set

        if not file.filename or not self._filename_regex.search(file.filename):
            detail = self._filename_error_detail or (
                f"Filename '{file.filename}' does not match the required pattern."
            )
            raise ValidationError(detail=str(detail), status_code=400)

    async def _validate_size(self, file: UploadFile) -> None:
        """
        Validates that the file size is within configured bounds.

        Uses the Content-Length header if available for efficiency, otherwise
        streams the file to determine its actual size.

        Args:
            file: The uploaded file to validate.

        Returns:
            None

        Raises:
            ValidationError: If the file size exceeds max_size or is below min_size.
        """
        if self._max_size is None and self._min_size is None:
            return  # No validation rule set

        file_size: Optional[int] = file.size

        if file_size is not None:
            # Easy path: Content-Length was provided
            _check_size_bounds(self, file_size, _SIZE_UNITS)
        else:
            # Hard path: Stream the file to count its size
            actual_size = await _get_streamed_size(self, file, _SIZE_UNITS)
            _check_size_bounds(self, actual_size, _SIZE_UNITS)
