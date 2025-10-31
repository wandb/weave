"""Utility for directly logging calls to Weave.

This module provides a utility function to directly log a call to Weave.
This form factor affords a logging pattern that feels more like logging
to a table, where you can directly log an operation with its inputs and
outputs without using the decorator pattern.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from weave.trace.call import Call
from weave.trace.context.weave_client_context import require_weave_client


def log_call(
    op: str,
    inputs: dict[str, Any],
    output: Any,
    *,
    # Additional arguments for call creation
    parent: Call | None = None,
    attributes: dict[str, Any] | None = None,
    display_name: str | Callable[[Call], str] | None = None,
    use_stack: bool = True,
    # Additional arguments for call finishing
    exception: BaseException | None = None,
) -> Call:
    """Log a call directly to Weave without using the decorator pattern.

    This function provides an imperative API for logging operations to Weave,
    useful when you want to log calls after they've already been executed or
    when the decorator pattern isn't suitable for your use case.

    Args:
        op (str): The operation name to log. This will be used as the op_name
            for the call. Anonymous operations (strings not referring to published
            ops) are supported.
        inputs (dict[str, Any]): A dictionary of input parameters for the operation.
        output (Any): The output/result of the operation.
        parent (Call | None): Optional parent call to nest this call under.
            If not provided, the call will be a root-level call (or nested under
            the current call context if one exists). Defaults to None.
        attributes (dict[str, Any] | None): Optional metadata to attach to the call.
            These are frozen once the call is created. Defaults to None.
        display_name (str | Callable[[Call], str] | None): Optional display name
            for the call in the UI. Can be a string or a callable that takes the
            call and returns a string. Defaults to None.
        use_stack (bool): Whether to push the call onto the runtime stack. When True,
            the call will be available in the call context and can be accessed via
            weave.require_current_call(). When False, the call is logged but not
            added to the call stack. Defaults to True.
        exception (BaseException | None): Optional exception to log if the operation
            failed. Defaults to None.

    Returns:
        Call: The created and finished Call object with full trace information.

    Examples:
        Basic usage:
        >>> import weave
        >>> weave.init('my-project')
        >>> call = weave.log_call(
        ...     op="my_function",
        ...     inputs={"x": 5, "y": 10},
        ...     output=15
        ... )

        Logging with attributes and display name:
        >>> call = weave.log_call(
        ...     op="process_data",
        ...     inputs={"data": [1, 2, 3]},
        ...     output={"mean": 2.0},
        ...     attributes={"version": "1.0", "env": "prod"},
        ...     display_name="Data Processing"
        ... )

        Logging a failed operation:
        >>> try:
        ...     result = risky_operation()
        ... except Exception as e:
        ...     call = weave.log_call(
        ...         op="risky_operation",
        ...         inputs={},
        ...         output=None,
        ...         exception=e
        ...     )

        Nesting calls:
        >>> parent_call = weave.log_call("parent", {"input": 1}, 2)
        >>> child_call = weave.log_call(
        ...     "child",
        ...     {"input": 2},
        ...     4,
        ...     parent=parent_call
        ... )

        Logging without adding to call stack:
        >>> call = weave.log_call(
        ...     op="background_task",
        ...     inputs={"task_id": 123},
        ...     output="completed",
        ...     use_stack=False  # Don't push to call stack
        ... )
    """
    # Get the current Weave client (will raise if weave.init() hasn't been called)
    client = require_weave_client()

    # Create the call with the provided parameters
    call = client.create_call(
        op=op,
        inputs=inputs,
        parent=parent,
        attributes=attributes,
        display_name=display_name,
        use_stack=use_stack,
    )

    # Immediately finish the call with the output or exception
    client.finish_call(call, output=output, exception=exception)

    return call
