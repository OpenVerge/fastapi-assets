"""
Tests for the FileValidator class.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, PropertyMock
from fastapi import HTTPException, UploadFile
from fastapi_assets.core.exceptions import ValidationError
from fastapi_assets.validators.file_validator import FileValidator


@pytest.fixture
def mock_upload_file() -> MagicMock:
    """
    Returns a configurable mock of a FastAPI/Starlette UploadFile.
    Uses AsyncMock for async methods.
    """
    file = MagicMock(spec=UploadFile)
    file.read = AsyncMock()
    file.seek = AsyncMock()
    file.close = AsyncMock()

    # Set default valid properties
    file.filename = "test_file.txt"
    file.content_type = "text/plain"
    file.size = 1024  # 1KB

    # Default streaming mock (1024 bytes total)
    file.read = AsyncMock(
        side_effect=[
            b"a" * 512,
            b"b" * 512,
            b"",  # End of file marker
        ]
    )

    return file


#  Test Cases


@pytest.mark.asyncio
class TestFileValidatorInit:
    """Tests for the FileValidator's __init__ method."""

    def test_init_defaults(self):
        """Tests that all rules are None by default."""
        validator = FileValidator()
        assert validator._max_size is None
        assert validator._min_size is None
        assert validator._content_types is None
        assert validator._filename_regex is None

    def test_init_size_parsing(self):
        """Tests that size strings are correctly parsed to bytes."""
        validator = FileValidator(max_size="2MB", min_size="1KB")
        assert validator._max_size == 2 * 1024 * 1024
        assert validator._min_size == 1024

    def test_init_int_size(self):
        """Tests that integer sizes are used directly."""
        validator = FileValidator(max_size=5000)
        assert validator._max_size == 5000

    def test_init_invalid_size_string(self):
        """Tests that a malformed size string raises a ValueError."""
        with pytest.raises(ValueError, match="Invalid size string"):
            FileValidator(max_size="10 ZB")  # ZB not in _SIZE_UNITS

    def test_init_filename_pattern(self):
        """Tests that the filename pattern is compiled to regex."""
        pattern = r"\.txt$"
        validator = FileValidator(filename_pattern=pattern)
        assert validator._filename_regex is not None
        assert validator._filename_regex.pattern == pattern
        assert validator._filename_regex.search("file.txt")

    def test_init_custom_error_details(self):
        """Tests that custom error detail messages are stored."""
        size_err = "File is too big"
        type_err = "Wrong file type"
        name_err = "Bad name"
        validator = FileValidator(
            on_size_error_detail=size_err,
            on_type_error_detail=type_err,
            on_filename_error_detail=name_err,
        )
        assert validator._size_error_detail == size_err
        assert validator._type_error_detail == type_err
        assert validator._filename_error_detail == name_err


