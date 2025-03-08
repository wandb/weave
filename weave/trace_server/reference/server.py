from fastapi import APIRouter, FastAPI

from weave.trace_server.reference.generate import (
    ServerDependency,
    generate_routes,
    noop_trace_server_factory,
)

server_dependency = ServerDependency(server_factory=noop_trace_server_factory)
trace_service_router = generate_routes(APIRouter(), server_dependency)
app = FastAPI()
app.include_router(trace_service_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
