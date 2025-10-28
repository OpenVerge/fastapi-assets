"""
Module providing the ImageValidator for validating uploaded image files.
"""

from typing import Any, Callable, List, Optional, Union
from fastapi_assets.core.base_validator import ValidationError
from fastapi import File, UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi_assets.validators.file_validator import FileValidator

# Pillow Dependency Handling
try:
    # Pillow is required for ImageValidator
    from PIL import Image, UnidentifiedImageError
    PIL = True
except ImportError:
    PIL = None  # type: ignore

# ImageValidator Implementation

_DEFAULT_IMAGE_CONTENT_TYPES = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
]


class ImageValidator(FileValidator):
    r"""
    A specialized dependency for validating image `UploadFile` objects.

    Inherits all checks from `FileValidator` (size, filename) and adds
    validations for image format, resolution, and aspect ratio by
    inspecting the file content with Pillow.

    Requires `fastapi-assets[image]` to be installed.

    .. code-block:: python
        from fastapi import FastAPI, UploadFile, Depends
        from fastapi_assets.validators.image_validator import ImageValidator

        app = FastAPI()

        image_validator = ImageValidator(
            max_size="5MB",
            allowed_formats=["JPEG", "PNG"],
            min_resolution=(640, 480),
            max_resolution=(1920, 1080),
            aspect_ratios=["16:9", "4:3"],
            on_format_error_detail="Only JPEG and PNG images are allowed.",
            on_resolution_error_detail="Image must be between 640x480 and 1920x1080."
        )

        @app.post("/upload/image/")
        async def upload_image(image: UploadFile = Depends(image_validator)):
            return {"filename": image.filename, "format": image.content_type}
    """

    def __init__(
        self,
        *,
        allowed_formats: Optional[List[str]] = None,
        min_resolution: Optional[tuple[int, int]] = None,
        max_resolution: Optional[tuple[int, int]] = None,
        exact_resolution: Optional[tuple[int, int]] = None,
        aspect_ratios: Optional[List[str]] = None,
        aspect_ratio_tolerance: float = 0.05,
        on_format_error_detail: Optional[Union[str, Callable[[Any], str]]] = None,
        on_resolution_error_detail: Optional[Union[str, Callable[[Any], str]]] = None,
        on_aspect_ratio_error_detail: Optional[Union[str, Callable[[Any], str]]] = None,
        **kwargs: Any,
    ):
        """
        Initializes the ImageValidator.

        Args:
            allowed_formats: List of allowed image formats (e.g., ['JPEG', 'PNG']).
            min_resolution: (width, height) tuple for minimum dimensions.
            max_resolution: (width, height) tuple for maximum dimensions.
            exact_resolution: (width, height) tuple for exact dimensions.
            aspect_ratios: List of allowed aspect ratios (e.g., ['16:9', '1:1']).
            aspect_ratio_tolerance: Float for allowed deviation from aspect ratios.
            on_size_error_detail: Custom error for size failures.
            on_type_error_detail: Custom error for content-type failures.
            on_filename_error_detail: Custom error for filename failures.
            on_format_error_detail: Custom error for format (Pillow) failures.
            on_resolution_error_detail: Custom error for resolution failures.
            on_aspect_ratio_error_detail: Custom error for aspect ratio failures.
            **kwargs: Catches all parent arguments.
        """
        if not PIL:
            raise ImportError(
                "The 'Pillow' library is required for ImageValidator. "
                "Install it with 'pip install fastapi-assets[image]'"
            )
        
        # Set default image content types if not overridden
        if "content_types" not in kwargs:
            kwargs["content_types"] = _DEFAULT_IMAGE_CONTENT_TYPES

        kwargs["error_detail"] = (
            "Image validation failed." if "error_detail" not in kwargs else kwargs["error_detail"]
        )

        # Initialize parent FileValidator
        super().__init__(**kwargs)

        # Store image-specific rules
        # Normalize formats to uppercase for reliable comparison
        self._allowed_formats = [f.upper() for f in allowed_formats] if allowed_formats else None
        self._min_resolution = min_resolution
        self._max_resolution = max_resolution
        self._exact_resolution = exact_resolution

        # Store original string ratios for error messages
        self._aspect_ratio_strings = aspect_ratios
        self._aspect_ratios = self._parse_aspect_ratios(aspect_ratios)
        self._aspect_ratio_tolerance = aspect_ratio_tolerance

        # Store image-specific error details
        self._format_error_detail = on_format_error_detail
        self._resolution_error_detail = on_resolution_error_detail
        self._aspect_ratio_error_detail = on_aspect_ratio_error_detail

    def _parse_aspect_ratios(self, ratios: Optional[List[str]]) -> Optional[List[float]]:
        """Helper to convert 'W:H' strings to float ratios.
        Args:
            ratios: List of aspect ratio strings (e.g., ['16:9']).
        Returns:
            List of float ratios (e.g., [1.777...]) or None.
        """
        if not ratios:
            return None
        parsed = []
        for r in ratios:
            try:
                w_str, h_str = r.split(":")
                w, h = int(w_str), int(h_str)
                if h == 0:
                    raise ValueError("Aspect ratio height cannot be zero.")
                parsed.append(w / h)
            except (ValueError, AttributeError, TypeError):
                raise ValueError(
                    f"Invalid aspect_ratios format: '{r}'. Expected 'W:H' (e.g., '16:9')."
                )
        return parsed

    async def __call__(self, file: UploadFile = File(...), **kwargs: Any) -> StarletteUploadFile:
        """
        FastAPI dependency entry point for image validation.
        Args:
            file: The uploaded image file to validate.
        Returns:
            The validated UploadFile object.
        """
        # Run all parent validations (size, content-type, filename)
        # This will also rewind the file stream to position 0.
        try:
            await super().__call__(file, **kwargs)
        except ValidationError as e:
            # Re-raise the exception from the parent
            self._raise_error(status_code=e.status_code, detail=str(e.detail))

        # Run image-specific validations using Pillow
        img = None
        try:
            # `file.file` is a SpooledTemporaryFile, which Image.open can read.
            img = Image.open(file.file)

            # Perform content-based validations
            self._validate_format(img)
            self._validate_resolution(img)
            self._validate_aspect_ratio(img)

        except (UnidentifiedImageError, IOError) as e:
            # Pillow couldn't identify it as an image, or file is corrupt
            detail = (
                self._format_error_detail
                or f"File is not a valid image or is corrupted. Error: {e}"
            )
            self._raise_error(status_code=415, detail=detail)

        except ValidationError as e:
            # One of our own _validate methods failed
            self._raise_error(status_code=e.status_code, detail=str(e.detail))

        except Exception as e:
            # Catch-all for other unexpected errors during Pillow validation
            await file.close()
            self._raise_error(
                status_code=400,
                detail=f"An unexpected error occurred during image validation: {e}",
            )
        finally:
            if img:
                img.close()

            # CRITICAL: Rewind the file stream *again* so the endpoint
            # can read it after Pillow is done.
            await file.seek(0)

        return file

    def _validate_format(self, img: Image.Image) -> None:
        """Checks the image's actual format (e.g., 'JPEG', 'PNG').
        Args:
            img: The opened PIL Image object.
        Returns:
            None
        Raises:
            ValidationError: If the image format is not allowed.
        """
        if not self._allowed_formats:
            return  # No rule set

        img_format = img.format
        if not img_format or img_format not in self._allowed_formats:
            detail = self._format_error_detail or (
                f"Unsupported image format: '{img_format}'. "
                f"Allowed formats are: {', '.join(self._allowed_formats)}"
            )
            # 415 Unsupported Media Type
            raise ValidationError(detail=str(detail), status_code=415)

    def _validate_resolution(self, img: Image.Image) -> None:
        """Checks image dimensions against min, max, and exact constraints.
        Args:
            img: The opened PIL Image object.
        Returns:
            None
        Raises:
            ValidationError: If the image resolution is out of bounds
        """
        if not (self._min_resolution or self._max_resolution or self._exact_resolution):
            return  # No resolution rules set

        width, height = img.size
        err_msg = None

        if self._exact_resolution:
            ex_w, ex_h = self._exact_resolution
            if (width, height) != (ex_w, ex_h):
                err_msg = f"Image resolution must be exactly {ex_w}x{ex_h}. Got {width}x{height}."

        if err_msg is None and self._min_resolution:
            min_w, min_h = self._min_resolution
            if width < min_w or height < min_h:
                err_msg = (
                    f"Image resolution ({width}x{height}) is below the minimum of {min_w}x{min_h}."
                )

        if err_msg is None and self._max_resolution:
            max_w, max_h = self._max_resolution
            if width > max_w or height > max_h:
                err_msg = (
                    f"Image resolution ({width}x{height}) exceeds the maximum of {max_w}x{max_h}."
                )

        if err_msg:
            detail = self._resolution_error_detail or err_msg
            raise ValidationError(detail=str(detail), status_code=400)

    def _validate_aspect_ratio(self, img: Image.Image) -> None:
        """Checks the image's aspect ratio against a list of allowed ratios.
        Args:
            img: The opened PIL Image object.
        Returns:
            None
        Raises:
            ValidationError: If the image's aspect ratio is not allowed.
        """
        if not self._aspect_ratios:
            return  # No rule set

        width, height = img.size
        if height == 0:
            raise ValidationError(
                detail="Image has zero height and aspect ratio cannot be calculated.",
                status_code=400,
            )

        actual_ratio = width / height

        for target_ratio in self._aspect_ratios:
            if abs(actual_ratio - target_ratio) <= self._aspect_ratio_tolerance:
                return  # Valid match found

        # No match found
        ratio_strings = self._aspect_ratio_strings or []
        detail = self._aspect_ratio_error_detail or (
            f"Image aspect ratio ({width}:{height} ≈ {actual_ratio:.2f}) is not allowed. "
            f"Allowed ratios are: {', '.join(ratio_strings)}"
        )
        raise ValidationError(detail=str(detail), status_code=400)
