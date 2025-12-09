"""Debugger module for exposing local functions as a traceable service.

Architecture:
    1. Datastore (abstract interface with Local and Weave implementations)
    2. Debugger (core business logic)
    3. DebuggerServer (FastAPI HTTP layer)
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import weave
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.op import Op, is_op, op


# =============================================================================
# Data Models
# =============================================================================


class Span(BaseModel):
    """Represents a single execution span of a callable."""

    name: str
    start_time_unix_nano: float
    end_time_unix_nano: float
    inputs: dict[str, Any]
    output: Any
    error: str | None = None
    weave_call_ref: str | None = None


# =============================================================================
# Datastore Interface and Implementations
# =============================================================================


class Datastore(ABC):
    """Abstract interface for storing and retrieving call spans."""

    @abstractmethod
    def add_span(self, callable_name: str, span: Span) -> None:
        """Store a span for a callable.

        Args:
            callable_name: The name of the callable.
            span: The span to store.
        """
        pass

    @abstractmethod
    def get_spans(self, callable_name: str, op: Op | None = None) -> list[Span]:
        """Retrieve all spans for a callable.

        Args:
            callable_name: The name of the callable.
            op: Optional op reference for implementations that need it.

        Returns:
            List of spans for the callable.
        """
        pass

    @abstractmethod
    def clear_spans(self, callable_name: str) -> None:
        """Clear all spans for a callable.

        Args:
            callable_name: The name of the callable.
        """
        pass


class LocalDatastore(Datastore):
    """In-memory datastore implementation.

    Stores spans in a local dictionary. Useful for testing or when
    weave persistence is not needed.
    """

    def __init__(self) -> None:
        self._spans: dict[str, list[Span]] = defaultdict(list)

    def add_span(self, callable_name: str, span: Span) -> None:
        """Store a span in memory."""
        self._spans[callable_name].append(span)

    def get_spans(self, callable_name: str, op: Op | None = None) -> list[Span]:
        """Retrieve spans from memory."""
        return self._spans[callable_name]

    def clear_spans(self, callable_name: str) -> None:
        """Clear spans from memory."""
        self._spans[callable_name] = []


class WeaveDatastore(Datastore):
    """Weave-backed datastore implementation.

    Uses Weave's trace server to store and retrieve call spans.
    Spans are automatically persisted when ops are called with weave tracing.
    """

    def add_span(self, callable_name: str, span: Span) -> None:
        """No-op: Weave automatically stores spans when ops are called."""
        # Spans are automatically stored by weave when using op.call()
        pass

    def get_spans(self, callable_name: str, op: Op | None = None) -> list[Span]:
        """Query Weave for call history of an op.

        Args:
            callable_name: The name of the callable.
            op: The op to query calls for (required for WeaveDatastore).

        Returns:
            List of spans from Weave's call history.
        """
        if op is None:
            return []

        spans = []
        try:
            # Query weave for calls to this op
            for call in op.calls():
                span = Span(
                    name=callable_name,
                    start_time_unix_nano=call.started_at.timestamp() if call.started_at else 0,
                    end_time_unix_nano=call.ended_at.timestamp() if call.ended_at else 0,
                    inputs=_safe_serialize_dict(call.inputs),
                    output=_safe_serialize_value(call.output),
                    error=call.exception,
                    weave_call_ref=call.ref.uri() if call.id else None,
                )
                spans.append(span)
        except Exception:
            # If querying fails, return empty list
            pass

        return spans

    def clear_spans(self, callable_name: str) -> None:
        """No-op: Cannot clear spans from Weave (they are immutable)."""
        # Weave calls are immutable - cannot be deleted via this interface
        pass


# =============================================================================
# Debugger (Core Business Logic)
# =============================================================================


class Debugger:
    """Core debugger that manages callables and their execution.

    The Debugger requires weave to be initialized. All callables are
    automatically converted to weave ops and published for traceability.

    Args:
        datastore: Optional datastore implementation. Defaults to WeaveDatastore.

    Raises:
        RuntimeError: If weave is not initialized when creating the Debugger.
    """

    def __init__(self, datastore: Datastore | None = None) -> None:
        # Require weave to be initialized
        self._client = require_weave_client()

        # Use WeaveDatastore by default
        self._datastore = datastore or WeaveDatastore()

        # Map of callable names to their ops
        self._callables: dict[str, Op] = {}

    @property
    def callables(self) -> dict[str, Op]:
        """Get the registered callables."""
        return self._callables

    def add_callable(
        self, callable: Callable[..., Any] | Op, *, name: str | None = None
    ) -> None:
        """Add a callable to be exposed by the debugger.

        The callable will be:
        1. Converted to a weave op (if not already)
        2. Published to weave for persistence

        Args:
            callable: The function or Op to add.
            name: Optional custom name. If not provided, uses the function's __name__.

        Raises:
            ValueError: If a callable with the same name already exists.
        """
        if name is None:
            name = _derive_callable_name(callable)

        if name in self._callables:
            raise ValueError(f"Callable with name {name} already exists")

        # Convert to op if not already
        callable_op: Op
        if not is_op(callable):
            callable_op = op(callable, name=name)
        else:
            callable_op = callable

        # Publish the op to weave
        weave.publish(callable_op, name=name)

        self._callables[name] = callable_op

    def list_callables(self) -> list[str]:
        """List all registered callable names."""
        return list(self._callables.keys())

    def invoke_callable(self, callable_name: str, inputs: dict[str, Any]) -> Any:
        """Invoke a registered callable with the given inputs.

        Args:
            callable_name: The name of the callable to invoke.
            inputs: Dictionary of input arguments.

        Returns:
            The result of calling the callable.

        Raises:
            KeyError: If the callable is not found.
        """
        if callable_name not in self._callables:
            raise KeyError(f"Callable '{callable_name}' not found")

        callable = self._callables[callable_name]

        # Use op.call() to get both result and call object
        # Note: op.call() never raises - errors are captured in the Call object
        output, call = callable.call(**inputs)

        # Check if the call had an exception
        if call.exception is not None:
            raise Exception(call.exception)

        return output

    def get_json_schema(self, callable_name: str) -> dict[str, Any]:
        """Get the JSON schema for a callable's inputs.

        Args:
            callable_name: The name of the registered callable.

        Returns:
            A JSON schema object describing the callable's input parameters.

        Raises:
            KeyError: If the callable is not found.
        """
        if callable_name not in self._callables:
            raise KeyError(f"Callable '{callable_name}' not found")

        # All callables are guaranteed to be ops (converted on add_callable)
        return self._callables[callable_name].get_input_json_schema()

    def get_calls(self, callable_name: str) -> list[Span]:
        """Get all calls (spans) for a given callable.

        Args:
            callable_name: The name of the callable.

        Returns:
            List of spans representing call history.

        Raises:
            KeyError: If the callable is not found.
        """
        if callable_name not in self._callables:
            raise KeyError(f"Callable '{callable_name}' not found")

        op = self._callables[callable_name]
        return self._datastore.get_spans(callable_name, op)

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
        GET  /callables                             - List all registered callables
        POST /callables/{callable_name}             - Invoke a callable
        GET  /callables/{callable_name}/json_schema - Get input JSON schema
        GET  /callables/{callable_name}/calls       - Get call history (spans)
        GET  /openapi.json                          - OpenAPI spec (provided by FastAPI)

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
        async def list_callables() -> list[str]:
            return self._debugger.list_callables()

        @app.post("/callables/{callable_name}")
        async def invoke_callable(
            callable_name: str, inputs: dict[str, Any]
        ) -> Any:
            try:
                return self._debugger.invoke_callable(callable_name, inputs)
            except KeyError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @app.get("/callables/{callable_name}/json_schema")
        async def get_json_schema(callable_name: str) -> dict[str, Any]:
            try:
                return self._debugger.get_json_schema(callable_name)
            except KeyError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @app.get("/callables/{callable_name}/calls")
        async def get_calls(callable_name: str) -> list[Span]:
            try:
                return self._debugger.get_calls(callable_name)
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


def _safe_serialize_value(value: Any) -> Any:
    """Safely serialize a value for storage in a span.

    Args:
        value: The value to serialize.

    Returns:
        A JSON-serializable representation of the value.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, (list, tuple)):
        return [_safe_serialize_value(item) for item in value]
    elif isinstance(value, dict):
        return {str(k): _safe_serialize_value(v) for k, v in value.items()}
    else:
        try:
            return str(value)
        except Exception:
            return "<<SERIALIZATION_ERROR>>"


def _safe_serialize_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Safely serialize a dictionary for storage in a span."""
    return {k: _safe_serialize_value(v) for k, v in d.items()}
