"""Debugger module for exposing local functions as a traceable service.

Architecture:
    1. Debugger (core business logic)
    2. DebuggerServer (FastAPI HTTP layer)

Ops are identified by their stable weave ref URI after publishing.
Schema and call history can be queried from the weave trace server using the ref.
"""

import threading
from collections.abc import Callable
from typing import Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import weave
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.op import Op, is_op, op


# =============================================================================
# Data Models
# =============================================================================


class CallRequest(BaseModel):
    """Request body for calling an op."""

    ref: str
    inputs: dict[str, Any]


class AsyncCallResponse(BaseModel):
    """Response for async call containing the call ID."""

    call_id: str


# =============================================================================
# Debugger (Core Business Logic)
# =============================================================================


class Debugger:
    """Core debugger that manages ops and their execution.

    The Debugger requires weave to be initialized. All functions are
    automatically converted to weave ops and published for traceability.
    Ops are identified by their stable weave ref URI.

    Schema and call history are available via the weave trace server using the ref.

    Raises:
        RuntimeError: If weave is not initialized when creating the Debugger.
    """

    def __init__(self) -> None:
        # Require weave to be initialized
        self._client = require_weave_client()

        # Map of ref URI to op
        self._ops: dict[str, Op] = {}

    @property
    def ops(self) -> dict[str, Op]:
        """Get the registered ops (keyed by ref URI)."""
        return self._ops

    def add_op(self, callable: Callable[..., Any] | Op) -> str:
        """Add an op to be exposed by the debugger.

        The callable will be:
        1. Converted to a weave op (if not already)
        2. Published to weave for persistence

        Args:
            callable: The function or Op to add.

        Returns:
            The ref URI of the published op.

        Raises:
            ValueError: If an op with the same ref already exists.
        """
        # Convert to op if not already
        callable_op: Op
        if not is_op(callable):
            callable_op = op(callable)
        else:
            callable_op = callable

        # Publish the op to weave - this sets op.ref
        weave.publish(callable_op)

        # Get the ref URI after publishing
        if callable_op.ref is None:
            raise RuntimeError("Op ref not set after publish")

        ref_uri = callable_op.ref.uri()

        if ref_uri in self._ops:
            raise ValueError(f"Op with ref {ref_uri} already exists")

        self._ops[ref_uri] = callable_op

        return ref_uri

    def list_ops(self) -> list[str]:
        """List all registered op refs."""
        return list(self._ops.keys())

    def call_op(self, ref_uri: str, inputs: dict[str, Any]) -> Any:
        """Call a registered op with the given inputs (synchronous).

        Args:
            ref_uri: The ref URI of the op to call.
            inputs: Dictionary of input arguments.

        Returns:
            The result of calling the op.

        Raises:
            KeyError: If the op is not found.
        """
        if ref_uri not in self._ops:
            raise KeyError(f"Op with ref '{ref_uri}' not found")

        op_to_call = self._ops[ref_uri]

        # Use op.call() to get both result and call object
        # Note: op.call() never raises - errors are captured in the Call object
        output, call = op_to_call.call(**inputs)

        # Check if the call had an exception
        if call.exception is not None:
            raise Exception(call.exception)

        return output

    def call_op_async(self, ref_uri: str, inputs: dict[str, Any]) -> str:
        """Start an async call and return the call ID immediately.

        The call execution continues in a background thread. Use the call ID
        to query the call status and result from the weave trace server.

        Args:
            ref_uri: The ref URI of the op to call.
            inputs: Dictionary of input arguments.

        Returns:
            The call ID (can be used to query status/result from weave).

        Raises:
            KeyError: If the op is not found.
        """
        if ref_uri not in self._ops:
            raise KeyError(f"Op with ref '{ref_uri}' not found")

        op_to_call = self._ops[ref_uri]

        # Create the call record first (this gives us the call ID)
        call = self._client.create_call(op_to_call, inputs)

        # Execute the op in a background thread
        def execute_in_background() -> None:
            try:
                output = op_to_call.resolve_fn(**inputs)
                self._client.finish_call(call, output)
            except Exception as e:
                self._client.finish_call(call, None, exception=e)

        thread = threading.Thread(target=execute_in_background, daemon=True)
        thread.start()

        return call.id

    def start(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start the debugger HTTP server.

        Args:
            host: Host address to bind to. Defaults to "0.0.0.0".
            port: Port to listen on. Defaults to 8000.
        """
        server = DebuggerServer(self)
        server.run(host=host, port=port)


# =============================================================================
# DebuggerServer (FastAPI HTTP Layer)
# =============================================================================


class DebuggerServer:
    """FastAPI HTTP server for the debugger.

    Exposes the debugger functionality via REST endpoints:
        GET  /ops            - List all registered op refs
        POST /call           - Call an op synchronously (JSON body: {"ref": "...", "inputs": {...}})
        POST /call_async     - Call an op asynchronously, returns call ID immediately
        GET  /openapi.json   - OpenAPI spec (provided by FastAPI)

    Ops are identified by their weave ref URI.
    Schema and call history can be queried from the weave trace server using the ref.

    Args:
        debugger: The Debugger instance to expose.
    """

    def __init__(self, debugger: Debugger) -> None:
        self._debugger = debugger
        self._app = self._create_app()

    @property
    def app(self) -> FastAPI:
        """Get the FastAPI application."""
        return self._app

    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(title="Weave Debugger")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "https://wandb.ai",
                "https://beta.wandb.ai",
                "https://qa.wandb.ai",
                "https://zoo-qa.wandb.dev",
                "https://app.wandb.test",
                "http://localhost",
                "http://localhost:3000",
                "http://localhost:9000",
                "https://wandb.github.io",
                "https://weave_scorer.wandb.test",
            ],
            allow_origin_regex=r"https://.+\.wandb\.dev",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Register endpoints
        @app.get("/ops")
        async def list_ops() -> list[str]:
            return self._debugger.list_ops()

        @app.post("/call")
        async def call_op(request: CallRequest) -> Any:
            try:
                return self._debugger.call_op(request.ref, request.inputs)
            except KeyError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @app.post("/call_async")
        async def call_op_async(request: CallRequest) -> AsyncCallResponse:
            try:
                call_id = self._debugger.call_op_async(request.ref, request.inputs)
                return AsyncCallResponse(call_id=call_id)
            except KeyError as e:
                raise HTTPException(status_code=404, detail=str(e))

        return app

    def run(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Run the server.

        Args:
            host: Host address to bind to.
            port: Port to listen on.
        """
        uvicorn.run(self._app, host=host, port=port)
