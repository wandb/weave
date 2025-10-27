from __future__ import annotations

from typing import Any

from weave.trace.call import Call
from weave.trace.context.weave_client_context import require_weave_client

"""
This module provides a utility function to directly log a call to Weave.

This form factor affords a logging pattern that feels more like logging
to a table.
"""


def log_call(
    op: str,
    inputs: dict[str, Any],
    output: Any,
    # *,
    # Additional arguments for call creation
    # parent: Call | None = None,
    # attributes: dict[str, Any] | None = None,
    # display_name: str | Callable[[Call], str] | None = None,
    # Additional arguments for call finishing
    # exception: BaseException | None = None,
) -> Call:
    """Log a call to Weave."""
    client = require_weave_client()
    call = client.create_call(op, inputs)
    client.finish_call(call, output)
    return call
