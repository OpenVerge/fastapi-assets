"""Module providing the CSVValidator for validating CSV files."""

from typing import Any, Callable, List, Optional, Union
from fastapi import File, UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile

# Import from base file_validator module
from fastapi_assets.core import ValidationError
from fastapi_assets.validators.file_validator import (
    FileValidator,
)

# Handle Optional Pandas Dependency
try:
    import pandas as pd
except ImportError:
    pd = None


class CSVValidator(FileValidator):
    r"""
    A specialized dependency for validating CSV `UploadFile` objects.

    It inherits all checks from `FileValidator` (size, filename) and adds
    CSV-specific checks for encoding, delimiter, columns, and row counts.

    This validator requires the 'pandas' library. Install it with:
    `pip install fastapi-asserts[pandas]`

    .. code-block:: python
        from fastapi import FastAPI, UploadFile, Depends
        from fastapi_assets.validators import CSVValidator

        app = FastAPI()

        csv_validator = CSVValidator(
            max_size="5MB",
            encoding='utf-8',
            delimiter=',',
            required_columns=['id', 'name', 'email'],
            disallowed_columns=['password'],
            min_rows=1,
            max_rows=1000,
            header_check_only=True # Efficiently check rows
        )

        @app.post("/upload-csv/")
        async def upload_csv_file(file: UploadFile = Depends(csv_validator)):
            # File is guaranteed to be a valid CSV within spec
            return {"filename": file.filename, "status": "validated"}
    """

    _DEFAULT_CSV_CONTENT_TYPES = ["text/csv", "application/vnd.ms-excel"]

    def __init__(
        self,
        *,
        # CSV-Specific Arguments
        encoding: Optional[Union[str, List[str]]] = None,
        delimiter: Optional[str] = None,
        required_columns: Optional[List[str]] = None,
        exact_columns: Optional[List[str]] = None,
        disallowed_columns: Optional[List[str]] = None,
        min_rows: Optional[int] = None,
        max_rows: Optional[int] = None,
        header_check_only: bool = True,
        # CSV-Specific Error Messages
        on_encoding_error_detail: Optional[Union[str, Callable[[Any], str]]] = None,
        on_column_error_detail: Optional[Union[str, Callable[[Any], str]]] = None,
        on_row_error_detail: Optional[Union[str, Callable[[Any], str]]] = None,
        on_parse_error_detail: Optional[Union[str, Callable[[Any], str]]] = None,
        # Inherited FileValidator Arguments
        **kwargs: Any,
    ):
        """
        Initializes the CSVValidator.

        Args:
            encoding: A string or list of allowed file encodings (e.g., 'utf-8').
            delimiter: The expected delimiter (e.g., ',').
            required_columns: List of column names that must be present.
            exact_columns: List of column names that must match the header exactly.
            disallowed_columns: List of column names that must not be present.
            min_rows: Minimum number of data rows (excluding header).
            max_rows: Maximum number of data rows (excluding header).
            header_check_only: If True (default), validates rows efficiently
                by reading only enough of the file to check bounds. If False,
                streams the entire file to get an exact row count.
            on_encoding_error_detail: Custom error message for encoding failures.
            on_column_error_detail: Custom error message for column validation failures.
            on_row_error_detail: Custom error message for row count failures.
            on_parse_error_detail: Custom error message for general CSV parsing errors.
            **kwargs: Any additional keyword arguments to pass to the parent class.
        """
        if not pd:
            raise ImportError(
                "The 'pandas' library is required for CSVValidator. "
                "Install it with 'pip install fastapi-assets[pandas]'"
            )

        kwargs["content_types"] = kwargs.get("content_types", self._DEFAULT_CSV_CONTENT_TYPES)

        kwargs["error_detail"] = kwargs.get("error_detail", "CSV file validation failed.")

        # Initialize parent FileValidator
        super().__init__(**kwargs)

        # Store CSV-specific rules
        self._encoding = [encoding] if isinstance(encoding, str) else encoding
        self._delimiter = delimiter
        self._required_columns = set(required_columns) if required_columns else None
        self._exact_columns = exact_columns
        self._disallowed_columns = set(disallowed_columns) if disallowed_columns else None
        self._min_rows = min_rows
        self._max_rows = max_rows
        self._header_check_only = header_check_only

        # Store CSV-specific error details
        self._encoding_error_detail = on_encoding_error_detail
        self._column_error_detail = on_column_error_detail
        self._row_error_detail = on_row_error_detail
        self._parse_error_detail = on_parse_error_detail

    async def __call__(self, file: UploadFile = File(...)) -> StarletteUploadFile:
        """
        FastAPI dependency entry point for CSV validation.

        Runs parent validations (size, type, filename) first, then
        performs CSV-specific validations (encoding, structure).
        Args:
            file: The uploaded CSV file to validate.
        Returns:
            The validated UploadFile object.
        Raises:
            HTTPException: If validation fails.
        """
        # Run all parent validations (size, content-type, filename)
        # This will also rewind the file (await file.seek(0))
        try:
            await self._validate(file=file)
        except ValidationError as e:
            await file.close()
            # Re-raise parent's validation error
            self._raise_error(status_code=e.status_code, detail=str(e.detail))
        except Exception as e:
            # Catch pandas errors (e.g., CParserError, UnicodeDecodeError)
            await file.close()
            detail = self._parse_error_detail or f"Failed to parse CSV file: {e}"
            self._raise_error(status_code=400, detail=detail)
        try:
            # CRITICAL: Rewind the file AGAIN so the endpoint can read it.
            await file.seek(0)
            return file
        except Exception as e:
            await file.close()
            self._raise_error(
                status_code=e.status_code if hasattr(e, "status_code") else 400,
                detail="File could not be rewound after validation.",
            )
            return None  # type: ignore  # pragma: no cover

    async def _validate(self, file: UploadFile) -> None:
        """
        Runs all CSV-specific validation checks on the uploaded file.

        This method orchestrates the validation pipeline: first calls parent
        FileValidator validations, then validates encoding, and finally
        validates the CSV structure (columns and rows).

        Args:
            file: The uploaded file to validate.

        Returns:
            None

        Raises:
            ValidationError: If any validation check fails.
        """
        await super()._validate(file)
        await self._validate_encoding(file)
        await file.seek(0)
        await self._validate_csv_structure(file)

    async def _validate_encoding(self, file: UploadFile) -> None:
        """
        Validates that the file encoding matches one of the allowed encodings.

        Reads a small chunk of the file and attempts to decode it with each
        specified encoding. If none match, raises a ValidationError.

        Args:
            file: The uploaded file to validate.

        Returns:
            None

        Raises:
            ValidationError: If the file encoding is not one of the allowed encodings.
        """
        if not self._encoding:
            return  # No check needed

        # Read a small chunk to test encoding
        chunk = await file.read(self._DEFAULT_CHUNK_SIZE)
        if not chunk:
            return  # Empty file, let other validators handle

        valid_encoding_found = False
        for enc in self._encoding:
            try:
                chunk.decode(enc)
                valid_encoding_found = True
                break  # Found a valid one
            except UnicodeDecodeError:
                continue  # Try next encoding

        if not valid_encoding_found:
            detail = self._encoding_error_detail or (
                f"File encoding is not one of the allowed: {', '.join(self._encoding)}"
            )
            raise ValidationError(detail=str(detail), status_code=400)

    def _check_columns(self, header: List[str]) -> None:
        """
        Validates the CSV header against configured column rules.

        Checks for required columns, disallowed columns, and exact column matching
        based on the validator's configuration. Raises ValidationError if any
        rule is violated.

        Args:
            header: List of column names extracted from the CSV header row.

        Returns:
            None

        Raises:
            ValidationError: If exact columns don't match, required columns are missing,
                or disallowed columns are present.
        """
        header_set = set(header)

        # Exact columns (checks order and content)
        if self._exact_columns:
            if header != self._exact_columns:
                detail = self._column_error_detail or (
                    f"CSV header does not match exactly. "
                    f"Expected: {self._exact_columns}. Got: {header}"
                )
                raise ValidationError(detail=str(detail), status_code=400)
            return  # If exact match is required, other checks are redundant

        # Required columns
        if self._required_columns:
            missing = self._required_columns - header_set
            if missing:
                detail = self._column_error_detail or (
                    f"CSV is missing required columns: {sorted(list(missing))}"
                )
                raise ValidationError(detail=str(detail), status_code=400)

        # Disallowed columns
        if self._disallowed_columns:
            found_disallowed = self._disallowed_columns.intersection(header_set)
            if found_disallowed:
                detail = self._column_error_detail or (
                    f"CSV contains disallowed columns: {sorted(list(found_disallowed))}"
                )
                raise ValidationError(detail=str(detail), status_code=400)

    def _check_row_counts(self, total_rows: int) -> None:
        """
        Validates that the CSV row count meets min/max constraints.

        Compares the actual number of data rows against the configured
        minimum and maximum row limits. Raises ValidationError if constraints
        are violated.

        Args:
            total_rows: The total number of data rows (excluding header) in the CSV.

        Returns:
            None

        Raises:
            ValidationError: If the row count is below minimum or exceeds maximum.
        """
        if self._min_rows is not None and total_rows < self._min_rows:
            detail = self._row_error_detail or (
                f"File does not meet minimum required rows: {self._min_rows}. Found: {total_rows}."
            )
            raise ValidationError(detail=str(detail), status_code=400)

        if self._max_rows is not None and total_rows > self._max_rows:
            detail = self._row_error_detail or (
                f"File exceeds maximum allowed rows: {self._max_rows}. Found: {total_rows}."
            )
            raise ValidationError(detail=str(detail), status_code=400)

    async def _validate_csv_structure(self, file: UploadFile) -> None:
        """
        Validates the CSV structure including columns and row counts using pandas.

        This method handles both efficient bounded reads (checking only necessary rows)
        and full file reads depending on the `header_check_only` setting. It validates
        column constraints first, then row count constraints if applicable.

        Args:
            file: The uploaded CSV file to validate.

        Returns:
            None

        Raises:
            ValidationError: If column validation fails, row count validation fails,
                or if the file cannot be parsed as valid CSV.
        """
        # file.file is the underlying SpooledTemporaryFile
        file_obj = file.file

        # Common pandas parameters
        read_params = {
            "delimiter": self._delimiter,
            # Use the first encoding if specified, otherwise let pandas infer
            "encoding": self._encoding[0] if self._encoding else None,
            "on_bad_lines": "error",  # Fail on malformed rows
        }

        # Column Validation (always efficient)
        column_check_needed = (
            self._required_columns or self._exact_columns or self._disallowed_columns
        )

        if column_check_needed:
            try:
                # Read *only* the header row
                df_header = pd.read_csv(file_obj, nrows=0, **read_params)
                await file.seek(0)  # Rewind after header read
                header_list = list(df_header.columns)
                self._check_columns(header_list)
            except ValidationError:
                # Re-raise ValidationError from _check_columns
                raise
            except Exception as e:
                # Catches pandas errors during header parse
                raise ValidationError(detail=f"Failed to read CSV header: {e}", status_code=400)

        # Row Validation
        row_check_needed = self._min_rows is not None or self._max_rows is not None

        # If no validation is needed, do a basic parse to ensure the file is valid CSV
        if not row_check_needed and not column_check_needed:
            try:
                # Do a basic parse to catch malformed CSV (e.g., inconsistent field count)
                # Read up to 1000 rows to validate format without consuming entire file
                pd.read_csv(file_obj, nrows=1000, **read_params)
                await file.seek(0)
            except Exception as e:
                raise ValidationError(detail=f"Failed to parse CSV file: {e}", status_code=400)
            return  # We are done

        if not row_check_needed:
            return  # We are done

        try:
            # Full Read (header_check_only=False)
            if not self._header_check_only:
                total_rows = 0
                # Use chunksize for memory-efficient full read
                for chunk_df in pd.read_csv(file_obj, chunksize=10_000, **read_params):
                    total_rows += len(chunk_df)
                await file.seek(0)  # Rewind after full read
                self._check_row_counts(total_rows)

            # Efficient Bounded Read (header_check_only=True)
            else:
                # We read *just enough* rows to check bounds
                rows_to_read = None
                if self._max_rows is not None:
                    # Read max_rows + 1 data rows.
                    rows_to_read = self._max_rows + 1

                if self._min_rows is not None:
                    # Ensure we read at least min_rows
                    rows_to_read = max(rows_to_read or 0, self._min_rows)

                # Read at most 'rows_to_read'
                df_rows = pd.read_csv(file_obj, nrows=rows_to_read, **read_params)
                await file.seek(0)  # Rewind after bounded read
                actual_rows = len(df_rows)

                # Check max_rows: If we read max_rows + 1, it's an error
                if self._max_rows is not None and actual_rows > self._max_rows:
                    detail = self._row_error_detail or (
                        f"File exceeds maximum allowed rows: {self._max_rows}."
                    )
                    raise ValidationError(detail=str(detail), status_code=400)

                # Check min_rows: If we read N rows and got < min_rows, it's an error
                if self._min_rows is not None and actual_rows < self._min_rows:
                    detail = self._row_error_detail or (
                        f"File does not meet minimum required rows: {self._min_rows}."
                    )
                    raise ValidationError(detail=str(detail), status_code=400)

        except ValidationError:
            # Re-raise ValidationError from _check_row_counts
            raise
        except Exception as e:
            # Catches pandas errors during row parse (e.g., ParserError)
            if self._parse_error_detail:
                detail_msg = (
                    self._parse_error_detail(e)
                    if callable(self._parse_error_detail)
                    else self._parse_error_detail
                )
            else:
                detail_msg = f"Failed to parse CSV file: {e}"
            raise ValidationError(detail=detail_msg, status_code=400)
