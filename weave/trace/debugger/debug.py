"""Debugger module for exposing local functions as a traceable service."""

import inspect
import time
from collections import defaultdict
from collections.abc import Callable
from functools import wraps
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel


class Span(BaseModel):
    """Represents a single execution span of a callable."""

    name: str
    start_time_unix_nano: float
    end_time_unix_nano: float
    inputs: dict[str, Any]
    output: Any
    error: str | None = None


class Debugger:
    """Exposes local callables as a traceable HTTP service."""

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

        self.callables[name] = callable

    async def get_callable_names(self) -> list[str]:
        """Get the names of all registered callables."""
        return list(self.callables.keys())

    async def get_spans(self, name: str) -> list[Span]:
        """Get all spans for a given callable name."""
        return self.spans[name]

    def make_call_fn(self, name: str) -> Callable[..., Any]:
        """Create an async wrapper function for the named callable.

        Args:
            name: The name of the registered callable.

        Returns:
            An async function that wraps the callable with span tracking.
        """
        callable = self.callables[name]

        @wraps(callable)
        async def call_fn(*args: Any, **kwargs: Any) -> Any:
            bound_args = inspect.signature(callable).bind(*args, **kwargs)
            bound_args.apply_defaults()
            inputs = {
                k: safe_serialize_input_value(v)
                for k, v in bound_args.arguments.items()
            }

            span = Span(
                name=name,
                start_time_unix_nano=time.time(),
                end_time_unix_nano=time.time(),
                inputs=inputs,
                output=None,
            )
            error_to_raise: Exception | None = None
            try:
                output = callable(*args, **kwargs)
                span.output = output
            except Exception as e:
                span.error = str(e)
                error_to_raise = e
            span.end_time_unix_nano = time.time()
            self.spans[name].append(span)

            if error_to_raise is not None:
                raise error_to_raise

            return output

        return call_fn

    async def spec(self) -> dict[str, Any]:
        """Get the OpenAPI specification for the debugger service."""
        return get_openapi(
            title=self.app.title,
            version=self.app.version,
            openapi_version=self.app.openapi_version,
            description=self.app.description,
            routes=self.app.routes,
        )

    def start(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start the debugger server.

        Args:
            host: Host address to bind to. Defaults to "0.0.0.0".
            port: Port to listen on. Defaults to 8000.
        """
        self.app = FastAPI()

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
        self.app.get("/callables")(self.get_callable_names)

        for name in self.callables.keys():
            self.app.post(f"/callables/{name}")(self.make_call_fn(name))

        self.app.get("/spec")(self.spec)
        self.app.get("/spans/{name}")(self.get_spans)

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
