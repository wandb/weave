"""Deployable debugger that works both locally and on Modal.

This module provides a unified interface for running the debugger either:
1. Locally: `python your_debugger.py`
2. On Modal: `modal deploy your_debugger.py`

Usage:
    ```python
    import weave
    from weave.trace.debugger import create_debugger

    @weave.op
    def my_op(x: int) -> int:
        return x * 2

    debugger, app = create_debugger(
        ops=[my_op],
        weave_project="my-project",
        app_name="my-debugger",
    )

    if __name__ == "__main__":
        debugger.serve()
    ```

Then run locally with `python your_debugger.py` or deploy with `modal deploy your_debugger.py`.
"""

from __future__ import annotations

import inspect
import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import modal


def create_debugger(
    ops: list[Callable[..., Any]],
    weave_project: str,
    app_name: str = "weave-debugger",
    *,
    host: str = "0.0.0.0",
    port: int = 8000,
    modal_image: modal.Image | None = None,
    modal_secrets: list[str] | None = None,
    modal_gpu: str | None = None,
) -> tuple["DeployableDebugger", "modal.App"]:
    """Create a debugger that can run locally or be deployed to Modal.

    Args:
        ops: List of functions/ops to expose via the debugger.
        weave_project: The weave project name for tracing.
        app_name: Name for the Modal app (used in deployment).
        host: Host to bind to for local server. Defaults to "0.0.0.0".
        port: Port for local server. Defaults to 8000.
        modal_image: Optional custom Modal image. If not provided, uses a default
            image with weave, fastapi, and common dependencies.
        modal_secrets: List of Modal secret names to attach (e.g., ["wandb-api-key"]).
        modal_gpu: Optional GPU type for Modal (e.g., "T4", "A10G").

    Returns:
        A tuple of (DeployableDebugger, modal.App). The debugger can be used to
        run locally via `debugger.serve()`. The app is for Modal deployment.

    Note:
        Local source files where ops are defined are automatically added to
        the Modal image so they're available during deployment.

    Examples:
        Basic usage:

        ```python
        import weave
        from weave.trace.debugger import create_debugger

        @weave.op
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        debugger, app = create_debugger(
            ops=[greet],
            weave_project="my-project",
        )

        if __name__ == "__main__":
            debugger.serve()
        ```

        With Modal secrets and GPU:

        ```python
        debugger, app = create_debugger(
            ops=[my_llm_op],
            weave_project="llm-project",
            modal_secrets=["wandb-api-key", "openai-secret"],
            modal_gpu="T4",
        )
        ```
    """
    deployable = DeployableDebugger(
        ops=ops,
        weave_project=weave_project,
        app_name=app_name,
        host=host,
        port=port,
        modal_image=modal_image,
        modal_secrets=modal_secrets,
        modal_gpu=modal_gpu,
    )
    return deployable, deployable.modal_app


