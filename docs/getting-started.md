# Getting Started with FastAPI Assets

Welcome to FastAPI Assets! This comprehensive guide will help you install, configure, and start using FastAPI Assets in your FastAPI applications.

## Table of Contents

1. [Installation](#installation)
2. [Basic Setup](#basic-setup)
3. [Your First Validator](#your-first-validator)
4. [Common Patterns](#common-patterns)
5. [Error Handling](#error-handling)
6. [Next Steps](#next-steps)

## Installation

### Requirements

- Python 3.12 or higher
- FastAPI 0.119.1 or higher

### Basic Installation

To install FastAPI Assets with core functionality:

```bash
pip install fastapi-assets
```

### Installation with Optional Dependencies

For image validation support:

```bash
pip install fastapi-assets[image]
```

For CSV validation support:

```bash
pip install fastapi-assets[pandas]
```

For all features:

```bash
pip install fastapi-assets[image,pandas]
```

### Verify Installation

To verify that FastAPI Assets is installed correctly:

```python
import fastapi_assets
print(fastapi_assets.__version__)
```

## Basic Setup

### Minimal FastAPI Application

Here's a minimal FastAPI application with FastAPI Assets:

```python
from fastapi import FastAPI, UploadFile, Depends
from fastapi_assets.validators import FileValidator

app = FastAPI()

# Create a file validator instance
file_validator = FileValidator(
    max_size="10MB",
    content_types=["image/jpeg", "image/png"]
)

@app.post("/upload/")
async def upload_file(file: UploadFile = Depends(file_validator)):
    """Upload and validate a file."""
    return {
        "filename": file.filename,
        "content_type": file.content_type
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Your First Validator

### File Upload Validation

FileValidator is the foundation for all file validation in FastAPI Assets. Here's how to use it:

```python
from fastapi import FastAPI, UploadFile, Depends
from fastapi_assets.validators import FileValidator

app = FastAPI()

# Create validators for different use cases
profile_photo_validator = FileValidator(
    max_size="2MB",
    min_size="10KB",
    content_types=["image/jpeg", "image/png", "image/gif"],
    filename_pattern=r"^[\w\s-]+\.(jpg|jpeg|png|gif)$"
)

document_validator = FileValidator(
    max_size="20MB",
    content_types=["application/pdf", "application/msword"]
)

@app.post("/upload/profile-photo/")
async def upload_profile_photo(
    file: UploadFile = Depends(profile_photo_validator)
):
    """Upload a profile photo with validation."""
    return {"filename": file.filename, "size": file.size}

@app.post("/upload/document/")
async def upload_document(
    file: UploadFile = Depends(document_validator)
):
    """Upload a document with validation."""
    return {"filename": file.filename}
```

### Image Validation

For specialized image validation with Pillow:

```python
from fastapi_assets.validators import ImageValidator

app = FastAPI()

image_validator = ImageValidator(
    max_size="5MB",
    allowed_formats=["JPEG", "PNG"],
    min_resolution=(800, 600),
    max_resolution=(4000, 4000),
    aspect_ratios=["1:1", "16:9"]
)

@app.post("/upload/image/")
async def upload_image(file: UploadFile = Depends(image_validator)):
    """Upload and validate an image file."""
    return {"filename": file.filename, "status": "validated"}
```

### CSV Validation

For CSV file validation with schema checking:

```python
from fastapi_assets.validators import CSVValidator

app = FastAPI()

csv_validator = CSVValidator(
    encoding="utf-8",
    delimiter=",",
    required_columns=["id", "name", "email"],
    disallowed_columns=["password"],
    min_rows=1,
    max_rows=10000
)

@app.post("/upload/csv/")
async def upload_csv(file: UploadFile = Depends(csv_validator)):
    """Upload and validate a CSV file."""
    return {"filename": file.filename, "status": "validated"}
```

## Common Patterns

### Reusable Validators

It's best practice to define validators once and reuse them:

```python
# validators.py
from fastapi_assets.validators import FileValidator, ImageValidator

# Profile images
profile_image_validator = ImageValidator(
    max_size="2MB",
    allowed_formats=["JPEG", "PNG"],
    min_resolution=(200, 200)
)

# Documents
pdf_validator = FileValidator(
    max_size="10MB",
    content_types=["application/pdf"]
)

# Avatars
avatar_validator = ImageValidator(
    max_size="512KB",
    allowed_formats=["PNG"],
    min_resolution=(64, 64),
    max_resolution=(256, 256),
)
```

Then import and use in your routes:

```python
# routes.py
from fastapi import FastAPI, UploadFile, Depends
from .validators import profile_image_validator, pdf_validator, avatar_validator

app = FastAPI()

@app.post("/profile/photo/")
async def update_profile_photo(
    file: UploadFile = Depends(profile_image_validator)
):
    return {"status": "uploaded"}

@app.post("/submit/document/")
async def submit_document(
    file: UploadFile = Depends(pdf_validator)
):
    return {"status": "submitted"}

@app.post("/avatar/")
async def upload_avatar(
    file: UploadFile = Depends(avatar_validator)
):
    return {"status": "updated"}
```

### Multiple Validators

You can combine multiple validators in a single endpoint:

```python
from fastapi_assets.validators import FileValidator, ImageValidator
from fastapi_assets.request_validators import QueryValidator

app = FastAPI()

image_validator = ImageValidator(max_size="5MB")
quality_validator = QueryValidator(
    "quality",
    _type=str,
    allowed_values=["high", "medium", "low"]
)

@app.post("/process/image/")
async def process_image(
    file: UploadFile = Depends(image_validator),
    quality: str = Depends(quality_validator())
):
    """Process an image with specified quality."""
    return {"filename": file.filename, "quality": quality}
```

### Custom Error Messages

Customize validation error messages:

```python
file_validator = FileValidator(
    max_size="5MB",
    min_size="100KB",
    content_types=["image/*"],
    on_size_error_detail="File must be between 100KB and 5MB",
    on_type_error_detail="Only image files are allowed",
    on_filename_error_detail="Filename contains invalid characters"
)
```

### Dynamic Error Messages

Use callables for dynamic error messages:

```python
def size_error_message(value):
    return f"File size {value} bytes exceeds the limit"

file_validator = FileValidator(
    max_size="5MB",
    on_size_error_detail=size_error_message
)
```

## Error Handling

### Understanding Validation Errors

When validation fails, FastAPI Assets raises HTTPException with appropriate status codes:

```python
# Automatic error handling
@app.post("/upload/")
async def upload_file(file: UploadFile = Depends(file_validator)):
    # If validation fails, a 400 error is automatically returned
    return {"filename": file.filename}
```


### Common Error Status Codes

- **400**: Bad Request - Validation failed (default)
- **413**: Payload Too Large - File exceeds max_size
- **415**: Unsupported Media Type - Content type not allowed

### Custom Status Codes

```python
file_validator = FileValidator(
    max_size="5MB",
    status_code=422  # Unprocessable Entity
)
```

## Request Parameter Validation

### Query Parameters

```python
from fastapi_assets.request_validators import QueryValidator

app = FastAPI()

page_validator = QueryValidator(
    "page",
    _type=int,
    default=1,
    ge=1,
    le=1000
)

sort_validator = QueryValidator(
    "sort",
    _type=str,
    allowed_values=["name", "date", "size"],
    default="name"
)

@app.get("/items/")
async def list_items(
    page: int = Depends(page_validator()),
    sort: str = Depends(sort_validator())
):
    return {"page": page, "sort": sort}
```

### Header Validation

```python
from fastapi_assets.request_validators import HeaderValidator

app = FastAPI()

auth_header_validator = HeaderValidator(
    "authorization",
    pattern=r"^Bearer [A-Za-z0-9\-._~\+\/]+=*$"
)

@app.get("/protected/")
async def protected_endpoint(
    authorization: str = Depends(auth_header_validator())
):
    return {"status": "authorized"}
```

### Cookie Validation

```python
from fastapi_assets.request_validators import CookieValidator

app = FastAPI()

session_cookie_validator = CookieValidator(
    "session_id",
    pattern=r"^[a-f0-9]{32}$"
)

@app.get("/dashboard/")
async def dashboard(
    session_id: str = Depends(session_cookie_validator())
):
    return {"session": session_id}
```


## Next Steps

- Read the [API Reference](./api-reference.md) for detailed documentation on all validators
- Check out [Examples](./examples.md) for real-world use cases
- Explore [Custom Validators](./custom_validators.md) to create your own validation logic
- Review the [Contributing Guide](./CONTRIBUTING.md) if you want to contribute

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Starlette Documentation](https://www.starlette.io/)

---

**Need Help?**

- Open an issue on [GitHub](https://github.com/OpenVerge/fastapi-assets)
