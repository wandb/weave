"""Debugger module for exposing local functions as a traceable service."""

import inspect
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, TypeAdapter

from weave.trace.context.weave_client_context import get_weave_client
from weave.trace.op import is_op, op


class Span(BaseModel):
    """Represents a single execution span of a callable."""

    name: str
    start_time_unix_nano: float
    end_time_unix_nano: float
    inputs: dict[str, Any]
    output: Any
    error: str | None = None
    weave_call_ref: str | None = None


class Debugger:
    """Exposes local callables as a traceable HTTP service.

    Endpoints:
        GET  /callables                             - List all registered callables
        POST /callables/{callable_name}             - Invoke a callable
        GET  /callables/{callable_name}/json_schema - Get input JSON schema
        GET  /callables/{callable_name}/calls       - Get call history (spans)
        GET  /openapi.json                          - OpenAPI spec (provided by FastAPI)
    """

    callables: dict[str, Callable[..., Any]]
    spans: dict[str, list[Span]]
    app: FastAPI

    def __init__(self) -> None:
        self.callables = {}
        self.spans = defaultdict(list)

    def add_callable(
        self, callable: Callable[..., Any], *, name: str | None = None
    ) -> None:
        """Add a callable to be exposed by the debugger.

        If the callable is not already a weave op, it will be automatically
        wrapped with @weave.op to ensure all invocations are traced.

        Args:
            callable: The function to add.
            name: Optional custom name. If not provided, uses the function's __name__.

        Raises:
            ValueError: If a callable with the same name already exists.
        """
        if name is None:
            name = derive_callable_name(callable)

        if name in self.callables:
            raise ValueError(f"Callable with name {name} already exists")

        # Automatically wrap non-ops with @weave.op to ensure all calls are traced
        if not is_op(callable):
            callable = op(callable, name=name)

        self.callables[name] = callable

    async def list_callables(self) -> list[str]:
        """List all registered callable names."""
        return list(self.callables.keys())

    async def invoke_callable(
        self, callable_name: str, inputs: dict[str, Any]
    ) -> Any:
        """Invoke a registered callable with the given inputs.

        All callables are automatically wrapped as weave ops, so if weave is
        initialized, every call will be traced and have a weave_call_ref.

        Args:
            callable_name: The name of the callable to invoke.
            inputs: Dictionary of input arguments.

        Returns:
            The result of calling the callable.

        Raises:
            HTTPException: If the callable is not found.
        """
        if callable_name not in self.callables:
            raise HTTPException(
                status_code=404, detail=f"Callable '{callable_name}' not found"
            )

        callable = self.callables[callable_name]

        # Check if weave is initialized for tracing
        weave_client = get_weave_client()

        # Create span
        span = Span(
            name=callable_name,
            start_time_unix_nano=time.time(),
            end_time_unix_nano=time.time(),
            inputs={k: safe_serialize_input_value(v) for k, v in inputs.items()},
            output=None,
        )

        error_to_raise: Exception | None = None
        try:
            if weave_client is not None:
                # Use op.call() to get both result and call object with ref
                # Note: op.call() never raises - errors are captured in the Call object
                output, call = callable.call(**inputs)
                span.output = output
                # Store the weave call ref URI
                span.weave_call_ref = call.ref.uri()
                # Check if the call had an exception
                if call.exception is not None:
                    span.error = call.exception
                    # Re-raise with the original error message
                    error_to_raise = Exception(call.exception)
            else:
                # Weave not initialized - just call directly (no tracing)
                output = callable(**inputs)
                span.output = output
        except Exception as e:
            span.error = str(e)
            error_to_raise = e

        span.end_time_unix_nano = time.time()
        self.spans[callable_name].append(span)

        if error_to_raise is not None:
            raise error_to_raise

        return output

    async def get_json_schema(self, callable_name: str) -> dict[str, Any]:
        """Get the JSON schema for a callable's inputs.

        Args:
            callable_name: The name of the registered callable.

        Returns:
            A JSON schema object describing the callable's input parameters.

        Raises:
            HTTPException: If the callable is not found.
        """
        if callable_name not in self.callables:
            raise HTTPException(
                status_code=404, detail=f"Callable '{callable_name}' not found"
            )

        callable = self.callables[callable_name]
        return get_callable_input_json_schema(callable)

    async def get_calls(self, callable_name: str) -> list[Span]:
        """Get all calls (spans) for a given callable.

        Args:
            callable_name: The name of the callable.

        Returns:
            List of spans representing call history.

        Raises:
            HTTPException: If the callable is not found.
        """
        if callable_name not in self.callables:
            raise HTTPException(
                status_code=404, detail=f"Callable '{callable_name}' not found"
            )

        return self.spans[callable_name]

    def start(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start the debugger server.

        Args:
            host: Host address to bind to. Defaults to "0.0.0.0".
            port: Port to listen on. Defaults to 8000.
        """
        self.app = FastAPI(title="Weave Debugger")

        self.app.add_middleware(
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

        # Register endpoints with path variables
        @self.app.get("/callables")
        async def list_callables() -> list[str]:
            return await self.list_callables()

        @self.app.post("/callables/{callable_name}")
        async def invoke_callable(
            callable_name: str, inputs: dict[str, Any]
        ) -> Any:
            return await self.invoke_callable(callable_name, inputs)

        @self.app.get("/callables/{callable_name}/json_schema")
        async def get_json_schema(callable_name: str) -> dict[str, Any]:
            return await self.get_json_schema(callable_name)

        @self.app.get("/callables/{callable_name}/calls")
        async def get_calls(callable_name: str) -> list[Span]:
            return await self.get_calls(callable_name)

        uvicorn.run(
            self.app,
            host=host,
            port=port,
        )


def derive_callable_name(callable: Callable[..., Any]) -> str:
    """Derive the name of a callable from its __name__ attribute."""
    return callable.__name__


def safe_serialize_input_value(value: Any) -> Any:
    """Safely serialize a value for storage in a span.

    Args:
        value: The value to serialize.

    Returns:
        A JSON-serializable representation of the value.
    """
    if isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, (list, tuple)):
        return [safe_serialize_input_value(item) for item in value]
    elif isinstance(value, dict):
        return {k: safe_serialize_input_value(v) for k, v in value.items()}
    else:
        try:
            return str(value)
        except Exception:
            return "<<SERIALIZATION_ERROR>>"


def get_callable_input_json_schema(callable: Callable[..., Any]) -> dict[str, Any]:
    """Generate a JSON schema for a callable's input parameters.

    Uses Pydantic's TypeAdapter for robust type-to-JSON-schema conversion.

    Args:
        callable: The function to generate schema for.

    Returns:
        A JSON schema object with properties for each parameter.

    Examples:
        >>> def my_func(a: int, b: str = "default") -> float:
        ...     pass
        >>> schema = get_callable_input_json_schema(my_func)
        >>> schema["properties"]["a"]["type"]
        'integer'
    """
    sig = inspect.signature(callable)
    type_hints: dict[str, Any] = {}
    try:
        type_hints = inspect.get_annotations(callable)
    except Exception:
        pass

    properties: dict[str, Any] = {}
    required: list[str] = []
    defs: dict[str, Any] = {}

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        annotation = type_hints.get(param_name)

        if annotation is not None:
            # Use Pydantic's TypeAdapter to generate the JSON schema
            adapter = TypeAdapter(annotation)
            param_schema = adapter.json_schema()

            # Extract $defs if present and merge into our definitions
            if "$defs" in param_schema:
                defs.update(param_schema.pop("$defs"))
        else:
            # No type annotation - allow any type
            param_schema = {}

        # Add default value if present
        if param.default is not inspect.Parameter.empty:
            param_schema["default"] = _serialize_default(param.default)
        else:
            required.append(param_name)

        properties[param_name] = param_schema

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }

    if required:
        schema["required"] = required

    if defs:
        schema["$defs"] = defs

    return schema


def _serialize_default(value: Any) -> Any:
    """Serialize a default value for JSON schema.

    Args:
        value: The default value to serialize.

    Returns:
        A JSON-serializable representation of the default value.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize_default(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize_default(v) for k, v in value.items()}
    return str(value)
