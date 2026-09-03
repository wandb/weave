"""Serialization JSON Schema for usage *Res models marks defaults required."""

from __future__ import annotations

from typing import Any

from weave.trace_server.trace_server_interface import (
    CallsUsageReq,
    CallsUsageRes,
    LLMAggregatedUsage,
    TableCreateRes,
    TraceUsageReq,
    TraceUsageRes,
)

_RESPONSE_ROOTS = (TraceUsageRes, CallsUsageRes)


def _schemas_with_properties(
    schema: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = [("root", schema)]
    defs = schema.get("$defs") or {}
    for name, sub in defs.items():
        if isinstance(sub, dict) and "properties" in sub:
            out.append((name, sub))
    return out


def test_usage_response_serialization_requires_every_property() -> None:
    for model in _RESPONSE_ROOTS:
        schema = model.model_json_schema(mode="serialization")
        for name, sub in _schemas_with_properties(schema):
            props = set(sub.get("properties") or {})
            required = set(sub.get("required") or [])
            assert required == props, f"{model.__name__}:{name} {required=} {props=}"


def test_usage_response_validation_still_allows_defaults() -> None:
    for model in (LLMAggregatedUsage, TraceUsageRes, CallsUsageRes):
        schema = model.model_json_schema(mode="validation")
        required = set(schema.get("required") or [])
        props = set(schema.get("properties") or {})
        assert required == set()
        assert required < props


def test_usage_request_validation_unchanged() -> None:
    usage_req = TraceUsageReq.model_json_schema(mode="validation")
    assert set(usage_req.get("required") or []) == {"project_id"}
    calls_req = CallsUsageReq.model_json_schema(mode="validation")
    assert set(calls_req.get("required") or []) == {"project_id", "call_ids"}


def test_table_create_row_digests_stay_optional() -> None:
    schema = TableCreateRes.model_json_schema(mode="serialization")
    required = set(schema.get("required") or [])
    props = set(schema.get("properties") or {})
    assert "row_digests" in props
    assert "row_digests" not in required


def test_usage_models_constructor_and_dump_keep_defaults() -> None:
    usage = LLMAggregatedUsage()
    dumped = usage.model_dump()
    assert dumped["requests"] == 0
    assert dumped["prompt_tokens_total_cost"] is None

    res = TraceUsageRes()
    dumped_res = res.model_dump()
    assert dumped_res["call_usage"] == {}
    assert dumped_res["unfinished_call_ids"] == []
