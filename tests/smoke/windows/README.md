# Weave Windows Smoke Tests

This directory (`tests/smoke/windows/`) contains Windows-specific smoke tests to validate that Weave works correctly on Windows containers.

## Overview

The smoke tests validate core Weave functionality on Windows:
- Basic Weave initialization and import
- Op decorators and function tracing  
- Nested operations
- Exception handling
- Complex data types
- Windows-specific file path handling
- Unicode support
- Basic concurrent operations

## CI/CD Integration

The Windows smoke tests run automatically in GitHub Actions via the `.github/workflows/windows-smoke-test.yaml` workflow. The tests run in a Windows Server Core container with Python 3.11.

### Test Execution

The workflow:
1. Builds a Windows container using `tests/smoke/windows/Dockerfile.windows`
2. Runs the smoke tests inside the container
3. Reports results back to the PR/commit

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

### `Dockerfile.windows`
Windows container definition:
- Based on Windows Server Core LTSC 2022
- Installs Python 3.11
- Installs Weave and dependencies
- Runs smoke tests by default

## Environment Variables

The tests use these environment variables:
- `WEAVE_CACHE_DIR` - Temporary directory for Weave data (set by tests)
- `PYTHONUNBUFFERED=1` - Ensures real-time output in container logs

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