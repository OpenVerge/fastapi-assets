"""
Professional test suite for the CSVValidator class.

This suite uses pytest, pytest-asyncio, and a factory fixture to simulate
FastAPI UploadFile objects for validation.
"""

import sys
import tempfile
from typing import Callable, Generator

import pytest
from fastapi import UploadFile, HTTPException

# --- Module under test ---
# (Adjust this import path based on your project structure)
# We assume the code is in: fastapi_assets/validators/csv_validator.py
from fastapi_assets.validators.csv_validator import CSVValidator

# Mock pandas for the dependency test
# We set pd to None to simulate it not being installed
try:
    import pandas as pd
except ImportError:
    pd = None


# --- Fixtures ---


@pytest.fixture
def mock_upload_file_factory() -> Generator[Callable[..., UploadFile], None, None]:
    """
    Provides a factory to create mock FastAPI UploadFile objects.
    These are backed by SpooledTemporaryFile, just like FastAPI.
    """
    # Keep track of files to close during cleanup
    files_to_close = []

    def _create_file(
        content: str,
        filename: str = "test.csv",
        content_type: str = "text/csv",
        encoding: str = "utf-8",
    ) -> UploadFile:
        """
        Creates a mock UploadFile object.

        Args:
            content: The string content to write to the file.
            filename: The name of the file.
            content_type: The MIME type of the file.
            encoding: The encoding to use for writing bytes.

        Returns:
            A FastAPI UploadFile instance.
        """
        # SpooledTemporaryFile is what FastAPI uses under the hood
        file_obj = tempfile.SpooledTemporaryFile()

        # Write content as bytes
        file_obj.write(content.encode(encoding))

        # Rewind to the start so it can be read
        file_obj.seek(0)

        # Create the UploadFile instance
        upload_file = UploadFile(
            file=file_obj,
            filename=filename,
            headers={"content-type": content_type},
        )
        files_to_close.append(file_obj)
        return upload_file

    # Yield the factory function to the tests
    yield _create_file

    # --- Teardown ---
    # Close all files created by the factory
    for f in files_to_close:
        f.close()


# --- Test Cases ---


