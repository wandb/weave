import pytest
from pydantic import ValidationError

from weave.flow.llm_structured_model import LLMStructuredCompletionModel as SDKModel
from weave.shared.object_class_util import dump_object
from weave.shared.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    BUILTIN_OBJECT_REGISTRY as SCHEMA_REGISTRY,
)
from weave.shared.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel as SchemaModel,
)
from weave.trace.base_objects import BUILTIN_OBJECT_REGISTRY as SDK_REGISTRY
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel as LegacyModel,
)

pytestmark = pytest.mark.trace_server


def test_registry_roles_and_legacy_execution_identity() -> None:
    assert SCHEMA_REGISTRY is not SDK_REGISTRY
    assert SCHEMA_REGISTRY["LLMStructuredCompletionModel"] is SchemaModel
    assert SDK_REGISTRY["LLMStructuredCompletionModel"] is SDKModel
    assert LegacyModel is SDKModel
    assert set(SCHEMA_REGISTRY) == set(SDK_REGISTRY)


def test_builtin_schema_and_stored_identity_match_sdk() -> None:
    assert SchemaModel.model_json_schema() == SDKModel.model_json_schema()
    assert dump_object(SchemaModel(llm_model_id="gpt-4o")) == dump_object(
        SDKModel(llm_model_id="gpt-4o")
    )


@pytest.mark.parametrize("model", [SchemaModel, SDKModel])
def test_schema_rejects_unknown_fields(model) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({"llm_model_id": "gpt-4o", "unknown": True})


@pytest.mark.parametrize(
    "payload",
    [
        {
            "llm_model_id": "gpt-4o",
            "ref": {"entity": "e", "project": "p", "name": "model", "_digest": "abc"},
        },
        {
            "llm_model_id": "gpt-4o",
            "_type": "LLMStructuredCompletionModel",
            "_class_name": "LLMStructuredCompletionModel",
            "_bases": ["Model", "Object", "BaseModel"],
            "default_params": {"temperature": 0.5},
        },
    ],
)
def test_wire_payload_normalization_matches_sdk(payload) -> None:
    assert (
        SchemaModel.model_validate(payload).model_dump()
        == SDKModel.model_validate(payload).model_dump()
    )
