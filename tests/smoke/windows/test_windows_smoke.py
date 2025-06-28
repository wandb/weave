"""
Basic smoke tests for Weave on Windows containers.
These tests validate core functionality works correctly on Windows.
"""

import os
import platform
import tempfile
import threading
import time

import pytest

import weave


def test_windows_environment():
    """Verify we're running on Windows."""
    assert platform.system() == "Windows", f"Expected Windows, got {platform.system()}"


def test_weave_import():
    """Test that weave can be imported successfully."""
    assert weave is not None
    assert hasattr(weave, "__version__")


def test_weave_init():
    """Test that weave can be initialized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set a temporary directory for weave data
        os.environ["WEAVE_CACHE_DIR"] = tmpdir

        # Initialize weave
        weave.init("windows-smoke-test")

        # Verify initialization created necessary directories
        assert os.path.exists(tmpdir)


def test_basic_op():
    """Test basic weave op functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["WEAVE_CACHE_DIR"] = tmpdir
        weave.init("windows-smoke-test-ops")

        @weave.op()
        def add_numbers(a: int, b: int) -> int:
            return a + b

        # Test the operation
        result = add_numbers(5, 3)
        assert result == 8

        # Test with different inputs
        result2 = add_numbers(10, -5)
        assert result2 == 5


def test_nested_ops():
    """Test nested weave operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["WEAVE_CACHE_DIR"] = tmpdir
        weave.init("windows-smoke-test-nested")

        @weave.op()
        def multiply(x: int, y: int) -> int:
            return x * y

        @weave.op()
        def calculate(a: int, b: int, c: int) -> int:
            temp = multiply(a, b)
            return multiply(temp, c)

        result = calculate(2, 3, 4)
        assert result == 24


def test_op_with_exceptions():
    """Test that ops handle exceptions properly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["WEAVE_CACHE_DIR"] = tmpdir
        weave.init("windows-smoke-test-exceptions")

        @weave.op()
        def divide(a: float, b: float) -> float:
            if b == 0:
                raise ValueError("Division by zero")
            return a / b

        # Test normal operation
        result = divide(10.0, 2.0)
        assert result == 5.0

        # Test exception handling
        with pytest.raises(ValueError):
            divide(10.0, 0.0)


def test_op_with_complex_types():
    """Test ops with complex data types."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["WEAVE_CACHE_DIR"] = tmpdir
        weave.init("windows-smoke-test-complex")

        @weave.op()
        def process_data(data: dict) -> dict:
            return {
                "sum": sum(data.get("numbers", [])),
                "count": len(data.get("numbers", [])),
                "name": data.get("name", "unknown").upper(),
            }

        test_data = {"numbers": [1, 2, 3, 4, 5], "name": "test"}

        result = process_data(test_data)
        assert result["sum"] == 15
        assert result["count"] == 5
        assert result["name"] == "TEST"


def test_file_paths_windows():
    """Test that file paths work correctly on Windows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["WEAVE_CACHE_DIR"] = tmpdir

        # Create a test file with Windows path
        test_file = os.path.join(tmpdir, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("Hello from Windows!")

        assert os.path.exists(test_file)
        assert "\\" in test_file  # Windows uses backslashes

        # Read the file back
        with open(test_file) as f:
            content = f.read()
        assert content == "Hello from Windows!"


def test_unicode_support():
    """Test Unicode support on Windows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["WEAVE_CACHE_DIR"] = tmpdir
        weave.init("windows-smoke-test-unicode")

        @weave.op()
        def process_unicode(text: str) -> str:
            return f"Processed: {text}"

        # Test with various Unicode characters
        test_strings = [
            "Hello World",  # ASCII
            "Hëllö Wörld",  # Latin with diacritics
            "你好世界",  # Chinese
            "🚀🌟✨",  # Emojis
            "Здравствуй мир",  # Cyrillic
        ]

        for test_str in test_strings:
            result = process_unicode(test_str)
            assert test_str in result


def test_concurrent_ops():
    """Test basic concurrent operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["WEAVE_CACHE_DIR"] = tmpdir
        weave.init("windows-smoke-test-concurrent")

        results = []

        @weave.op()
        def slow_operation(value: int) -> int:
            time.sleep(0.1)  # Simulate some work
            return value * 2

        def worker(value):
            result = slow_operation(value)
            results.append(result)

        # Create multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Check results
        assert len(results) == 5
        assert sorted(results) == [0, 2, 4, 6, 8]