@pytest.mark.asyncio
class TestFileValidatorCall:
    """Tests the main __call__ entry point."""

    async def test_call_valid_file(self, mock_upload_file: MagicMock):
        """
        Tests the happy path where the file is valid and no exceptions are raised.
        """
        validator = FileValidator(
            max_size="2MB", content_types=["text/plain"], filename_pattern=r"\.txt$"
        )

        # Configure file to be valid
        mock_upload_file.size = 1024 * 1024  # 1MB
        mock_upload_file.content_type = "text/plain"
        mock_upload_file.filename = "report.txt"

        result_file = await validator(mock_upload_file)

        # Should return the file
        assert result_file == mock_upload_file
        # CRITICAL: Should rewind the file for the endpoint to read
        mock_upload_file.seek.assert_called_once_with(0)

    async def test_call_invalid_content_type(self, mock_upload_file: MagicMock):
        """Tests that a content-type failure raises a 415 HTTPException."""
        validator = FileValidator(content_types=["image/jpeg"])
        mock_upload_file.content_type = "text/plain"  # Invalid

        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_upload_file)

        assert exc_info.value.status_code == 415
        assert "unsupported media type" in exc_info.value.detail

    async def test_call_invalid_filename(self, mock_upload_file: MagicMock):
        """Tests that a filename failure raises a 400 HTTPException."""
        validator = FileValidator(filename_pattern=r"\.jpg$")
        mock_upload_file.filename = "image.png"  # Invalid

        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_upload_file)

        assert exc_info.value.status_code == 400
        assert "does not match" in exc_info.value.detail

    async def test_call_invalid_size_too_large(self, mock_upload_file: MagicMock):
        """Tests that a size (max) failure raises a 413 HTTPException."""
        validator = FileValidator(max_size="1KB")
        mock_upload_file.size = 2000  # Invalid (approx 2KB)

        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_upload_file)

        assert exc_info.value.status_code == 413
        assert "exceeds the maximum limit" in exc_info.value.detail

    async def test_call_invalid_size_too_small(self, mock_upload_file: MagicMock):
        """Tests that a size (min) failure raises a 400 HTTPException."""
        validator = FileValidator(min_size="5KB")
        mock_upload_file.size = 1024  # Invalid (1KB)

        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_upload_file)

        assert exc_info.value.status_code == 400
        assert "less than the minimum requirement" in exc_info.value.detail

    async def test_call_streaming_size_too_large(self, mock_upload_file: MagicMock):
        """Tests size failure when file.size is None and streaming is required."""
        validator = FileValidator(max_size="1KB")  # 1024 bytes

        # Mock file.size = None
        mock_upload_file.size = None

        # Mock read to return too much data (1500 bytes total)
        # _DEFAULT_CHUNK_SIZE is 8192, so we return that plus more to exceed 1KB
        mock_upload_file.read = AsyncMock(
            side_effect=[
                b"a" * 1024,  # First chunk: 1024 bytes (already exceeds 1KB limit)
                b"b" * 500,  # This won't be read because we'll fail on first chunk
                b"",  # End of file
            ]
        )

        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_upload_file)

        assert exc_info.value.status_code == 413
        assert "exceeds" in exc_info.value.detail.lower()

    async def test_call_unexpected_error(self, mock_upload_file: MagicMock):
        """
        Tests that a non-ValidationError exception is caught, the file is closed,
        and a 400 error is raised.
        """
        # Enable content_types validation so it accesses the content_type property
        validator = FileValidator(content_types=["text/plain"])

        # Force an unexpected error by making content_type raise an exception
        type(mock_upload_file).content_type = PropertyMock(
            side_effect=Exception("Unexpected crash!")
        )

        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_upload_file)

        assert exc_info.value.status_code == 400
        assert "An unexpected error" in exc_info.value.detail
        # Should close the file on unexpected error
        mock_upload_file.close.assert_called_once()
        # Should NOT seek the file
        mock_upload_file.seek.assert_not_called()