@pytest.mark.asyncio
class TestCSVValidator:
    """Groups all tests for the CSVValidator."""

    # --- Basic Success and File Handling ---

    async def test_happy_path_validation(self, mock_upload_file_factory: Callable[..., UploadFile]):
        """
        Tests a valid CSV file that passes all checks.
        """
        csv_content = "id,name,email\n1,Alice,a@b.com\n2,Bob,c@d.com"
        validator = CSVValidator(
            max_size="1MB",
            required_columns=["id", "name"],
            disallowed_columns=["password"],
            min_rows=2,
            max_rows=10,
        )

        file = mock_upload_file_factory(csv_content)

        # Should not raise any exception
        validated_file = await validator(file)
        assert validated_file is file

    async def test_file_is_rewound_after_validation(
        self, mock_upload_file_factory: Callable[..., UploadFile]
    ):
        """
        Crucial test: Ensures the file is readable by the endpoint
        after validation is complete.
        """
        csv_content = "id,name\n1,Alice\n2,Bob"
        validator = CSVValidator(required_columns=["id"], min_rows=2)

        file = mock_upload_file_factory(csv_content)

        # Run validation
        await validator(file)

        # Check if the file pointer is at the beginning
        assert await file.read() == csv_content.encode("utf-8")

    # --- Dependency Check ---

    def test_pandas_dependency_check(self, monkeypatch):
        """
        Tests that CSVValidator raises an ImportError if pandas is not installed.
        """
        # Temporarily simulate pandas not being installed
        monkeypatch.setattr(sys.modules[__name__], "pd", None)

        # Reload the module to trigger the check at the top
        # Note: This is tricky. A better way is to test the __init__ check.
        # The user's code has the check in __init__, which is good.

        # Reset the 'pd' value in the validator module itself
        monkeypatch.setattr("fastapi_assets.validators.csv_validator.pd", None)

        with pytest.raises(ImportError) as exc:
            CSVValidator()

        assert "pandas" in str(exc.value).lower()

        # Restore pandas for other tests
        monkeypatch.setattr("fastapi_assets.validators.csv_validator.pd", pd)

    # --- CSV-Specific Validations ---

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "encoding, content, should_pass",
        [
            ("utf-8", "id,name\n1,Café", True),  # Café has non-ASCII character (é)
            ("ascii", "id,name\n1,Café", False),  # Fails ascii check due to é
            ("latin-1", "id,name\n1,Café", True),  # Passes latin-1
        ],
    )
    async def test_encoding_validation(
        self, mock_upload_file_factory, encoding, content, should_pass
    ):
        """Tests the file encoding check."""
        if should_pass:
            validator = CSVValidator(encoding=encoding)
            file = mock_upload_file_factory(content, encoding=encoding)
            await validator(file)
        else:
            # For the failure case, try to validate UTF-8 content with ASCII constraint
            # Create UTF-8 file with non-ASCII character (é in Café)
            file_fail = mock_upload_file_factory("id,name\n1,Café", encoding="utf-8")
            # Validator expects ASCII only
            validator_fail = CSVValidator(encoding="ascii")
            with pytest.raises(HTTPException) as exc:
                await validator_fail(file_fail)
            assert "File encoding is not one of the allowed" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_delimiter_validation(self, mock_upload_file_factory):
        """Tests the delimiter check."""
        csv_content = "id|name\n1|Alice"

        # Success case
        validator_pass = CSVValidator(delimiter="|", required_columns=["id", "name"])
        await validator_pass(mock_upload_file_factory(csv_content))

        # Fail case (default delimiter is ',')
        validator_fail = CSVValidator(required_columns=["id", "name"])
        with pytest.raises(HTTPException) as exc:
            # Pandas fails to find 'id' and 'name'
            await validator_fail(mock_upload_file_factory(csv_content))
        assert "missing required columns" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_column_validations(self, mock_upload_file_factory):
        """Tests required, exact, and disallowed columns."""
        csv_content = "id,name,email,secret_key\n1,Alice,a@b.com,xyz"

        # Test Required (Pass)
        validator_req = CSVValidator(required_columns=["id", "email"])
        await validator_req(mock_upload_file_factory(csv_content))

        # Test Required (Fail)
        validator_req_fail = CSVValidator(required_columns=["id", "timestamp"])
        with pytest.raises(HTTPException) as exc:
            await validator_req_fail(mock_upload_file_factory(csv_content))
        assert "missing required columns" in str(exc.value.detail)
        assert "timestamp" in str(exc.value.detail)

        # Test Disallowed (Pass)
        validator_dis = CSVValidator(disallowed_columns=["password"])
        await validator_dis(mock_upload_file_factory(csv_content))

        # Test Disallowed (Fail)
        validator_dis_fail = CSVValidator(disallowed_columns=["name", "secret_key"])
        with pytest.raises(HTTPException) as exc:
            await validator_dis_fail(mock_upload_file_factory(csv_content))
        assert "contains disallowed columns" in str(exc.value.detail)
        assert "secret_key" in str(exc.value.detail)

        # Test Exact (Fail - wrong order)
        validator_ex_fail = CSVValidator(exact_columns=["id", "email", "name", "secret_key"])
        with pytest.raises(HTTPException) as exc:
            await validator_ex_fail(mock_upload_file_factory(csv_content))
        assert "does not match exactly" in str(exc.value.detail)

        # Test Exact (Success)
        validator_ex_pass = CSVValidator(exact_columns=["id", "name", "email", "secret_key"])
        await validator_ex_pass(mock_upload_file_factory(csv_content))

    @pytest.mark.asyncio
    @pytest.mark.parametrize("header_check_only", [True, False])
    async def test_row_count_validation(self, mock_upload_file_factory, header_check_only):
        """
        Tests min_rows and max_rows for both efficient and full-read modes.
        CSV content has 3 data rows.
        """
        csv_content = "id,name\n1,Alice\n2,Bob\n3,Charlie"

        # Test min_rows (Fail)
        validator_min = CSVValidator(min_rows=4, header_check_only=header_check_only)
        with pytest.raises(HTTPException) as exc_min:
            await validator_min(mock_upload_file_factory(csv_content))
        assert "minimum required rows" in str(exc_min.value.detail)

        # Test max_rows (Fail)
        validator_max = CSVValidator(max_rows=2, header_check_only=header_check_only)
        with pytest.raises(HTTPException) as exc_max:
            await validator_max(mock_upload_file_factory(csv_content))
        assert "exceeds maximum allowed rows" in str(exc_max.value.detail)

        # Test success (in bounds)
        validator_pass = CSVValidator(min_rows=3, max_rows=3, header_check_only=header_check_only)
        await validator_pass(mock_upload_file_factory(csv_content))

    # --- Error Handling and Custom Messages ---

    @pytest.mark.asyncio
    async def test_csv_parsing_error(self, mock_upload_file_factory):
        """Tests a malformed CSV that causes a pandas ParserError."""
        # Row 2 has an extra field
        csv_content = "id,name\n1,Alice\n2,Bob,extra\n3,Charlie"

        validator = CSVValidator()
        with pytest.raises(HTTPException) as exc:
            await validator(mock_upload_file_factory(csv_content))

        assert exc.value.status_code == 400
        assert "Failed to parse CSV file" in str(exc.value.detail)
        # Check that the underlying pandas error is included
        assert "expected 2 fields" in str(exc.value.detail).lower()

    @pytest.mark.asyncio
    async def test_custom_error_messages(self, mock_upload_file_factory):
        """Tests that custom error messages override defaults."""
        csv_content = "id,name,password\n1,Alice,xyz"

        # Custom column error
        validator_col = CSVValidator(
            disallowed_columns=["password"],
            on_column_error_detail="Cannot upload file with password.",
        )
        with pytest.raises(HTTPException) as exc_col:
            await validator_col(mock_upload_file_factory(csv_content))
        assert exc_col.value.detail == "Cannot upload file with password."

        # Custom row error
        validator_row = CSVValidator(
            min_rows=5,
            on_row_error_detail="File must have at least 5 data rows.",
        )
        with pytest.raises(HTTPException) as exc_row:
            await validator_row(mock_upload_file_factory(csv_content))
        assert exc_row.value.detail == "File must have at least 5 data rows."

    # --- Inherited Validation ---

    @pytest.mark.asyncio
    async def test_inherited_max_size_validation(self, mock_upload_file_factory):
        """
        Tests that the parent FileValidator's max_size check still works.
        Note: This tests the streaming size check as file.size is None.
        """
        csv_content = "id,name\n1,Alice\n2,Bob\n3,Charlie"  # ~40 bytes

        validator = CSVValidator(max_size="20B")
        file = mock_upload_file_factory(csv_content)

        with pytest.raises(HTTPException) as exc:
            await validator(file)

        assert exc.value.status_code == 413  # 413 Payload Too Large
        assert "exceeds" in str(exc.value.detail).lower()
        assert "20B" in str(exc.value.detail)
