from types import ModuleType

import pytest

from weave.shared import (
    common_interface,
    errors,
    feedback_types,
    http_service_interface,
    project_id,
    query,
    refs_conversion,
    sensitive_data_policy,
    service_interface,
    trace_server_interface,
)
from weave.shared.agents import constants as agent_constants
from weave.shared.agents import schema as agent_schema
from weave.shared.agents import semconv
from weave.shared.agents import types as agent_types
from weave.shared.builtin_object_classes import (
    annotation_spec,
    base_object_def,
    leaderboard,
    saved_view,
)
from weave.trace_server import common_interface as legacy_common
from weave.trace_server import errors as legacy_errors
from weave.trace_server import http_service_interface as legacy_http
from weave.trace_server import service_interface as legacy_service
from weave.trace_server import trace_server_converter as legacy_converter
from weave.trace_server import trace_server_interface as legacy_interface
from weave.trace_server.agents import constants as legacy_agent_constants
from weave.trace_server.agents import schema as legacy_agent_schema
from weave.trace_server.agents import semconv as legacy_semconv
from weave.trace_server.agents import types as legacy_agent_types
from weave.trace_server.interface import feedback_types as legacy_feedback
from weave.trace_server.interface import query as legacy_query
from weave.trace_server.interface.builtin_object_classes import (
    annotation_spec as legacy_annotation,
)
from weave.trace_server.interface.builtin_object_classes import (
    base_object_def as legacy_base,
)
from weave.trace_server.interface.builtin_object_classes import (
    leaderboard as legacy_leaderboard,
)
from weave.trace_server.interface.builtin_object_classes import (
    saved_view as legacy_saved_view,
)
from weave.trace_server.sensitive_data import policy as legacy_policy
from weave.utils import project_id as legacy_project_id


@pytest.mark.parametrize(
    ("legacy_module", "shared_module"),
    [
        (legacy_common, common_interface),
        (legacy_interface, trace_server_interface),
        (legacy_agent_types, agent_types),
        (legacy_agent_schema, agent_schema),
        (legacy_agent_constants, agent_constants),
        (legacy_semconv, semconv),
        (legacy_policy, sensitive_data_policy),
        (legacy_saved_view, saved_view),
        (legacy_converter, refs_conversion),
        (legacy_annotation, annotation_spec),
        (legacy_base, base_object_def),
        (legacy_leaderboard, leaderboard),
        (legacy_project_id, project_id),
        (legacy_feedback, feedback_types),
        (legacy_http, http_service_interface),
        (legacy_query, query),
        (legacy_service, service_interface),
    ],
)
def test_legacy_contract_exports_preserve_identity(
    legacy_module: ModuleType, shared_module: ModuleType
) -> None:
    for name in vars(legacy_module)["__all__"]:
        assert vars(legacy_module)[name] is vars(shared_module)[name]


def test_legacy_exceptions_preserve_identity() -> None:
    for name, value in vars(errors).items():
        if isinstance(value, type) and issubclass(value, Exception):
            assert vars(legacy_errors)[name] is value

    with pytest.raises(legacy_errors.InvalidExternalRef, match="bad ref"):
        raise errors.InvalidExternalRef("bad ref")