@pytest.mark.asyncio
class TestFileValidatorLogic:
    """
    Unit tests for the individual _validate_* logic methods.
    These test that the methods raise ValidationError correctly.
    """

    def test_content_type_no_rule(self, mock_upload_file: MagicMock):
        """Tests that no rule set passes validation."""
        validator = FileValidator()
        try:
            validator._validate_content_type(mock_upload_file)
        except ValidationError:
            pytest.fail("Validation failed when no rule was set")

    def test_content_type_exact_match(self, mock_upload_file: MagicMock):
        validator = FileValidator(content_types=["image/png"])
        mock_upload_file.content_type = "image/png"
        try:
            validator._validate_content_type(mock_upload_file)
        except ValidationError:
            pytest.fail("Validation failed on exact match")

    def test_content_type_wildcard_match(self, mock_upload_file: MagicMock):
        validator = FileValidator(content_types=["image/*"])
        mock_upload_file.content_type = "image/jpeg"
        try:
            validator._validate_content_type(mock_upload_file)
        except ValidationError:
            pytest.fail("Validation failed on wildcard match")

    def test_content_type_no_match(self, mock_upload_file: MagicMock):
        validator = FileValidator(content_types=["image/png", "image/jpeg"])
        mock_upload_file.content_type = "text/plain"

        with pytest.raises(ValidationError) as e:
            validator._validate_content_type(mock_upload_file)

        assert e.value.status_code == 415
        assert "unsupported media type" in e.value.detail

    def test_content_type_custom_error(self, mock_upload_file: MagicMock):
        custom_error = "Only JPEGs allowed."
        validator = FileValidator(content_types=["image/jpeg"], on_type_error_detail=custom_error)
        mock_upload_file.content_type = "image/png"

        with pytest.raises(ValidationError) as e:
            validator._validate_content_type(mock_upload_file)

        assert e.value.status_code == 415
        assert e.value.detail == custom_error

    def test_filename_no_rule(self, mock_upload_file: MagicMock):
        validator = FileValidator()
        try:
            validator._validate_filename(mock_upload_file)
        except ValidationError:
            pytest.fail("Validation failed when no rule was set")

    def test_filename_match(self, mock_upload_file: MagicMock):
        validator = FileValidator(filename_pattern=r"\.csv$")
        mock_upload_file.filename = "data_export.csv"
        try:
            validator._validate_filename(mock_upload_file)
        except ValidationError:
            pytest.fail("Validation failed on filename match")

    def test_filename_no_match(self, mock_upload_file: MagicMock):
        validator = FileValidator(filename_pattern=r"^[a-zA-Z]+$")
        mock_upload_file.filename = "123_invalid.txt"

        with pytest.raises(ValidationError) as e:
            validator._validate_filename(mock_upload_file)

        assert e.value.status_code == 400
        assert "does not match" in e.value.detail

    def test_filename_is_none(self, mock_upload_file: MagicMock):
        """Tests that a None filename fails validation if a rule exists."""
        validator = FileValidator(filename_pattern=r".*")
        mock_upload_file.filename = None

        with pytest.raises(ValidationError) as e:
            validator._validate_filename(mock_upload_file)

        assert e.value.status_code == 400
        assert "Filename 'None'" in e.value.detail

    async def test_size_no_rule(self, mock_upload_file: MagicMock):
        validator = FileValidator()
        try:
            await validator._validate_size(mock_upload_file)
        except ValidationError:
            pytest.fail("Size validation failed when no rule was set")

    async def test_size_from_header_valid(self, mock_upload_file: MagicMock):
        validator = FileValidator(max_size="2MB", min_size="1KB")
        mock_upload_file.size = 1024 * 1024  # 1MB (valid)

        try:
            await validator._validate_size(mock_upload_file)
        except ValidationError:
            pytest.fail("Size validation failed on valid file size")

    async def test_size_from_header_too_large(self, mock_upload_file: MagicMock):
        validator = FileValidator(max_size="1MB")
        mock_upload_file.size = 1024 * 1024 + 1  # 1MB + 1 byte (invalid)

        with pytest.raises(ValidationError) as e:
            await validator._validate_size(mock_upload_file)

        assert e.value.status_code == 413
        assert "exceeds the maximum limit" in e.value.detail

    async def test_size_from_header_too_small(self, mock_upload_file: MagicMock):
        validator = FileValidator(min_size="2KB")
        mock_upload_file.size = 1024  # 1KB (invalid)

        with pytest.raises(ValidationError) as e:
            await validator._validate_size(mock_upload_file)

        assert e.value.status_code == 400
        assert "less than the minimum requirement" in e.value.detail

    async def test_size_from_stream_valid(self, mock_upload_file: MagicMock):
        validator = FileValidator(max_size="2MB", min_size="1KB")

        # Mock streaming, file.size is None
        mock_upload_file.size = None
        # Stream will return 1024 bytes (from default fixture)

        try:
            await validator._validate_size(mock_upload_file)
        except ValidationError:
            pytest.fail("Streaming size validation failed on valid file")

    async def test_size_from_stream_too_large(self, mock_upload_file: MagicMock):
        validator = FileValidator(max_size="512B")

        mock_upload_file.size = None
        # Stream will return 1024 bytes (default fixture)

        with pytest.raises(ValidationError) as e:
            await validator._validate_size(mock_upload_file)

        assert e.value.status_code == 413
        assert "exceeds the maximum limit" in e.value.detail

    async def test_size_from_stream_too_small(self, mock_upload_file: MagicMock):
        validator = FileValidator(min_size="2KB")

        mock_upload_file.size = None
        # Stream will return 1024 bytes (default fixture)

        with pytest.raises(ValidationError) as e:
            await validator._validate_size(mock_upload_file)

        assert e.value.status_code == 400
        assert "less than the minimum requirement" in e.value.detail

    async def test_size_custom_error(self, mock_upload_file: MagicMock):
        custom_error = "That file is way too big."
        validator = FileValidator(max_size="1KB", on_size_error_detail=custom_error)
        mock_upload_file.size = 2000  # > 1KB

        with pytest.raises(ValidationError) as e:
            await validator._validate_size(mock_upload_file)

        assert e.value.status_code == 413
        assert e.value.detail == custom_error
