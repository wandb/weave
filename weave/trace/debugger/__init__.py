"""Weave Debugger - Interactive debugging and deployment for weave ops.

This module provides tools for exposing weave ops as HTTP services that can
be run locally or deployed to Modal.

Basic Usage:
    ```python
    import weave
    from weave.trace.debugger import create_debugger

    @weave.op
    def my_op(x: int) -> int:
        return x * 2

    debugger, app = create_debugger(
        ops=[my_op],
        weave_project="my-project",
    )

    # Run locally: python your_file.py
    # Deploy to Modal: modal deploy your_file.py
    if __name__ == "__main__":
        debugger.serve()
    ```
"""

from weave.trace.debugger.debug import (
    Debugger,
    DebuggerServer,
)
from weave.trace.debugger.deployable import (
    DeployableDebugger,
    create_debugger,
)

__all__ = [
    "Debugger",
    "DebuggerServer",
    "DeployableDebugger",
    "create_debugger",
]

