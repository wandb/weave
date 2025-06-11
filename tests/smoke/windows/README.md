# Weave Windows Smoke Tests

This directory (`tests/smoke/windows/`) contains Windows-specific smoke tests to validate that Weave works correctly on Windows containers and Windows environments.

## Overview

The smoke tests cover:
- Basic Weave initialization and import
- Op decorators and function tracing
- Nested operations
- Exception handling
- Complex data types
- Windows-specific file path handling
- Unicode support
- Basic concurrent operations

## Running Tests Locally

**Note:** All commands should be run from the repository root unless otherwise specified.

### Prerequisites

For native testing:
- Windows 10/11 or Windows Server 2019/2022
- Python 3.9+ installed
- Git for Windows

For container testing:
- Docker Desktop for Windows with Windows containers enabled
- Windows 10/11 Pro/Enterprise or Windows Server

### Using PowerShell Script

The easiest way to run tests locally is using the provided PowerShell script:

```powershell
# Run tests natively
cd tests/smoke/windows
.\run_windows_tests.ps1

# Run tests in a Windows container
.\run_windows_tests.ps1 -UseContainer -BuildContainer

# Run with verbose output
.\run_windows_tests.ps1 -Verbose
```

### Manual Testing

#### Native Windows Testing

```powershell
# Install dependencies (from repo root)
pip install -e .
pip install pytest

# Run smoke tests
cd tests/smoke/windows
python -m pytest test_windows_smoke.py -v
```

#### Container Testing

```powershell
# Build the Windows container (from repo root)
docker build -f tests/smoke/windows/Dockerfile.windows -t weave-windows-test:latest .

# Run tests in the container
docker run --rm weave-windows-test:latest

# Run with custom command
docker run --rm weave-windows-test:latest python -m pytest tests/smoke/windows/test_windows_smoke.py -v --tb=short
```

## CI/CD Integration

The Windows smoke tests are automatically run in GitHub Actions when:
- Code is pushed to master/main branches
- Pull requests are created
- Manual workflow dispatch is triggered

The workflow runs tests:
1. In Windows containers
2. Natively on Windows runners with Python 3.9, 3.10, and 3.11

## Test Structure

### `test_windows_smoke.py`
Main test file containing all smoke tests:
- `test_windows_environment()` - Verifies Windows environment
- `test_weave_import()` - Tests Weave can be imported
- `test_weave_init()` - Tests Weave initialization
- `test_basic_op()` - Tests basic op functionality
- `test_nested_ops()` - Tests nested operations
- `test_op_with_exceptions()` - Tests exception handling
- `test_op_with_complex_types()` - Tests complex data types
- `test_file_paths_windows()` - Tests Windows file paths
- `test_unicode_support()` - Tests Unicode handling
- `test_concurrent_ops()` - Tests concurrent operations

### `tests/smoke/windows/Dockerfile.windows`
Windows container definition:
- Based on Windows Server Core LTSC 2022
- Installs Python 3.11
- Installs Weave and dependencies
- Runs smoke tests by default

### `.github/workflows/windows-smoke-test.yaml`
GitHub Actions workflow for CI/CD:
- Runs tests on Windows Server 2022
- Tests in both containers and native environments
- Multiple Python versions

### `tests/smoke/windows/run_windows_tests.ps1`
PowerShell script for local testing:
- Supports both native and container testing
- Handles dependency installation
- Provides colored output and error handling

## Troubleshooting

### Common Issues

1. **Docker not running**
   ```
   Error: Docker is not installed or not running!
   ```
   Solution: Start Docker Desktop and switch to Windows containers

2. **Python not found**
   ```
   Error: Python is not installed or not in PATH!
   ```
   Solution: Install Python from python.org and add to PATH

3. **Container build fails**
   - Ensure you're using Windows containers (not Linux)
   - Check Docker Desktop settings
   - Ensure sufficient disk space

4. **Import errors in tests**
   - Run `pip install -e .` from repository root
   - Ensure all dependencies are installed

### Environment Variables

The tests use these environment variables:
- `WEAVE_SMOKE_TEST=1` - Indicates smoke test mode
- `WEAVE_CACHE_DIR` - Temporary directory for Weave data
- `PYTHONUNBUFFERED=1` - Ensures real-time output

## Adding New Tests

To add new smoke tests:

1. Add test functions to `test_windows_smoke.py`
2. Follow the naming convention `test_<feature>_<aspect>()`
3. Use temporary directories for file operations
4. Clean up resources after tests
5. Test both success and failure cases

Example:
```python
def test_new_feature():
    """Test description."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ['WEAVE_CACHE_DIR'] = tmpdir
        weave.init("test-project")
        
        # Your test code here
        assert expected_condition
```

## Performance Considerations

- Smoke tests should be fast (< 1 minute total)
- Use small datasets and minimal iterations
- Avoid network calls unless testing connectivity
- Use threading instead of multiprocessing for concurrency tests

## Maintenance

- Update Windows base image versions periodically
- Test with new Python versions as they're released
- Monitor CI/CD logs for flaky tests
- Keep tests focused on core functionality only 