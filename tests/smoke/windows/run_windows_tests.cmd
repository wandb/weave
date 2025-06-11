@echo off
REM Simple batch script to run Weave Windows smoke tests

echo === Weave Windows Smoke Test Runner (CMD) ===
echo.

REM Check if we should use container
if "%1"=="container" goto :container_test

:native_test
echo Running tests natively...
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -e ../../..
python -m pip install pytest

REM Set environment variables
set WEAVE_SMOKE_TEST=1
set PYTHONUNBUFFERED=1

REM Run tests
echo.
echo Running smoke tests...
python -m pytest test_windows_smoke.py -v
if errorlevel 1 (
    echo.
    echo ERROR: Tests failed!
    exit /b 1
)
goto :success

:container_test
echo Running tests in Windows container...
echo.

REM Check Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not installed or not running!
    exit /b 1
)

REM Change to repo root
pushd ..\..\.

REM Build container if requested
if "%2"=="build" (
    echo Building Windows container...
    docker build -f tests/smoke/windows/Dockerfile.windows -t weave-windows-test:latest .
    if errorlevel 1 (
        echo ERROR: Failed to build container!
        popd
        exit /b 1
    )
)

REM Run tests in container
echo Running tests in container...
docker run --rm -e WEAVE_SMOKE_TEST=1 -e PYTHONUNBUFFERED=1 weave-windows-test:latest
if errorlevel 1 (
    echo ERROR: Tests failed in container!
    popd
    exit /b 1
)

popd

:success
echo.
echo SUCCESS: All tests passed!
exit /b 0 