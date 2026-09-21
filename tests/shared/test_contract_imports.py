from types import ModuleType

import pytest

from weave.shared import (
    common_interface,
    feedback_types,
    http_service_interface,
    project_id,
    query,
    service_interface,
)
from weave.shared.builtin_object_classes import (
    annotation_spec,
    base_object_def,
    leaderboard,
)
from weave.trace_server import common_interface as legacy_common
from weave.trace_server import http_service_interface as legacy_http
from weave.trace_server import service_interface as legacy_service
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
from weave.utils import project_id as legacy_project_id


@pytest.mark.parametrize(
    ("legacy_module", "shared_module"),
    [
        (legacy_common, common_interface),
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
