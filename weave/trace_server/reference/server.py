from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.reference import generate_server


class StubTraceServer(tsi.TraceServerInterface): ...


stub_server = StubTraceServer()
app = generate_server(stub_server)
