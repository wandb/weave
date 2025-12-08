from typing import Callable

import uvicorn
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

# from weave.trace.debugger.cert import get_ssl_certs
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from collections import defaultdict
from pydantic import BaseModel
import time
import inspect
from typing import Coroutine, Any
from functools import wraps
class Span(BaseModel):
    name: str
    start_time_unix_nano: float
    end_time_unix_nano: float
    inputs: dict
    output: Any
    error: Optional[str] = None

class Debugger:
    callables: dict[str, Callable]
    spans: dict[str, list[Span]]

    def __init__(self):
        self.callables = {}
        self.spans = defaultdict(list)
        
    def add_callable(self, callable: Callable, *, name: Optional[str] = None) -> None:
        if name is None:
            name = derive_callable_name(callable)

        if name in self.callables:
            raise ValueError(f"Callable with name {name} already exists")

        self.callables[name] = callable


    async def get_callable_names(self) -> list[str]:
        return list(self.callables.keys())

    async def get_spans(self, name: str) -> list[Span]:
        return self.spans[name]

    def make_call_fn(self, name: str) -> Coroutine:

        callable = self.callables[name]

        @wraps(callable)
        async def call_fn(*args, **kwargs):
            bound_args = inspect.signature(callable).bind(*args, **kwargs)
            bound_args.apply_defaults()
            inputs = {k: safe_serialize_input_value(v) for k, v in bound_args.arguments.items()}

            span = Span(
                name=name,
                start_time_unix_nano=time.time(),
                end_time_unix_nano=time.time(),
                inputs=inputs,
                output=None)
            try:
                output = callable(*args, **kwargs)
                span.output = output
            except Exception as e:
                span.error = str(e)
            span.end_time_unix_nano = time.time()
            self.spans[name].append(span)

            if span.error is not None:
                raise span.error

            return output
        return call_fn

    # async def trace(self,  a:int, b:int) -> int:
    #     return self.target_callable(a, b)

    async def spec(self) -> dict:
            return get_openapi(
            title=self.app.title,
            version=self.app.version,
            openapi_version=self.app.openapi_version,
            description=self.app.description,
            routes=self.app.routes,
        )

    def start(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start the debugger server with HTTPS.

        Automatically generates a self-signed certificate for local development.

        Args:
            host: Host address to bind to. Defaults to "0.0.0.0".
            port: Port to listen on. Defaults to 8000.
        """
        # Setup FastAPI app
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
        # Docs site:
        "https://wandb.github.io",
        "https://weave_scorer.wandb.test",
        # environment.wandb_public_base_url(),
    ],
    allow_origin_regex=r"https://.+\.wandb\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
        self.app.get("/callables")(self.get_callable_names)


        for name, callable in self.callables.items():
            self.app.post(f"/callables/{name}")(self.make_call_fn(name))

 
        self.app.get("/spec")(self.spec)

        self.app.get("/spans/{name}")(self.get_spans)

        uvicorn.run(
            self.app,
            host=host,
            port=port,
            # allowed_origins=["localhost:9002"]
            # ssl_keyfile=key_path,
            # ssl_certfile=cert_path,
        )



def derive_callable_name(callable: Callable) -> str:   
    return callable.__name__

def safe_serialize_input_value(value: Any) -> Any:
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