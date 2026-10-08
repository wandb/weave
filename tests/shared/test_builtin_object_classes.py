import pytest

from weave.flow import llm_structured_model as llm_structured_model_sdk
from weave.shared.interface.builtin_object_classes import (
    annotation_spec,
    builtin_object_registry,
    leaderboard,
    llm_structured_model,
    saved_view,
    test_only_example,
)
from weave.trace.object_record import class_all_bases_names, pydantic_object_record
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
    assert llm_structured_model_legacy is llm_structured_model_sdk
    assert llm_structured_model_legacy.Message is llm_structured_model.Message
    assert (
        llm_structured_model_legacy.LLMStructuredCompletionModelDefaultParams
        is llm_structured_model.LLMStructuredCompletionModelDefaultParams
    )
    assert (
        llm_structured_model_legacy.parse_response
        is llm_structured_model.parse_response
    )


def test_llm_structured_model_schema_matches_the_sdk_model() -> None:
    assert (
        llm_structured_model.LLMStructuredCompletionModel.model_json_schema()
        == llm_structured_model_sdk.LLMStructuredCompletionModel.model_json_schema()
    )
    record = pydantic_object_record(
        llm_structured_model.LLMStructuredCompletionModel(llm_model_id="gpt-4o")
    )
    assert record._bases == class_all_bases_names(
        llm_structured_model_sdk.LLMStructuredCompletionModel
    )
