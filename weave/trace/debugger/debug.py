"""Debugger module for exposing local functions as a traceable service.

Architecture:
    1. Debugger (core business logic)
    2. DebuggerServer (FastAPI HTTP layer)

Callables are identified by their stable weave ref URI after publishing.
"""

from collections.abc import Callable
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import weave
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.op import Op, is_op, op
from weave.trace_server.trace_server_interface import CallSchema


# =============================================================================
# Data Models
# =============================================================================


class CallableInfo(BaseModel):
    """Information about a registered callable."""

    ref: str
    name: str


# =============================================================================
# Debugger (Core Business Logic)
# =============================================================================


class Debugger:
    """Core debugger that manages callables and their execution.

    The Debugger requires weave to be initialized. All callables are
    automatically converted to weave ops and published for traceability.
    Callables are identified by their stable weave ref URI.

    Raises:
        RuntimeError: If weave is not initialized when creating the Debugger.
    """

    def __init__(self) -> None:
        # Require weave to be initialized
        self._client = require_weave_client()

        # Map of ref URI to op
        self._callables: dict[str, Op] = {}

        # Map of ref URI to human-readable name
        self._names: dict[str, str] = {}

    @property
    def callables(self) -> dict[str, Op]:
        """Get the registered callables (keyed by ref URI)."""
        return self._callables

    def add_callable(
        self, callable: Callable[..., Any] | Op, *, name: str | None = None
    ) -> str:
        """Add a callable to be exposed by the debugger.

        The callable will be:
        1. Converted to a weave op (if not already)
        2. Published to weave for persistence

        Args:
            callable: The function or Op to add.
            name: Optional custom name. If not provided, uses the function's __name__.

        Returns:
            The ref URI of the published callable.

        Raises:
            ValueError: If a callable with the same ref already exists.
        """
        if name is None:
            name = _derive_callable_name(callable)

        # Convert to op if not already
        callable_op: Op
        if not is_op(callable):
            callable_op = op(callable, name=name)
        else:
            callable_op = callable

        # Publish the op to weave - this sets op.ref
        weave.publish(callable_op, name=name)

        # Get the ref URI after publishing
        if callable_op.ref is None:
            raise RuntimeError("Op ref not set after publish")

        ref_uri = callable_op.ref.uri()

        if ref_uri in self._callables:
            raise ValueError(f"Callable with ref {ref_uri} already exists")

        self._callables[ref_uri] = callable_op
        self._names[ref_uri] = name

        return ref_uri

    def list_callables(self) -> list[CallableInfo]:
        """List all registered callables with their refs and names."""
        return [
            CallableInfo(ref=ref_uri, name=self._names[ref_uri])
            for ref_uri in self._callables.keys()
        ]

    def invoke_callable(self, ref_uri: str, inputs: dict[str, Any]) -> Any:
        """Invoke a registered callable with the given inputs.

        Args:
            ref_uri: The ref URI of the callable to invoke.
            inputs: Dictionary of input arguments.

        Returns:
            The result of calling the callable.

        Raises:
            KeyError: If the callable is not found.
        """
        if ref_uri not in self._callables:
            raise KeyError(f"Callable with ref '{ref_uri}' not found")

        callable = self._callables[ref_uri]

        # Use op.call() to get both result and call object
        # Note: op.call() never raises - errors are captured in the Call object
        output, call = callable.call(**inputs)

        # Check if the call had an exception
        if call.exception is not None:
            raise Exception(call.exception)

        return output

    def get_json_schema(self, ref_uri: str) -> dict[str, Any]:
        """Get the JSON schema for a callable's inputs.

        Args:
            ref_uri: The ref URI of the registered callable.

        Returns:
            A JSON schema object describing the callable's input parameters.

        Raises:
            KeyError: If the callable is not found.
        """
        if ref_uri not in self._callables:
            raise KeyError(f"Callable with ref '{ref_uri}' not found")

        # All callables are guaranteed to be ops (converted on add_callable)
        return self._callables[ref_uri].get_input_json_schema()

    def get_calls(self, ref_uri: str) -> list[CallSchema]:
        """Get all calls for a given callable.

        Args:
            ref_uri: The ref URI of the callable.

        Returns:
            List of CallSchema objects representing call history.

        Raises:
            KeyError: If the callable is not found.
        """
        if ref_uri not in self._callables:
            raise KeyError(f"Callable with ref '{ref_uri}' not found")

        callable_op = self._callables[ref_uri]
        return _get_calls_for_op(callable_op)

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
        GET  /callables                  - List all registered callables (refs and names)
        POST /invoke?ref={ref}           - Invoke a callable by ref
        GET  /schema?ref={ref}           - Get input JSON schema for a callable
        GET  /calls?ref={ref}            - Get call history (spans) for a callable
        GET  /openapi.json               - OpenAPI spec (provided by FastAPI)

    Callables are identified by their weave ref URI (passed as query parameter).

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
        @app.get("/callables")
        async def list_callables() -> list[CallableInfo]:
            return self._debugger.list_callables()

        @app.post("/invoke")
        async def invoke_callable(ref: str, inputs: dict[str, Any]) -> Any:
            try:
                return self._debugger.invoke_callable(ref, inputs)
            except KeyError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @app.get("/schema")
        async def get_json_schema(ref: str) -> dict[str, Any]:
            try:
                return self._debugger.get_json_schema(ref)
            except KeyError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @app.get("/calls")
        async def get_calls(ref: str) -> list[CallSchema]:
            try:
                return self._debugger.get_calls(ref)
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


# =============================================================================
# Helper Functions
# =============================================================================


def _derive_callable_name(callable: Callable[..., Any]) -> str:
    """Derive the name of a callable from its __name__ attribute."""
    return callable.__name__


def _get_calls_for_op(callable_op: Op) -> list[CallSchema]:
    """Query Weave for call history of an op.

    Args:
        callable_op: The op to query calls for.

    Returns:
        List of CallSchema objects from Weave's call history.
    """
    calls = []
    try:
        for call in callable_op.calls():
            # CallSchema requires id and project_id - skip if missing
            if call.id is None:
                continue

            call_schema = CallSchema(
                id=call.id,
                project_id=call.project_id,
                op_name=call.op_name,
                display_name=call.display_name,
                trace_id=call.trace_id,
                parent_id=call.parent_id,
                thread_id=call.thread_id,
                turn_id=call.turn_id,
                started_at=call.started_at,
                attributes=call.attributes or {},
                inputs=call.inputs,
                ended_at=call.ended_at,
                exception=call.exception,
                output=call.output,
                summary=call.summary,
                wb_run_id=call.wb_run_id,
                wb_run_step=call.wb_run_step,
                wb_run_step_end=call.wb_run_step_end,
                deleted_at=call.deleted_at,
            )
            calls.append(call_schema)
    except Exception:
        # If querying fails, return empty list
        pass

    return calls
