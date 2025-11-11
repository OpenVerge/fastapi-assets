# FastAPI Assets Documentation

**FastAPI Assets** is a powerful, production-ready validation and assertion toolkit designed specifically for FastAPI applications. It simplifies the process of validating file uploads and request metadata, ensuring that your application handles user input securely and efficiently.

## Overview

FastAPI Assets provides a comprehensive suite of validators that integrate seamlessly with FastAPI's dependency injection system. Whether you're validating file uploads, image files, CSV data, or request parameters, FastAPI Assets provides intuitive, type-safe APIs that make validation simple and robust.

### Why FastAPI Assets?

- **Security First**: Built with security best practices to prevent common vulnerabilities
- **Performance Optimized**: Efficient streaming validation that doesn't load entire files into memory
- **Type Safe**: Full type hints and modern Python support for better IDE integration
- **Modular Design**: Use only what you need - validators are independent and composable
- **Well Documented**: Comprehensive API documentation and practical examples
- **Thoroughly Tested**: Extensive test coverage ensures reliability
- **Extensible**: Easily add custom validators and extend functionality

## Key Features

### File Validation
- Validate file size with flexible size format support (e.g., "10MB", "1KB")
- Check MIME types with wildcard pattern support
- Validate filename patterns with regex
- Efficient streaming for large files

### Image Validation
- Inherit all file validation capabilities
- Verify image format and integrity using Pillow
- Validate image dimensions (width and height)
- Check aspect ratios
- Support for multiple image formats (JPEG, PNG, GIF, WebP, BMP, TIFF)

### CSV Validation
- All file validation features
- Schema validation (required/disallowed columns)
- Encoding validation
- Row count constraints
- Delimiter customization
- Header verification
- Efficient header-only checks

### Request Parameter Validation
- **Query Validators**: Validate query strings with allowed values and constraints
- **Header Validators**: Validate HTTP headers 
- **Cookie Validators**: Validate cookie values
- **Path Validators**: Validate path segments with custom rules

## Quick Start

### Installation

```bash
pip install fastapi-assets
```

For extended functionality:

```bash
pip install fastapi-assets[image,pandas]
```

### Basic File Upload Validation

```python
from fastapi import FastAPI, UploadFile, Depends
from fastapi_assets.validators import FileValidator

app = FastAPI()

# Create a file validator
file_validator = FileValidator(
    max_size="10MB",
    min_size="1KB",
    content_types=["image/jpeg", "image/png"]
)

@app.post("/upload/")
async def upload_file(file: UploadFile = Depends(file_validator)):
    return {
        "filename": file.filename,
        "size": file.size,
        "content_type": file.content_type
    }
```

## Documentation

- [Getting Started](./getting-started.md) - Installation, setup, and basic usage patterns
- [API Reference](./api-reference.md) - Complete API documentation for all validators
- [Examples](./examples.md) - Real-world usage examples and best practices
- [Contributing](./CONTRIBUTING.md) - Guidelines for contributing to the project

## Project Structure

```
fastapi-assets/
├── fastapi_assets/
│   ├── core/              # Core validation framework
│   ├── validators/        # File, image, and CSV validators
│   └── request_validators/# Query, header, cookie, path validators
├── tests/                 # Comprehensive test suite
├── docs/                  # Documentation
└── pyproject.toml         # Project configuration
```

## Requirements

- Python 3.12+
- FastAPI 0.119.1+

## Optional Dependencies

- **image**: Pillow 12.0.0+ for image validation
- **pandas**: Pandas 2.3.3+ for CSV validation


## Support

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/OpenVerge/fastapi-assets).
