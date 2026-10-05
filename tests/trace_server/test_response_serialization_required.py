"""Serialization JSON Schema for response *Res models marks defaults required."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from weave.trace_server.trace_server_interface import (
    CallsUsageReq,
    CallsUsageRes,
    CustomRuntimeApplyReq,
    CustomRuntimeApplyRes,
    DatasetSourcesLinkRes,
    DatasetSourcesQueryRes,
    EvalResultsQueryRes,
    EvalResultsScorerStats,
    EvalResultsSummaryRes,
    EvaluationStatusRes,
    EvaluationStatusRunning,
    FeedbackAggregateBucket,
    FeedbackAggregateRes,
    GenAISpanRef,
    ImageGenerationCreateRes,
    LLMAggregatedUsage,
    ProjectTTLSettingsReadRes,
    TableCreateRes,
    TraceUsageReq,
    TraceUsageRes,
)

_RESPONSE_ROOTS = (
    TraceUsageRes,
    CallsUsageRes,
    EvalResultsQueryRes,
    EvalResultsSummaryRes,
    CustomRuntimeApplyRes,
    EvaluationStatusRes,
    ImageGenerationCreateRes,
    FeedbackAggregateRes,
    DatasetSourcesQueryRes,
    DatasetSourcesLinkRes,
    ProjectTTLSettingsReadRes,
)


def _schemas_with_properties(
    schema: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = [("root", schema)]
    defs = schema.get("$defs") or {}
    for name, sub in defs.items():
        if isinstance(sub, dict) and "properties" in sub:
            out.append((name, sub))
    return out


def _declared_required(model: type[BaseModel]) -> set[str]:
    return {name for name, field in model.model_fields.items() if field.is_required()}


def test_response_serialization_requires_every_property() -> None:
    for model in _RESPONSE_ROOTS:
        schema = model.model_json_schema(mode="serialization")
        for name, sub in _schemas_with_properties(schema):
            props = set(sub.get("properties") or {})
            required = set(sub.get("required") or [])
            assert required == props, f"{model.__name__}:{name} {required=} {props=}"


def test_response_validation_still_allows_defaults() -> None:
    # The flag is serialization-only: a validation schema still requires exactly the
    # fields that carry no default.
    for model in (
        LLMAggregatedUsage,
        TraceUsageRes,
        CallsUsageRes,
        EvaluationStatusRunning,
        EvalResultsScorerStats,
        FeedbackAggregateBucket,
        ProjectTTLSettingsReadRes,
    ):
        schema = model.model_json_schema(mode="validation")
        required = set(schema.get("required") or [])
        props = set(schema.get("properties") or {})
        assert required == _declared_required(model), f"{model.__name__} {required=}"
        assert required < props


def test_response_request_validation_unchanged() -> None:
    usage_req = TraceUsageReq.model_json_schema(mode="validation")
    assert set(usage_req.get("required") or []) == {"project_id"}
    calls_req = CallsUsageReq.model_json_schema(mode="validation")
    assert set(calls_req.get("required") or []) == {"project_id", "call_ids"}
    # The flag is serialization-only, so the request body still accepts a missing
    # max_tokens even though CustomRuntimeIDRes is marked.
    apply_req = CustomRuntimeApplyReq.model_json_schema(mode="validation")
    runtime_id = apply_req["$defs"]["CustomRuntimeID"]
    assert "max_tokens" in runtime_id["properties"]
    assert "max_tokens" not in set(runtime_id.get("required") or [])


def test_genai_span_ref_stays_one_schema() -> None:
    # GenAISpanRef is reachable from a request as well as a response, so the day its two
    # schemas differ FastAPI splits the generated name into -Input and -Output.
    assert GenAISpanRef.model_json_schema(
        mode="validation"
    ) == GenAISpanRef.model_json_schema(mode="serialization")


def test_table_create_row_digests_stay_optional() -> None:
    schema = TableCreateRes.model_json_schema(mode="serialization")
    required = set(schema.get("required") or [])
    props = set(schema.get("properties") or {})
    assert "row_digests" in props
    assert "row_digests" not in required


def test_response_models_constructor_and_dump_keep_defaults() -> None:
    usage = LLMAggregatedUsage()
    dumped = usage.model_dump()
    assert dumped["requests"] == 0
    assert dumped["prompt_tokens_total_cost"] is None

    res = TraceUsageRes()
    dumped_res = res.model_dump()
    assert dumped_res["call_usage"] == {}
    assert dumped_res["unfinished_call_ids"] == []

    status = EvaluationStatusRunning(completed_rows=1, total_rows=2)
    assert status.model_dump()["code"] == "running"

    ttl = ProjectTTLSettingsReadRes()
    assert ttl.model_dump()["retention_days"] is None
