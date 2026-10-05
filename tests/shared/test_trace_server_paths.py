import importlib

import pytest

from weave.shared.agents import schema
from weave.trace_server.agents import schema as schema_legacy

pytestmark = pytest.mark.trace_server


@pytest.mark.parametrize(
    "module",
    [
        "agents.constants",
        "agents.semconv",
        "agents.types",
        "common_interface",
        "helpers.url_safety",
        "http_service_interface",
        "interface.feedback_types",
        "sensitive_data.policy",
        "service_interface",
        "trace_server_converter",
        "trace_server_interface",
        "validation",
    ],
)
def test_trace_server_path_is_the_shared_module(module: str) -> None:
    legacy = importlib.import_module(f"weave.trace_server.{module}")
    assert legacy is importlib.import_module(f"weave.shared.{module}")


def test_trace_server_agents_schema_reexports_the_shared_types() -> None:
    assert schema_legacy.NormalizedMessage is schema.NormalizedMessage
    assert schema_legacy.SpanKindLiteral is schema.SpanKindLiteral
    assert schema_legacy.StatusCodeLiteral is schema.StatusCodeLiteral
