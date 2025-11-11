# Contributing to FastAPI Assets
Thank you for your interest in contributing to FastAPI Assets! We welcome contributions from the community to help improve and expand this project. Whether you're fixing bugs, adding new features, or improving documentation, your contributions are valuable.

## Reporting Bugs

Before creating bug reports, check the issue list. When creating a bug report, include:

- **Use a clear descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples to demonstrate the steps**
- **Describe the behavior you observed and what the problem is**
- **Explain which behavior you expected to see instead**
- **Include Python version, FastAPI Assets version, and OS information**
- **Include relevant error messages and stack traces**

## Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Use a clear descriptive title**
- **Provide a step-by-step description of the suggested enhancement**
- **Provide specific examples to demonstrate the steps**
- **Describe the current behavior and expected behavior**
- **Explain why this enhancement would be useful**

## Pull Requests

- Fill in the required template
- Include appropriate test cases
- Update documentation and examples
- End all files with a newline

## Development Setup

### Prerequisites

- Python 3.12 or higher
- Git
- pip

### Setting Up Development Environment

1. **Fork the repository**

```bash
# Go to the GitHub repository and click "Fork"
```

2. **Clone your fork**

```bash
git clone https://github.com/YOUR_USERNAME/fastapi-assets.git
cd fastapi-assets
```

3. **Create a virtual environment**

```bash
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Unix/macOS:
source venv/bin/activate
```

4. **Install dependencies with development extras**

```bash
pip install -e ".[dev,image,pandas]"
```

5. **Create a feature branch**

```bash
git checkout -b feature/your-feature-name
```

## Development Workflow

### Code Style

FastAPI Assets uses:
- **Ruff** for linting and formatting
- **MyPy** for type checking
- **Pytest** for testing

### Running Linting

```bash
ruff check fastapi_assets tests
ruff format fastapi_assets tests
```

### Running Type Checks

```bash
mypy fastapi_assets
```

### Running Tests

```bash
pytest
pytest --cov=fastapi_assets
pytest tests/test_file_validator.py -v
```

## Making Changes

1. Create a feature branch
2. Make your changes with type hints and docstrings
3. Format your code with ruff
4. Run tests to ensure everything passes
5. Run type checks with mypy
6. Commit with clear messages following conventional commits
7. Push to your fork
8. Create a pull request

## Code of Conduct

By participating in this project, you agree to abide by the Contributor Covenant Code of Conduct.

