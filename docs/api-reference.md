# API Reference

Complete API documentation for FastAPI Assets validators and utilities.

## Core Module

### BaseValidator

**Module**: `fastapi_assets.core.base_validator`

Abstract base class for all validators in FastAPI Assets. Provides standardized error handling and HTTP exception raising.

#### Class Definition

```python
class BaseValidator(abc.ABC):
    """Abstract base class for creating reusable FastAPI validation dependencies."""
```

#### Parameters

- **status_code** (int, default: 400): HTTP status code to return on validation failure
- **error_detail** (Union[str, Callable], default: "Validation failed."): Error message or callable that generates error messages
- **validators** (Optional[List[Callable]], default: None): List of custom validation functions

#### Methods

##### `_raise_error()`

Raises a standardized HTTPException with resolved error detail.

```python
def _raise_error(
    self,
    value: Optional[Any] = None,
    status_code: Optional[int] = None,
    detail: Optional[Union[str, Callable[[Any], str]]] = None,
) -> None:
    """Raises HTTPException with validated error message."""
```

**Parameters**:
- `value`: The value that failed validation
- `status_code`: Override default status code
- `detail`: Override default error detail

**Raises**: `HTTPException` with resolved status code and detail

---

### ValidationError

**Module**: `fastapi_assets.core.exceptions`

Custom exception raised by validators during validation logic.

```python
class ValidationError(Exception):
    """Raised when validation logic fails."""
    
    def __init__(
        self,
        detail: str,
        status_code: int = 400
    ):
        self.detail = detail
        self.status_code = status_code
```

---

## File Validators

### FileValidator

**Module**: `fastapi_assets.validators.file_validator`

General-purpose validator for file uploads with size, MIME type, and filename validation.

#### Class Definition

```python
class FileValidator(BaseValidator):
    """Validates UploadFile objects for size, MIME type, and filename patterns."""
```

#### Parameters

- **max_size** (Optional[Union[str, int]], default: None): Maximum file size (e.g., "10MB", 1024)
- **min_size** (Optional[Union[str, int]], default: None): Minimum file size (e.g., "1KB")
- **content_types** (Optional[List[str]], default: None): Allowed MIME types with wildcard support
- **filename_pattern** (Optional[str], default: None): Regex pattern for filename validation
- **on_size_error_detail** (Optional[Union[str, Callable]], default: None): Custom error message for size validation
- **on_type_error_detail** (Optional[Union[str, Callable]], default: None): Custom error message for content type
- **on_filename_error_detail** (Optional[Union[str, Callable]], default: None): Custom error message for filename
- **status_code** (int, default: 400): HTTP status code on validation failure
- **error_detail** (Union[str, Callable], default: "Validation failed"): Default error message
- **validators** (Optional[List[Callable]], default: None): List of custom validators

#### Size Format Support

| Format | Example | Bytes |
|--------|---------|-------|
| Bytes | `"1024"` or `"1024B"` | 1024 |
| Kilobytes | `"5KB"` or `"5 KB"` | 5120 |
| Megabytes | `"10MB"` or `"10 MB"` | 10485760 |
| Gigabytes | `"1GB"` or `"1 GB"` | 1073741824 |
| Terabytes | `"1TB"` or `"1 TB"` | 1099511627776 |

#### MIME Type Wildcards

| Pattern | Matches |
|---------|---------|
| `"image/*"` | All image types (jpeg, png, gif, etc.) |
| `"text/*"` | All text types (plain, html, css, etc.) |
| `"application/*"` | All application types |
| `"image/jpeg"` | Specific MIME type only |

---

### ImageValidator

**Module**: `fastapi_assets.validators.image_validator`

Specialized validator for image files with format, dimensions, and aspect ratio validation.

#### Parameters

Inherits all FileValidator parameters plus:

- **allowed_formats** (Optional[List[str]], default: None): Allowed image formats (e.g., ["JPEG", "PNG"])
- **min_resolution** (Optional[Tuple[int, int]], default: None): Minimum image resolution (width, height)
- **max_resolution** (Optional[Tuple[int, int]], default: None): Maximum image resolution (width, height)
- **aspect_ratios** (Optional[List[str]], default: None): Allowed aspect ratios (e.g., ["1:1", "16:9"])
- **on_format_error_detail** (Optional[Union[str, Callable]], default: None): Custom error for format
- **on_dimension_error_detail** (Optional[Union[str, Callable]], default: None): Custom error for dimensions
- **on_aspect_ratio_error_detail** (Optional[Union[str, Callable]], default: None): Custom error for aspect ratio

#### Supported Formats

- JPEG / JPG
- PNG
- GIF
- WebP
- BMP
- TIFF

---

### CSVValidator

**Module**: `fastapi_assets.validators.csv_validator`

Specialized validator for CSV files with schema, encoding, and row count validation.

