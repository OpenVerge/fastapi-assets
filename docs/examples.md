# Examples & Use Cases

This document provides practical examples demonstrating how to use FastAPI Assets in real-world scenarios.

## Table of Contents

1. [File Upload Examples](#file-upload-examples)
2. [Image Processing](#image-processing)
3. [CSV Import](#csv-import)
4. [Request Parameter Validation](#request-parameter-validation)
5. [Error Handling](#error-handling)
6. [Advanced Patterns](#advanced-patterns)

## File Upload Examples

### Basic File Upload

Simple file upload with size and type validation:

```python
from fastapi import FastAPI, UploadFile, Depends
from fastapi_assets.validators import FileValidator

app = FastAPI()

# Create a simple file validator
file_validator = FileValidator(
    max_size="10MB",
    content_types=["application/pdf"]
)

@app.post("/upload/pdf/")
async def upload_pdf(file: UploadFile = Depends(file_validator)):
    """Upload a PDF file."""
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": file.size
    }
```

### Multiple File Type Support

Accepting multiple file types with different validators:

```python
from fastapi import FastAPI, UploadFile, Depends
from fastapi_assets.validators import FileValidator

app = FastAPI()

# PDF validator
pdf_validator = FileValidator(
    max_size="20MB",
    content_types=["application/pdf"]
)

# Image validator
image_validator = FileValidator(
    max_size="5MB",
    content_types=["image/jpeg", "image/png", "image/gif"]
)

# Document validator
doc_validator = FileValidator(
    max_size="15MB",
    content_types=[
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
)

@app.post("/upload/document/")
async def upload_document(file: UploadFile = Depends(pdf_validator)):
    return {"type": "pdf", "filename": file.filename}

@app.post("/upload/image/")
async def upload_image(file: UploadFile = Depends(image_validator)):
    return {"type": "image", "filename": file.filename}

@app.post("/upload/document-word/")
async def upload_word_document(file: UploadFile = Depends(doc_validator)):
    return {"type": "word", "filename": file.filename}
```

### Filename Validation

Validating filenames with regex patterns:

```python
from fastapi_assets.validators import FileValidator

# Only allow alphanumeric filenames with specific extensions
strict_filename_validator = FileValidator(
    max_size="5MB",
    filename_pattern=r"^[a-zA-Z0-9_\-]+\.(pdf|doc|docx|txt)$",
    on_filename_error_detail="Filename must contain only letters, numbers, hyphens, and underscores"
)

@app.post("/upload/")
async def upload_with_filename_validation(
    file: UploadFile = Depends(strict_filename_validator)
):
    return {"filename": file.filename}
```

---

## Image Processing

### Profile Photo Upload

Validate profile photos with size and dimension constraints:

```python
from fastapi_assets.validators import ImageValidator

# Profile photo validator
profile_validator = ImageValidator(
    max_size="2MB",
    min_size="100KB",
    allowed_formats=["JPEG", "PNG"],
    min_resolution=(200, 200),
    max_resolution=(4000, 4000),
    on_size_error_detail="Profile photo must be between 100KB and 2MB",
    on_dimension_error_detail="Image must be at least 200x200 pixels"
)

@app.post("/profile/photo/")
async def upload_profile_photo(
    file: UploadFile = Depends(profile_validator)
):
    """Upload and validate a profile photo."""
    return {
        "filename": file.filename,
        "status": "validated",
        "message": "Profile photo updated successfully"
    }
```

### Avatar Upload

Strict square image validation for avatars:

```python
# Avatar validator - strict square format
avatar_validator = ImageValidator(
    max_size="512KB",
    allowed_formats=["PNG"],
    min_resolution=(64, 64),
    max_resolution=(256, 256),
    aspect_ratios=["1:1"],
)

@app.post("/avatar/")
async def upload_avatar(file: UploadFile = Depends(avatar_validator)):
    """Upload user avatar."""
    return {"filename": file.filename, "type": "avatar"}
```

### Banner/Hero Image

Landscape image validation:

```python
# Banner validator - landscape format
banner_validator = ImageValidator(
    max_size="10MB",
    allowed_formats=["JPEG", "PNG", "WebP"],
    min_resolution=(1920, 1080),
    aspect_ratios=["16:9", "4:3"],
)

@app.post("/banner/")
async def upload_banner(file: UploadFile = Depends(banner_validator)):
    """Upload banner image."""
    return {"filename": file.filename, "type": "banner"}
```

### Image Gallery Upload

Multiple image format support:

```python
# Gallery validator - flexible dimensions
gallery_validator = ImageValidator(
    max_size="8MB",
    allowed_formats=["JPEG", "PNG", "WebP", "GIF"],
   min_resolution=(800, 600),
   max_resolution=(5000, 5000),
)

@app.post("/gallery/images/")
async def upload_gallery_image(file: UploadFile = Depends(gallery_validator)):
    """Upload image to gallery."""
    return {"filename": file.filename, "type": "gallery"}
```

---

## CSV Import

### User Data Import

Import user data from CSV with schema validation:

```python
from fastapi_assets.validators import CSVValidator

# User data CSV validator
user_csv_validator = CSVValidator(
    max_size="5MB",
    encoding="utf-8",
    delimiter=",",
    required_columns=["id", "name", "email", "phone"],
    min_rows=1,
    max_rows=10000,
    on_columns_error_detail="CSV must contain: id, name, email, phone"
)

@app.post("/import/users/")
async def import_users(file: UploadFile = Depends(user_csv_validator)):
    """Import users from CSV."""
    # In real app, you would parse and import the data
    return {
        "filename": file.filename,
        "status": "imported",
        "message": "Users imported successfully"
    }
```

### Sales Data Import

CSV with flexible encoding support:

```python
# Sales data validator
sales_validator = CSVValidator(
    max_size="50MB",
    encoding=["utf-8", "latin-1"],  # Support multiple encodings
    delimiter=",",
    required_columns=["date", "product_id", "quantity", "price"],
    disallowed_columns=["internal_notes", "cost"],
    min_rows=1,
    max_rows=100000,
    header_check_only=True  # Don't validate every row for performance
)

@app.post("/import/sales/")
async def import_sales(file: UploadFile = Depends(sales_validator)):
    """Import sales data from CSV."""
    return {
        "filename": file.filename,
        "status": "imported",
        "message": "Sales data imported successfully"
    }
```

### Student Records Import

CSV with strict column validation:

```python
# Student records validator
student_csv_validator = CSVValidator(
    max_size="10MB",
    encoding="utf-8",
    delimiter=",",
    required_columns=["student_id", "first_name", "last_name", "email", "grade"],
    disallowed_columns=["ssn", "password"],  # Never allow sensitive data
    min_rows=1,
    max_rows=50000
)

@app.post("/import/students/")
async def import_student_records(file: UploadFile = Depends(student_csv_validator)):
    """Import student records."""
    return {
        "filename": file.filename,
        "status": "imported"
    }
```

---

## Request Parameter Validation

### Query Parameter Validation

Validate pagination and filtering:

```python
from fastapi_assets.request_validators import QueryValidator

app = FastAPI()

# Pagination parameters
page_validator = QueryValidator(
    "page",
    _type=int,
    default=1,
    ge=1,
    le=1000
)

per_page_validator = QueryValidator(
    "per_page",
    _type=int,
    default=20,
    ge=1,
    le=100
)

# Status filter
status_validator = QueryValidator(
    "status",
    _type=str,
    allowed_values=["active", "inactive", "pending"],
    default="active"
)

@app.get("/items/")
async def list_items(
    page: int = Depends(page_validator()),
    per_page: int = Depends(per_page_validator()),
    status: str = Depends(status_validator())
):
    """List items with pagination and filtering."""
    return {
        "page": page,
        "per_page": per_page,
        "status": status,
        "total": 1000
    }
```

### Header Validation

Validate authorization and custom headers:

```python
from fastapi_assets.request_validators import HeaderValidator

app = FastAPI()

# Authorization header validator
auth_validator = HeaderValidator(
    "authorization",
    pattern=r"^Bearer [A-Za-z0-9\-._~\+\/]+=*$"
)

# API key header validator
api_key_validator = HeaderValidator(
    "x-api-key",
    pattern=r"^[a-f0-9]{32}$"
)

@app.get("/protected/")
async def protected_endpoint(
    auth: str = Depends(auth_validator())
):
    """Protected endpoint requiring authorization."""
    return {"status": "authorized"}

@app.post("/api/data/")
async def api_endpoint(
    api_key: str = Depends(api_key_validator())
):
    """API endpoint requiring API key."""
    return {"status": "authenticated"}
```

### Cookie Validation

Validate session and preference cookies:

```python
from fastapi_assets.request_validators import CookieValidator

app = FastAPI()

# Session cookie validator
session_validator = CookieValidator(
    "session_id",
    pattern=r"^[a-f0-9]{32}$"
)

@app.get("/dashboard/")
async def dashboard(
    session_id: str = Depends(session_validator())
):
    """Dashboard requiring valid session."""
    return {"session": session_id, "user": "john_doe"}
```

---

## Error Handling

### Custom Error Messages

Provide user-friendly error messages:

```python
from fastapi_assets.validators import FileValidator

# Validator with custom error messages
file_validator = FileValidator(
    max_size="5MB",
    min_size="100KB",
    content_types=["application/pdf"],
    on_size_error_detail="File must be between 100KB and 5MB. Please try again.",
    on_type_error_detail="Only PDF files are accepted. Please upload a PDF.",
    on_filename_error_detail="Filename contains invalid characters."
)

@app.post("/upload/")
async def upload_file(file: UploadFile = Depends(file_validator)):
    return {"filename": file.filename}
```

### Dynamic Error Messages

Generate contextual error messages:

```python
from fastapi_assets.validators import FileValidator

def format_size_error(size_bytes):
    # Convert bytes to human-readable format
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"File is {size_bytes:.1f}{unit}, but maximum is 5MB"
        size_bytes /= 1024
    return "File is too large"

file_validator = FileValidator(
    max_size="5MB",
    on_size_error_detail=format_size_error
)

@app.post("/upload/")
async def upload_file(file: UploadFile = Depends(file_validator)):
    return {"filename": file.filename}
```

### Global Exception Handler

Custom error response format:

```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "path": str(request.url.path),
            "timestamp": str(datetime.now())
        }
    )
```

---

## Advanced Patterns

### Reusable Validator Configuration

Create a module for centralized validator definitions:

```python
# validators.py
from fastapi_assets.validators import FileValidator, ImageValidator, CSVValidator

# Profile validators
profile_photo = ImageValidator(
    max_size="2MB",
    allowed_formats=["JPEG", "PNG"],
    min_resolution=(200, 200)
)

profile_banner = ImageValidator(
    max_size="5MB",
    allowed_formats=["JPEG", "PNG", "WebP"],
    min_resolution=(1200, 600)
)

# Document validators
pdf_document = FileValidator(
    max_size="20MB",
    content_types=["application/pdf"]
)

resume = FileValidator(
    max_size="5MB",
    content_types=["application/pdf", "application/msword"],
    filename_pattern=r"^[a-zA-Z0-9_\-]+\.(pdf|doc|docx)$"
)

# Data validators
user_data_csv = CSVValidator(
    max_size="10MB",
    required_columns=["id", "name", "email"],
    max_rows=50000
)

# routes.py
from fastapi import FastAPI, UploadFile, Depends
from . import validators

app = FastAPI()

@app.post("/profile/photo/")
async def update_profile_photo(
    file: UploadFile = Depends(validators.profile_photo)
):
    return {"status": "updated"}

@app.post("/upload/resume/")
async def upload_resume(
    file: UploadFile = Depends(validators.resume)
):
    return {"status": "uploaded"}

@app.post("/import/users/")
async def import_users(
    file: UploadFile = Depends(validators.user_data_csv)
):
    return {"status": "imported"}
```

### Conditional Validation

Validate based on conditions:

```python
from fastapi import FastAPI, UploadFile, Depends, Query
from fastapi_assets.validators import FileValidator, ImageValidator

app = FastAPI()

# Validators for different upload types
image_validator = ImageValidator(max_size="5MB")
document_validator = FileValidator(max_size="20MB")

@app.post("/upload/")
async def upload_file(
    file: UploadFile = Depends(),
    upload_type: str = Query(..., regex="^(image|document)$")
):
    """Upload file with type-specific validation."""
    if upload_type == "image":
        validator = image_validator
    else:
        validator = document_validator
    
    # Validate the file
    validated_file = await validator(file)
    
    return {
        "type": upload_type,
        "filename": validated_file.filename
    }
```

### Combined Validators

Use file and request validators together:

```python
from fastapi_assets.validators import ImageValidator
from fastapi_assets.request_validators import QueryValidator

app = FastAPI()

image_validator = ImageValidator(
    max_size="5MB",
    allowed_formats=["JPEG", "PNG"]
)

quality_validator = QueryValidator(
    "quality",
    _type=str,
    allowed_values=["low", "medium", "high"],
    default="medium"
)

compression_validator = QueryValidator(
    "compress",
    _type=bool,
    default=False
)

@app.post("/upload/image/")
async def upload_and_process_image(
    file: UploadFile = Depends(image_validator),
    quality: str = Depends(quality_validator()),
    compress: bool = Depends(compression_validator())
):
    """Upload and process image with options."""
    return {
        "filename": file.filename,
        "quality": quality,
        "compress": compress,
        "status": "processed"
    }
```

### Batch File Upload with Validation

Handle multiple files with individual validation:

```python
from typing import List

@app.post("/upload/images/batch/")
async def upload_images_batch(
    files: List[UploadFile] = Depends()
):
    """Upload multiple images with validation."""
    results = []
    
    for file in files:
        try:
            # Validate each file
            validated_file = await image_validator(file)
            results.append({
                "filename": file.filename,
                "status": "success",
                "size": file.size
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })
    
    return {"results": results}
```

---

## Best Practices

1. **Define validators once** - Create validators in a separate module and reuse them
2. **Use meaningful error messages** - Help users understand what went wrong
3. **Set reasonable limits** - Balance security with user experience
4. **Log validation failures** - Track issues for debugging
5. **Test validators** - Unit test your validators independently
6. **Document requirements** - Clearly document file requirements in API docs
7. **Consider performance** - Use `header_check_only=True` for large CSV files

---


