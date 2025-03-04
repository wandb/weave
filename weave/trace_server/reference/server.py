from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.reference.generate import generate_server


class StubTraceServer(tsi.TraceServerInterface): ...


# The type ignore here is safe.  We are just inheriting from the protocol to generate a
# stub implementation.  By definition, the stub should have all the methods of the protocol.
stub_server = StubTraceServer()  # type: ignore


app = generate_server(stub_server)
