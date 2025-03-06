from fastapi import APIRouter, FastAPI

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.reference.generate import ServerDependency, generate_routes


class StubTraceService(tsi.TraceServerInterface): ...


# The type ignore here is safe.  We are just inheriting from the protocol to generate a
# stub implementation.  By definition, the stub should have all the methods of the protocol.
stub_server = StubTraceService()  # type: ignore
server_dependency = ServerDependency(
    endpoint_auth_mapping=None,  # No auth for the stub server
    server_factory=lambda auth, op_name: stub_server,
)

trace_service_router = generate_routes(APIRouter(), server_dependency)
app = FastAPI()
app.include_router(trace_service_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
