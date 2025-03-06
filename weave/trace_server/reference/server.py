from fastapi import APIRouter, FastAPI

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.reference.generate import ServerDependency, generate_routes


class StubTraceServer(tsi.TraceServerInterface): ...


# The type ignore here is safe.  We are just inheriting from the protocol to generate a
# stub implementation.  By definition, the stub should have all the methods of the protocol.
stub_server = StubTraceServer()  # type: ignore


app = FastAPI()
router = APIRouter()

# Create a server dependency that simply returns the stub server
server_dependency = ServerDependency(
    auth_dependency=lambda: None,  # No auth for the stub server
    server_factory=lambda _: stub_server,  # Always return the stub server
)

router = generate_routes(router, server_dependency)
app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
