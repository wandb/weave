from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, FastAPI, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from weave.trace_server.reference.generate import (
    ServiceDependency,
    generate_routes,
    noop_trace_server_factory,
)

security = HTTPBasic()


def authenticate(
    creds: Annotated[HTTPBasicCredentials, Depends(security)],
    wandb: Annotated[str | None, Cookie(include_in_schema=False)],
    wandb_qa: Annotated[str | None, Cookie(include_in_schema=False)],
    use_admin_privileges: Annotated[str | None, Header(include_in_schema=False)],
    origin: Annotated[str | None, Header(include_in_schema=False)],
) -> None: ...  # This is just a stub for codegen


server_dependency = ServiceDependency(service_factory=noop_trace_server_factory)
trace_service_router = generate_routes(APIRouter(), server_dependency)
app = FastAPI()
app.include_router(trace_service_router, dependencies=[Depends(authenticate)])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
