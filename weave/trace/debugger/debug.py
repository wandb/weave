from typing import Callable

import uvicorn
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

# from weave.trace.debugger.cert import get_ssl_certs
from fastapi.middleware.cors import CORSMiddleware

class Debugger:
    target_callable: Callable

    def __init__(self, target_callable: Callable):
        self.target_callable = target_callable

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
        self.app.get("/")(self.root)
        self.app.post("/trace")(self.trace)
        self.app.get("/spec")(self.spec)


    

    async def root(self) -> dict:
        return {"message": "Hello, World!"}

    async def trace(self,  a:int, b:int) -> int:
        return self.target_callable(a, b)

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
        # cert_path, key_path = get_ssl_certs()

        uvicorn.run(
            self.app,
            host=host,
            port=port,
            # allowed_origins=["localhost:9002"]
            # ssl_keyfile=key_path,
            # ssl_certfile=cert_path,
        )