**Requirements**: Install with `pip install fastapi-assets[pandas]`

#### Parameters

Inherits all FileValidator parameters plus:

- **encoding** (Optional[Union[str, List[str]]], default: None): Allowed encoding(s) for CSV
- **delimiter** (Optional[str], default: None): CSV delimiter character
- **required_columns** (Optional[List[str]], default: None): Columns that must exist
- **disallowed_columns** (Optional[List[str]], default: None): Columns that must not exist
- **min_rows** (Optional[int], default: None): Minimum number of data rows
- **max_rows** (Optional[int], default: None): Maximum number of data rows
- **header_check_only** (bool, default: False): Only validate headers without checking all rows
- **on_encoding_error_detail** (Optional[Union[str, Callable]], default: None): Custom encoding error
- **on_columns_error_detail** (Optional[Union[str, Callable]], default: None): Custom columns error
- **on_rows_error_detail** (Optional[Union[str, Callable]], default: None): Custom rows error

---

## Request Validators

### QueryValidator

**Module**: `fastapi_assets.request_validators.query_validator`

Validator for FastAPI query parameters with support for allowed values and constraints.

#### Parameters

- **param_name** (str): Name of the query parameter
- **_type** (type, default: str): Parameter type (int, str, float, bool, etc.)
- **default** (Optional[Any], default: None): Default value if parameter is missing
- **allowed_values** (Optional[List[Any]], default: None): List of allowed values
- **pattern** (Optional[str], default: None): Regex pattern for string validation
- **ge** (Optional[Union[int, float]], default: None): Greater than or equal to
- **le** (Optional[Union[int, float]], default: None): Less than or equal to
- **gt** (Optional[Union[int, float]], default: None): Greater than
- **lt** (Optional[Union[int, float]], default: None): Less than
- **error_detail** (Union[str, Callable], default: "Validation failed"): Error message
- **status_code** (int, default: 400): HTTP status code on validation failure

---

### HeaderValidator

**Module**: `fastapi_assets.request_validators.header_validator`

Comprehensive validator for HTTP headers with pattern matching, format validation, allowed values, and custom validators. Extends FastAPI's `Header` dependency with granular error control.

#### Class Definition

```python
class HeaderValidator(BaseValidator):
    """
    A dependency for validating HTTP headers with extended rules.
    
    Provides pattern matching, format validation, allowed values,
    and custom validators with fine-grained error messages.
    """
```

#### Parameters

- **default** (Any, default: Undefined): Default value if header is missing. If not provided, header is required.
- **alias** (Optional[str], default: None): The actual header name to extract (e.g., "X-API-Key", "Authorization")
- **convert_underscores** (bool, default: True): If True, underscores in parameter name convert to hyphens in header name
- **pattern** (Optional[str], default: None): Regex pattern that header value must match (cannot be used with `format`)
- **format** (Optional[str], default: None): Predefined format name for validation
- **allowed_values** (Optional[List[str]], default: None): List of exact string values allowed for the header
- **validators** (Optional[List[Callable]], default: None): List of custom validation functions (sync or async)
- **title** (Optional[str], default: None): Title for the header in OpenAPI documentation
- **description** (Optional[str], default: None): Description for the header in OpenAPI documentation
- **on_required_error_detail** (str, default: "Required header is missing."): Error message if header is missing
- **on_pattern_error_detail** (str, default: "Header has an invalid format."): Error message if pattern/format fails
- **on_allowed_values_error_detail** (str, default: "Header value is not allowed."): Error message if value not in allowed list
- **on_custom_validator_error_detail** (str, default: "Header failed custom validation."): Error message if custom validator fails
- **status_code** (int, default: 400): HTTP status code for validation errors
- **error_detail** (str, default: "Header Validation Failed"): Generic fallback error message


---

### CookieValidator

**Module**: `fastapi_assets.request_validators.cookie_validator`

Validator for cookie values with pattern matching and constraints.

#### Parameters

- **alias** (str): Name of the cookie to validate
- **pattern** (Optional[str], default: None): Regex pattern for cookie value
- **error_detail** (Union[str, Callable], default: "Validation failed"): Error message
- **status_code** (int, default: 400): HTTP status code on validation failure

---

### PathValidator

**Module**: `fastapi_assets.request_validators.path_validator`

Validator for path parameters with type conversion and pattern matching.

#### Parameters

- **param_name** (str): Name of the path parameter
- **_type** (type, default: str): Parameter type
- **pattern** (Optional[str], default: None): Regex pattern for validation
- **error_detail** (Union[str, Callable], default: "Validation failed"): Error message
- **status_code** (int, default: 400): HTTP status code on validation failure

---


## Exceptions
### ValidationError
The `ValidationError` exception is raised when a validation check fails. It provides details about the nature of the validation failure, allowing developers to handle errors gracefully in their applications.
