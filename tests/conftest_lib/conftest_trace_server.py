import pytest

from weave.trace_server.trace_server_interface import TraceServerInterface

from .http_trace_server import build_minimal_blind_authenticating_trace_server


@pytest.fixture
def get_http_trace_server():
    def _get_http_trace_server(resolver: TraceServerInterface):
        app = build_minimal_blind_authenticating_trace_server(
            resolver=resolver,
            assumed_user_id="test_user",
        )
        return app

    return _get_http_trace_server