class DeployableDebugger:
    """A debugger that can be deployed locally or to Modal.

    This class wraps the core Debugger and DebuggerServer to provide a unified
    interface that works for both local development and Modal deployment.

    The same code works for both:
    - Local: `python your_file.py` calls `serve()`
    - Modal: `modal deploy your_file.py` uses `modal_app`
    """

    def __init__(
        self,
        ops: list[Callable[..., Any]],
        weave_project: str,
        app_name: str = "weave-debugger",
        *,
        host: str = "0.0.0.0",
        port: int = 8000,
        modal_image: modal.Image | None = None,
        modal_secrets: list[str] | None = None,
        modal_gpu: str | None = None,
    ) -> None:
        self._ops = ops
        self._weave_project = weave_project
        self._app_name = app_name
        self._host = host
        self._port = port
        self._modal_image = modal_image
        self._modal_secrets = modal_secrets or []
        self._modal_gpu = modal_gpu

        # Create Modal app lazily
        self._modal_app: modal.App | None = None

    @property
    def modal_app(self) -> "modal.App":
        """Get or create the Modal app for deployment."""
        if self._modal_app is None:
            self._modal_app = self._create_modal_app()
        return self._modal_app

    def _create_modal_app(self) -> "modal.App":
        """Create the Modal app with ASGI endpoint."""
        try:
            import modal
        except ImportError:
            raise ImportError(
                "Modal is required for deployment. Install it with: pip install modal"
            )

        app = modal.App(self._app_name)

        # Build the image
        if self._modal_image is not None:
            image = self._modal_image
        else:
            # Install weave from the hackweek branch with debugger features
            # Need git for pip install from GitHub
            weave_git_url = (
                "git+https://github.com/wandb/weave.git"
                "@tim/hackweek_2025_debugger_weave"
            )
            image = (
                modal.Image.debian_slim(python_version="3.12")
                .apt_install("git")
                .pip_install(
                    weave_git_url,
                    "fastapi",
                    "uvicorn",
                    "pydantic",
                    "openai",  # Common dependency for LLM apps
                )
            )

        # Add local source files to the image (Modal 1.0+ API)
        # This makes the modules importable on Modal
        image = self._add_local_files_to_image(image)

        # Collect secrets
        secrets = [modal.Secret.from_name(s) for s in self._modal_secrets]

        # Build function kwargs
        # serialized=True allows Modal to serialize functions with closures
        func_kwargs: dict[str, Any] = {
            "image": image,
            "serialized": True,
        }
        if secrets:
            func_kwargs["secrets"] = secrets
        if self._modal_gpu:
            func_kwargs["gpu"] = self._modal_gpu

        # We need to capture these for the closure
        ops = self._ops
        weave_project = self._weave_project

        @app.function(**func_kwargs)
        @modal.asgi_app()
        def serve_debugger():
            """ASGI app for Modal deployment."""
            import weave
            from weave.trace.debugger.debug import Debugger, DebuggerServer

            weave.init(weave_project)
            debugger = Debugger()
            for op_fn in ops:
                debugger.add_op(op_fn)

            return DebuggerServer(debugger).app

        return app

    def _add_local_files_to_image(self, image: Any) -> Any:
        """Add local source files to the Modal image.

        Detects the source files where ops are defined and adds them to the
        image so they're available on Modal. Uses Modal 1.0+ API.

        Args:
            image: The Modal image to add files to.

        Returns:
            The image with local files added.
        """
        seen_files: set[str] = set()

        for op_fn in self._ops:
            # Get the source file for this op
            try:
                # Handle weave ops - get the underlying function
                if hasattr(op_fn, "resolve_fn"):
                    source_fn = op_fn.resolve_fn
                else:
                    source_fn = op_fn

                source_file = inspect.getfile(source_fn)
                source_file = os.path.abspath(source_file)

                if source_file not in seen_files:
                    seen_files.add(source_file)

                    # Get the module name from the file
                    module_name = Path(source_file).stem

                    # Add the file to the image in /root (Modal 1.0+ API)
                    # This makes the module importable
                    remote_path = f"/root/{module_name}.py"
                    image = image.add_local_file(source_file, remote_path)
            except (TypeError, OSError):
                # Can't get source file (e.g., built-in function)
                pass

        return image

    def serve(self, host: str | None = None, port: int | None = None) -> None:
        """Start the debugger server locally.

        Args:
            host: Host to bind to. Defaults to the value set in constructor.
            port: Port to listen on. Defaults to the value set in constructor.
        """
        import weave
        from weave.trace.debugger.debug import Debugger, DebuggerServer

        weave.init(self._weave_project)
        debugger = Debugger()
        for op_fn in self._ops:
            debugger.add_op(op_fn)

        server = DebuggerServer(debugger)
        server.run(
            host=host or self._host,
            port=port or self._port,
        )

    def get_local_debugger(self) -> "Debugger":
        """Get a local Debugger instance (useful for testing).

        Note: This initializes weave and creates a new Debugger.

        Returns:
            A configured Debugger instance.
        """
        import weave
        from weave.trace.debugger.debug import Debugger

        weave.init(self._weave_project)
        debugger = Debugger()
        for op_fn in self._ops:
            debugger.add_op(op_fn)
        return debugger

