@echo off
setlocal enabledelayedexpansion

REM List of Python versions to test
for %%V in (3.12 3.13) do (
    echo =======================================
    echo Testing on Python %%V
    echo =======================================
    uv run --python %%V pytest
    if errorlevel 1 (
        echo Tests failed on Python %%V
        exit /b 1
    )
)

echo =======================================
echo All Python version tests completed successfully
echo =======================================
endlocal
