from weave.flow import llm_structured_model as llm_structured_model_sdk
from weave.trace.builtin_object_classes import llm_structured_model
from weave.trace.object_record import class_all_bases_names, pydantic_object_record


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
