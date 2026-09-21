import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from weave.flow.llm_structured_model import LLMStructuredCompletionModel as RuntimeModel
from weave.shared.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel as ValidationModel,
)
from weave.shared.digest import compute_object_digest
from weave.shared.object_class_util import dump_object
from weave.trace.serialization.serialize import from_json
from weave.trace.weave_client import WeaveClient

CASES = json.loads(Path(__file__).with_name("llm_model_baseline.json").read_text())


@pytest.mark.parametrize("case", CASES)
def test_llm_validation_and_digest_contract(case: dict[str, Any]) -> None:
    runtime = RuntimeModel.model_validate(case["input"])
    passive = ValidationModel.model_validate(case["input"])
    assert runtime.model_dump(mode="json") == case["model_dump"]
    assert passive.model_dump(mode="json") == case["model_dump"]
    if "digest_error" in case:
        with pytest.raises(TypeError, match="ObjectRef is not JSON serializable"):
            compute_object_digest(case["input"], "LLMStructuredCompletionModel")
    else:
        assert dump_object(passive) == dump_object(runtime) == case["dump"]
        assert (
            compute_object_digest(case["input"], "LLMStructuredCompletionModel")
            == case["digest"]
        )


def test_llm_schema_contract() -> None:
    assert ValidationModel.model_json_schema() == RuntimeModel.model_json_schema()


@pytest.mark.parametrize("model", [RuntimeModel, ValidationModel])
def test_llm_rejects_unknown_fields(
    model: type[RuntimeModel] | type[ValidationModel],
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate({"llm_model_id": "gpt-4", "unknown": "field"})


def test_llm_deserialization_uses_executable_model(client: WeaveClient) -> None:
    payload = dump_object(ValidationModel(llm_model_id="gpt-4"))
    result = from_json(payload, client.project_id, client.server)
    assert type(result) is RuntimeModel
    assert callable(result.predict)
