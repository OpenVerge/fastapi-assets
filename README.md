# FastAPI Assets

<div align="center">

[![Python Versions](https://img.shields.io/badge/python-3.10%20--%203.14-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0%2B-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Code Style](https://img.shields.io/badge/Code%20Style-Ruff-black.svg)](https://github.com/astral-sh/ruff)

A powerful validation and assertion toolkit for FastAPI applications.

[Documentation](https://openverge.github.io/fastapi-assets/) · [Examples](./docs/examples.md) · [Contributing](./docs/CONTRIBUTING.md)

</div>

---

## Overview

**FastAPI Assets** is a comprehensive validation toolkit designed specifically for FastAPI applications. It simplifies the process of validating file uploads, request metadata, and HTTP parameters, ensuring that your application handles user input securely and efficiently.

FastAPI Assets provides:

- **File Validators** - Validate file uploads with size, MIME type, and filename checks
- **Image Validators** - Specialized validation for image files (format, dimensions, aspect ratio)
- **CSV Validators** - Validate CSV structure, encoding, columns, and row counts
- **Request Validators** - Validate headers, query parameters, path parameters, and cookies
- **Custom Validators** - Create custom validation logic with sync or async support
- **Granular Error Messages** - Fine-grained error control for precise user feedback
- **Type-Safe** - Full type hints and runtime type validation
- **Light Weight** - Minimal dependencies; optional extras for specific features

## Quick Start

### Installation

```bash
# Basic installation
pip install fastapi-assets

# With image support (includes Pillow)
pip install fastapi-assets[image]

# With CSV support (includes pandas)
pip install fastapi-assets[pandas]

# With all optional features
pip install fastapi-assets[image,pandas]
```

## Features

### File Validators

- **FileValidator** - General-purpose file validation
  - File size validation (min/max with human-readable formats)
  - MIME type validation with wildcard support
  - Filename pattern validation
  - Custom validator functions

- **ImageValidator** - Specialized image validation
  - Image format validation (JPEG, PNG, WebP, GIF, BMP, TIFF)
  - Image dimension validation
  - Aspect ratio validation
  - Inherits all FileValidator features

- **CSVValidator** - CSV file validation (requires pandas)
  - CSV encoding validation
  - Required/disallowed columns
  - Row count validation
  - Header-only validation option

### Request Validators

- **HeaderValidator** - HTTP header validation
  - Pattern matching with regex
  - Predefined formats (UUID4, email, Bearer token, etc.)
  - Allowed values restriction
  - Custom validators

- **QueryValidator** - Query parameter validation
  - Type conversion and validation
  - Allowed values restriction
  - Numeric range validation
  - Pattern matching

- **PathValidator** - Path parameter validation
  - Type conversion
  - Pattern matching
  - Range validation

- **CookieValidator** - Cookie value validation
  - Pattern matching
  - Required value validation
  - Custom validators

### Advanced Features

- **Granular Error Messages** - Customize error messages for each validation type
- **Custom Validators** - Add custom validation logic (sync or async)
- **HTTP Status Codes** - Customize HTTP response codes per validator
- **Type Safety** - Full type hints for IDE support and type checking

## Documentation

Comprehensive documentation is available at [https://openverge.github.io/fastapi-assets/](https://openverge.github.io/fastapi-assets/)

- [Getting Started](./docs/getting-started.md) - Installation and basic usage
- [API Reference](./docs/api-reference.md) - Complete API documentation
- [Examples](./docs/examples.md) - Practical usage examples
- [Custom Validators](./docs/custom_validators.md) - Creating custom validation logic


## Project Structure

```
fastapi-assets/
├── fastapi_assets/
│   ├── core/                    # Core validation framework
│   │   ├── base_validator.py   # Abstract base validator
│   │   └── exceptions.py        # Custom exceptions
│   ├── validators/              # File validators
│   │   ├── file_validator.py
│   │   ├── image_validator.py
│   │   ├── csv_validator.py
│   │   └── utils.py
│   └── request_validators/      # HTTP request validators
│       ├── header_validator.py
│       ├── query_validator.py
│       ├── path_validator.py
│       └── cookie_validator.py
├── tests/                       # Comprehensive test suite
├── docs/                        # Documentation
└── pyproject.toml              # Project configuration
```


## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](./docs/CONTRIBUTING.md) for guidelines.

## Code of Conduct

Please read [CODE_OF_CONDUCT.md](./docs/CODE_OF_CONDUCT.md) before contributing.

## License

This project is licensed under the MIT License - see the [LICENSE.txt](LICENSE.txt) file for details.



---

**FastAPI Assets** - Making FastAPI validation simple, secure, and intuitive.

*Version 0.1.0* | *Last Updated: November 2025*


