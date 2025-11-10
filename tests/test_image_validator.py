"""
Test suite for the ImageValidator class.

This suite uses pytest and pytest-asyncio to validate all features
of the ImageValidator, including inherited checks, image-specific
validations (format, resolution, aspect ratio), and error handling.
"""

import io
from typing import Tuple
from unittest.mock import MagicMock, AsyncMock

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

# Mock Dependencies
# To make this test file runnable, we must mock the classes
# ImageValidator inherits from or imports.


class MockValidationError(Exception):
    """Mock a ValidationError for testing."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class MockBaseValidator:
    """Mock the BaseValidator class."""

    def __init__(self, status_code: int = 400, error_detail: str = "Validation failed."):
        self._status_code = status_code
        self._error_detail = error_detail

    def _raise_error(self, status_code: int, detail: str) -> None:
        """Mock the error raising to throw HTTPException, as a FastAPI dependency would."""
        raise HTTPException(status_code=status_code, detail=detail)


class MockFileValidator(MockBaseValidator):
    """Mock the FileValidator class to simulate its behavior."""

    _DEFAULT_CHUNK_SIZE = 65_536

    def __init__(
        self,
        max_size: int = None,
        min_size: int = None,
        content_types: list[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._max_size = max_size
        self._min_size = min_size
        self._content_types = content_types

    async def __call__(self, file: UploadFile, **kwargs):
        """Simulate FileValidator's __call__ logic for testing inheritance."""
        # Mock size check
        if self._max_size is not None:
            # Get file size
            file.file.seek(0, io.SEEK_END)
            file_size = file.file.tell()
            file.file.seek(0)

            if file_size > self._max_size:
                raise MockValidationError(detail="File is too large.", status_code=413)

        # Mock content-type check
        if self._content_types and file.content_type not in self._content_types:
            raise MockValidationError(detail="Invalid content type.", status_code=415)

        # Critical: rewind file for next operation
        await file.seek(0)
        return file


# Monkeypatch the Imports in the Module Under Test
# We replace the real imports with our mocks *before* importing ImageValidator

import sys
from unittest.mock import MagicMock

# Create mock modules
mock_base_validator = MagicMock()
mock_base_validator.ValidationError = MockValidationError
mock_base_validator.BaseValidator = MockBaseValidator

mock_file_validator = MagicMock()
mock_file_validator.FileValidator = MockFileValidator

# Put them in sys.modules
sys.modules["fastapi_assets.core.base_validator"] = mock_base_validator
sys.modules["fastapi_assets.validators.file_validator"] = mock_file_validator

# Import the Class Under Test
# Now, when ImageValidator is imported, it will use our mocks
from fastapi_assets.validators.image_validator import (  # noqa: E402
    ImageValidator,
    _DEFAULT_IMAGE_CONTENT_TYPES,
)

# Test Helper Functions


def create_mock_image_file(
    filename: str,
    content_type: str,
    img_format: str,
    size: Tuple[int, int],
    color: str = "blue",
) -> UploadFile:
    """Creates an in-memory mock image UploadFile."""
    buffer = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buffer, format=img_format)
    buffer.seek(0)

    # Save the original close method
    original_close = buffer.close
    # Override close to prevent actual closing during tests
    buffer.close = lambda: None

    # Use MagicMock to create a mock UploadFile with settable content_type
    file = MagicMock(spec=UploadFile)
    file.filename = filename
    file.content_type = content_type
    file.file = buffer
    file.size = len(buffer.getvalue())  # Set the size attribute

    # Create a wrapper for seek
    async def mock_seek(offset):
        buffer.seek(offset)

    # Create a wrapper for read
    async def mock_read():
        return buffer.read()

    async def mock_close():
        # Don't actually close the buffer so tests can still access it
        pass

    file.read = AsyncMock(side_effect=mock_read)
    file.seek = AsyncMock(side_effect=mock_seek)
    file.close = AsyncMock(side_effect=mock_close)
    return file


def create_mock_text_file(filename: str) -> UploadFile:
    """Creates an in-memory mock text UploadFile."""
    buffer = io.BytesIO(b"This is not an image, just plain text.")
    buffer.seek(0)

    # Override close to prevent actual closing during tests
    buffer.close = lambda: None

    # Use MagicMock to create a mock UploadFile with settable content_type
    file = MagicMock(spec=UploadFile)
    file.filename = filename
    file.content_type = "text/plain"
    file.file = buffer
    file.size = len(buffer.getvalue())  # Set the size attribute

    # Create a wrapper for seek
    async def mock_seek(offset):
        buffer.seek(offset)

    # Create a wrapper for read
    async def mock_read():
        return buffer.read()

    async def mock_close():
        # Don't actually close the buffer so tests can still access it
        pass

    file.read = AsyncMock(side_effect=mock_read)
    file.seek = AsyncMock(side_effect=mock_seek)
    file.close = AsyncMock(side_effect=mock_close)
    return file


