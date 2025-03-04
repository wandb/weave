from fastapi import APIRouter, FastAPI

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.reference.generate import generate_routes


class StubTraceServer(tsi.TraceServerInterface): ...


# The type ignore here is safe.  We are just inheriting from the protocol to generate a
# stub implementation.  By definition, the stub should have all the methods of the protocol.
stub_server = StubTraceServer()  # type: ignore


app = FastAPI()
router = APIRouter()
router = generate_routes(router, stub_server)
app.include_router(router)
