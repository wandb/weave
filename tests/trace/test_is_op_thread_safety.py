"""Test that is_op() is thread-safe.

This test verifies that the is_op() function can be called safely from multiple
threads simultaneously without causing segmentation faults or race conditions.
"""

import threading
from typing import Any

import weave
from weave.trace.op import is_op


def test_is_op_thread_safety(client: Any) -> None:
    """Test that is_op() can be called safely from multiple threads."""

    @weave.op()
    def my_op(x: int) -> int:
        return x + 1

    # Also test with a non-op function
    def regular_func(x: int) -> int:
        return x + 1

    num_threads = 50
    calls_per_thread = 100
    errors: list[Exception] = []

    def check_is_op() -> None:
        try:
            for _ in range(calls_per_thread):
                assert is_op(my_op) is True
                assert is_op(regular_func) is False
                # Also test with various other types
                assert is_op(42) is False
                assert is_op("string") is False
                assert is_op(None) is False
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=check_is_op) for _ in range(num_threads)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Check that no errors occurred
    if errors:
        raise AssertionError(f"Errors occurred in threads: {errors}")


def test_is_op_with_serialization_thread_safety(client: Any) -> None:
    """Test is_op() in a scenario similar to where the segfault occurred.

    This test creates ops with postprocessing functions and publishes them,
    which triggers serialization in background threads.
    """

    def postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
        # Postprocessing function
        return inputs

    def postprocess_output(output: Any) -> Any:
        # Postprocessing function
        return output

    errors: list[Exception] = []

    def create_and_publish_op(index: int) -> None:
        try:
            # Create an op with postprocessing functions
            @weave.op(
                name=f"test_op_{index}",
                postprocess_inputs=postprocess_inputs,
                postprocess_output=postprocess_output,
            )
            def my_func(x: int) -> int:
                return x + 1

            # Call the op (this triggers serialization)
            result = my_func(index)
            assert result == index + 1

            # Publish the op (this also triggers serialization)
            ref = weave.publish(my_func)
            assert ref is not None

        except Exception as e:
            errors.append(e)

    num_threads = 20
    threads = [
        threading.Thread(target=create_and_publish_op, args=(i,))
        for i in range(num_threads)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Check that no errors occurred
    if errors:
        raise AssertionError(f"Errors occurred in threads: {errors}")
