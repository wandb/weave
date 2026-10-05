import pytest

from weave.shared import (
    common_interface,
    http_service_interface,
    service_interface,
    trace_server_converter,
    trace_server_interface,
    validation,
)
from weave.shared.agents import constants, schema, semconv
from weave.shared.agents import types as agent_types
from weave.shared.helpers import url_safety
from weave.shared.interface import feedback_types
from weave.shared.sensitive_data import policy
from weave.trace_server import common_interface as common_interface_legacy
from weave.trace_server import http_service_interface as http_service_interface_legacy
from weave.trace_server import service_interface as service_interface_legacy
from weave.trace_server import trace_server_converter as trace_server_converter_legacy
from weave.trace_server import trace_server_interface as trace_server_interface_legacy
from weave.trace_server import validation as validation_legacy
from weave.trace_server.agents import constants as constants_legacy
from weave.trace_server.agents import schema as schema_legacy
from weave.trace_server.agents import semconv as semconv_legacy
from weave.trace_server.agents import types as agent_types_legacy
from weave.trace_server.helpers import url_safety as url_safety_legacy
from weave.trace_server.interface import feedback_types as feedback_types_legacy
from weave.trace_server.sensitive_data import policy as policy_legacy

pytestmark = pytest.mark.trace_server


def test_trace_server_paths_are_the_shared_modules() -> None:
    assert trace_server_interface is trace_server_interface_legacy
    assert common_interface is common_interface_legacy
    assert service_interface is service_interface_legacy
    assert http_service_interface is http_service_interface_legacy
    assert trace_server_converter is trace_server_converter_legacy
    assert validation is validation_legacy
    assert agent_types is agent_types_legacy
    assert semconv is semconv_legacy
    assert constants is constants_legacy
    assert feedback_types is feedback_types_legacy
    assert policy is policy_legacy
    assert url_safety is url_safety_legacy


def test_trace_server_agents_schema_reexports_the_shared_types() -> None:
    assert schema_legacy.NormalizedMessage is schema.NormalizedMessage
    assert schema_legacy.SpanKindLiteral is schema.SpanKindLiteral
    assert schema_legacy.StatusCodeLiteral is schema.StatusCodeLiteral
