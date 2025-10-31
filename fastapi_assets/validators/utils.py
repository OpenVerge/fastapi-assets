"""Utility functions for file validation in FastAPI Assets."""

from typing import TYPE_CHECKING, List, Optional, Union
import re
import fnmatch
from fastapi_assets.core.base_validator import ValidationError
from starlette.datastructures import UploadFile

if TYPE_CHECKING:
    from fastapi_assets.validators.file_validator import FileValidator


def _parse_size_to_bytes(size: Union[str, int], size_pattern: re.Pattern, size_units: dict) -> int:
    """Converts a size string (e.g., "10MB") to bytes.
    Args:
        size: Size as a string with units or an integer in bytes.
        size_pattern: Compiled regex pattern to parse size strings.
        size_units: Dictionary mapping size units to their byte values.
    Returns:
        Size in bytes as an integer.
    """
    if isinstance(size, int):
        return size

    match = size_pattern.fullmatch(size.strip())
    if not match:
        raise ValueError(f"Invalid size string format: '{size}'")

    value, unit = match.groups()
    unit = unit.upper()

    if unit not in size_units:
        raise ValueError(f"Invalid size unit: '{unit}' (use B, KB, MB, GB, TB)")

    return int(float(value) * size_units[unit])


def _match_content_type(file_type: str, allowed_types: List[str]) -> bool:
    """Checks if a file's MIME type matches any allowed type, supporting wildcards.
    Args:
        file_type: The MIME type of the file (e.g., "image/jpeg").
        allowed_types: List of allowed MIME types (e.g., ["image/*", "application/pdf"]).
    Returns:
        True if there's a match, False otherwise.
    """
    if not file_type:
        return False
    for allowed_type in allowed_types:
        if fnmatch.fnmatch(file_type, allowed_type):
            return True
    return False


def _format_bytes(byte_count: int, size_units: dict) -> str:
    """Utility to format bytes into a human-readable string.
    Args:
        byte_count: The size in bytes.
        size_units: Dictionary mapping size units to their byte values.
    Returns:
        Formatted size string (e.g., "10MB").
    """
    for unit, limit in reversed(size_units.items()):
        if byte_count >= limit:
            value = byte_count / limit
            return f"{value:.1f}{unit}" if value % 1 else f"{value:.0f}{unit}"
    return "0B"


async def _get_streamed_size(self: "FileValidator", file: UploadFile, size_units: dict) -> int:
    """
    Reads the file in chunks to determine its size,
    while enforcing max_size limit during the stream.
    Args:
        self: The FileValidator instance.
        file: The uploaded file to measure.
        size_units: Dictionary mapping size units to their byte values.
    Returns:
        The size of the file in bytes.
    Raises:
        ValidationError: If the file exceeds max_size during streaming.
    """
    actual_size = 0
    chunk_size = self._DEFAULT_CHUNK_SIZE
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        actual_size += len(chunk)

        if self._max_size is not None and actual_size > self._max_size:
            # Stop reading and close the file immediately
            await file.close()
            detail = self._size_error_detail or (
                f"File size exceeds the maximum limit of "
                f"{_format_bytes(byte_count=self._max_size, size_units=size_units)} (streaming check)."
            )
            raise ValidationError(detail=str(detail), status_code=413)

    return actual_size


def _check_size_bounds(self: "FileValidator", file_size: int, size_units: dict) -> None:
    """Compares a known file size against max/min bounds.
    Args:
        self: The FileValidator instance.
        file_size: The size of the file in bytes.
        size_units: Dictionary mapping size units to their byte values.
    Returns:
        None
    Raises:
        ValidationError: If size is out of bounds.
    """

    if self._max_size is not None and file_size > self._max_size:
        detail = self._size_error_detail or (
            f"File size ({_format_bytes(byte_count=file_size, size_units=size_units)}) exceeds "
            f"the maximum limit of {_format_bytes(byte_count=self._max_size, size_units=size_units)}."
        )
        # Use 413 for Payload Too Large
        raise ValidationError(detail=str(detail), status_code=413)

    if self._min_size is not None and file_size < self._min_size:
        detail = self._size_error_detail or (
            f"File size ({_format_bytes(byte_count=file_size, size_units=size_units)}) is less "
            f"than the minimum requirement of {_format_bytes(byte_count=self._min_size, size_units=size_units)}."
        )
        raise ValidationError(detail=str(detail), status_code=400)
