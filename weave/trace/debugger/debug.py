import time
from typing import Callable
from fastapi import FastAPI,Request
from fastapi.openapi.utils import get_openapi

import uvicorn

class Debugger:
    target_callable: Callable

    def __init__(self, target_callable: Callable):
        self.target_callable = target_callable

        # Setup FastAPI app
        self.app = FastAPI()
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

    def start(self):

        uvicorn.run(self.app, host="0.0.0.0", port=8000)