# Test Suite


@pytest.mark.asyncio
class TestImageValidator:
    """Test suite for the ImageValidator."""

    async def test_valid_image_passes(self):
        """
        Tests that a fully valid image passes all checks.
        """
        validator = ImageValidator(
            max_size=1024 * 1024,  # 1MB
            allowed_formats=["PNG"],
            min_resolution=(100, 100),
            max_resolution=(500, 500),
            aspect_ratios=["1:1"],
        )

        file = create_mock_image_file("valid.png", "image/png", "PNG", (200, 200))

        try:
            validated_file = await validator(file)
            assert validated_file == file
            # Check that the file is rewound for the endpoint to read
            if not file.file.closed:
                assert file.file.tell() == 0
        finally:
            await file.close()

    async def test_file_is_rewound_after_validation(self):
        """
        Tests that the file stream is rewound to 0 twice:
        1. After the parent FileValidator checks (if any).
        2. After the ImageValidator (Pillow) checks.
        """
        validator = ImageValidator(allowed_formats=["PNG"])
        file = create_mock_image_file("test.png", "image/png", "PNG", (50, 50))

        # Get the original size
        file.file.seek(0, io.SEEK_END)
        original_size = file.file.tell()
        file.file.seek(0)

        assert original_size > 0

        try:
            await validator(file)

            # Check 1: Is file pointer at 0?
            assert file.file.tell() == 0

            # Check 2: Can we read the full content?
            content = await file.read()
            assert len(content) == original_size
        finally:
            await file.close()  # Initialization Tests

    def test_init_sets_defaults(self):
        """Tests that the validator sets default image content types."""
        validator = ImageValidator()
        assert validator._content_types == _DEFAULT_IMAGE_CONTENT_TYPES
        assert validator._allowed_formats is None

    def test_init_overrides_content_types(self):
        """Tests that 'content_types' in kwargs overrides the default."""
        validator = ImageValidator(content_types=["image/foo"])
        assert validator._content_types == ["image/foo"]

    def test_init_parses_aspect_ratios(self):
        """Tests that string aspect ratios are correctly parsed to floats."""
        validator = ImageValidator(aspect_ratios=["16:9", "1:1", "4:3"])
        assert validator._aspect_ratios is not None
        assert pytest.approx(validator._aspect_ratios[0]) == 16 / 9
        assert pytest.approx(validator._aspect_ratios[1]) == 1.0
        assert pytest.approx(validator._aspect_ratios[2]) == 4 / 3

    def test_init_invalid_aspect_ratio_raises(self):
        """Tests that a malformed aspect ratio string raises a ValueError."""
        with pytest.raises(ValueError, match="Invalid aspect_ratios format: '16-9'"):
            ImageValidator(aspect_ratios=["16-9"])

        with pytest.raises(ValueError, match="Invalid aspect_ratios format: '1:0'"):
            ImageValidator(aspect_ratios=["1:0"])

    # Inherited Validation Tests

    async def test_inherited_max_size_failure(self):
        """
        Tests that the parent FileValidator check (max_size) is
        correctly called and raises an error.
        """
        # Set max_size to 100 bytes. The mock image will be larger.
        validator = ImageValidator(max_size=100)
        file = create_mock_image_file("large.png", "image/png", "PNG", (100, 100))

        try:
            with pytest.raises(HTTPException) as exc_info:
                await validator(file)

            assert exc_info.value.status_code == 413  # From our mock
            assert "exceeds the maximum limit" in exc_info.value.detail
        finally:
            await file.close()

    # Image-Specific Validation Tests

    async def test_invalid_format_failure(self):
        """Tests failure when Pillow-detected format is not in allowed_formats."""
        validator = ImageValidator(allowed_formats=["JPEG"])
        file = create_mock_image_file("image.png", "image/png", "PNG", (100, 100))

        try:
            with pytest.raises(HTTPException) as exc_info:
                await validator(file)

            assert exc_info.value.status_code == 415
            assert "Unsupported image format: 'PNG'" in exc_info.value.detail
        finally:
            await file.close()

    async def test_not_an_image_file_failure(self):
        """Tests failure when the file is not a valid image (e.g., text)."""
        validator = ImageValidator(allowed_formats=["JPEG"])

        # Create a mock that has image content_type but contains text
        buffer = io.BytesIO(b"This is not an image, just plain text.")
        buffer.seek(0)
        buffer.close = lambda: None  # Prevent closing

        file = MagicMock(spec=UploadFile)
        file.filename = "fake.jpg"
        file.content_type = "image/jpeg"  # Looks like JPEG but isn't
        file.file = buffer

        async def mock_seek(offset):
            buffer.seek(offset)

        async def mock_read():
            return buffer.read()

        async def mock_close():
            pass

        file.read = AsyncMock(side_effect=mock_read)
        file.seek = AsyncMock(side_effect=mock_seek)
        file.close = AsyncMock(side_effect=mock_close)

        try:
            with pytest.raises(HTTPException) as exc_info:
                await validator(file)

            assert exc_info.value.status_code == 415
            assert "File is not a valid image" in exc_info.value.detail
        finally:
            await file.close()

    async def test_min_resolution_failure(self):
        """Tests failure when image dimensions are below min_resolution."""
        validator = ImageValidator(min_resolution=(200, 200))
        file = create_mock_image_file("small.png", "image/png", "PNG", (100, 100))

        try:
            with pytest.raises(HTTPException) as exc_info:
                await validator(file)

            assert exc_info.value.status_code == 400
            assert "is below the minimum of 200x200" in exc_info.value.detail
        finally:
            await file.close()

    async def test_max_resolution_failure(self):
        """Tests failure when image dimensions are above max_resolution."""
        validator = ImageValidator(max_resolution=(50, 50))
        file = create_mock_image_file("large.png", "image/png", "PNG", (100, 100))

        try:
            with pytest.raises(HTTPException) as exc_info:
                await validator(file)

            assert exc_info.value.status_code == 400
            assert "exceeds the maximum of 50x50" in exc_info.value.detail
        finally:
            await file.close()

    async def test_exact_resolution_failure(self):
        """Tests failure when image dimensions do not match exact_resolution."""
        validator = ImageValidator(exact_resolution=(100, 100))
        file = create_mock_image_file("wrong.png", "image/png", "PNG", (101, 100))

        try:
            with pytest.raises(HTTPException) as exc_info:
                await validator(file)

            assert exc_info.value.status_code == 400
            assert "must be exactly 100x100" in exc_info.value.detail
        finally:
            await file.close()

    async def test_exact_resolution_success(self):
        """Tests success when image dimensions match exact_resolution."""
        validator = ImageValidator(exact_resolution=(100, 100))
        file = create_mock_image_file("correct.png", "image/png", "PNG", (100, 100))

        try:
            await validator(file)
            # No exception raised
        finally:
            await file.close()

    async def test_aspect_ratio_failure(self):
        """Tests failure when image aspect ratio is not in the allowed list."""
        validator = ImageValidator(aspect_ratios=["1:1", "16:9"])
        # Create a 4:3 image
        file = create_mock_image_file("4_3.png", "image/png", "PNG", (800, 600))

        try:
            with pytest.raises(HTTPException) as exc_info:
                await validator(file)

            assert exc_info.value.status_code == 400
            assert "aspect ratio (800:600" in exc_info.value.detail
            assert "Allowed ratios are: 1:1, 16:9" in exc_info.value.detail
        finally:
            await file.close()

    async def test_aspect_ratio_tolerance_success(self):
        """
        Tests that an image with an aspect ratio *close* to the target
        passes when a tolerance is specified.
        """
        # 16:9 is ~1.777. Our image is 178:100 = 1.78
        validator = ImageValidator(aspect_ratios=["16:9"], aspect_ratio_tolerance=0.01)
        file = create_mock_image_file("off_16_9.png", "image/png", "PNG", (178, 100))

        try:
            await validator(file)
            # No exception raised, 1.78 is within 0.01 of 1.777
        finally:
            await file.close()

    # Custom Error Message Tests

    async def test_custom_format_error_message(self):
        """Tests that 'on_format_error_detail' provides a custom message."""
        custom_msg = "Only JPEGs are allowed, please."
        validator = ImageValidator(allowed_formats=["JPEG"], on_format_error_detail=custom_msg)
        file = create_mock_image_file("image.png", "image/png", "PNG", (100, 100))

        try:
            with pytest.raises(HTTPException) as exc_info:
                await validator(file)

            assert exc_info.value.status_code == 415
            assert exc_info.value.detail == custom_msg
        finally:
            await file.close()

    async def test_custom_resolution_error_message(self):
        """Tests that 'on_resolution_error_detail' provides a custom message."""
        custom_msg = "Image is too small."
        validator = ImageValidator(min_resolution=(200, 200), on_resolution_error_detail=custom_msg)
        file = create_mock_image_file("small.png", "image/png", "PNG", (100, 100))

        try:
            with pytest.raises(HTTPException) as exc_info:
                await validator(file)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == custom_msg
        finally:
            await file.close()

    async def test_custom_aspect_ratio_error_message(self):
        """Tests that 'on_aspect_ratio_error_detail' provides a custom message."""
        custom_msg = "Image must be square."
        validator = ImageValidator(aspect_ratios=["1:1"], on_aspect_ratio_error_detail=custom_msg)
        file = create_mock_image_file("16_9.png", "image/png", "PNG", (1920, 1080))

        try:
            with pytest.raises(HTTPException) as exc_info:
                await validator(file)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == custom_msg
        finally:
            await file.close()
