import pytest

from weave.shared.interface.builtin_object_classes import (
    annotation_spec,
    builtin_object_registry,
    leaderboard,
    llm_structured_model,
    saved_view,
    test_only_example,
)
from weave.trace_server.interface.builtin_object_classes import (
    annotation_spec as annotation_spec_legacy,
)
from weave.trace_server.interface.builtin_object_classes import (
    builtin_object_registry as builtin_object_registry_legacy,
)
from weave.trace_server.interface.builtin_object_classes import (
    leaderboard as leaderboard_legacy,
)
from weave.trace_server.interface.builtin_object_classes import (
    llm_structured_model as llm_structured_model_legacy,
)
from weave.trace_server.interface.builtin_object_classes import (
    saved_view as saved_view_legacy,
)
from weave.trace_server.interface.builtin_object_classes import (
    test_only_example as test_only_example_legacy,
)

pytestmark = pytest.mark.trace_server


def test_trace_server_builtin_object_classes_reexport_the_same_objects() -> None:
    assert annotation_spec.AnnotationSpec is annotation_spec_legacy.AnnotationSpec
    assert leaderboard.Leaderboard is leaderboard_legacy.Leaderboard
    assert saved_view.SavedView is saved_view_legacy.SavedView
    assert saved_view.Column is saved_view_legacy.Column
    assert saved_view.Pin is saved_view_legacy.Pin
    assert (
        test_only_example.TestOnlyNestedBaseModel
        is test_only_example_legacy.TestOnlyNestedBaseModel
    )
    assert (
        builtin_object_registry.BUILTIN_OBJECT_REGISTRY
        is builtin_object_registry_legacy.BUILTIN_OBJECT_REGISTRY
    )
    assert (
        llm_structured_model._prepare_llm_messages
        is llm_structured_model_legacy._prepare_llm_messages
    )
