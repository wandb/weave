"""Serialization JSON Schema for agent *Res models marks defaults required."""

from __future__ import annotations

from typing import Any

from weave.trace_server.agents.types import (
    AgentConversationChatRes,
    AgentConversationSpansRes,
    AgentCustomAttrsSchemaRes,
    AgentSearchRes,
    AgentSpanSchema,
    AgentSpansQueryReq,
    AgentSpansQueryRes,
    AgentSpanStatsRes,
    AgentsQueryReq,
    AgentsQueryRes,
    AgentTraceChatRes,
    AgentVersionsQueryRes,
)

_RESPONSE_ROOTS = (
    AgentsQueryRes,
    AgentVersionsQueryRes,
    AgentSpansQueryRes,
    AgentSpanStatsRes,
    AgentCustomAttrsSchemaRes,
    AgentSearchRes,
    AgentTraceChatRes,
    AgentConversationChatRes,
    AgentConversationSpansRes,
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


def test_agent_response_serialization_requires_every_property() -> None:
    for model in _RESPONSE_ROOTS:
        schema = model.model_json_schema(mode="serialization")
        for name, sub in _schemas_with_properties(schema):
            props = set(sub.get("properties") or {})
            required = set(sub.get("required") or [])
            assert required == props, f"{model.__name__}:{name} {required=} {props=}"


def test_agent_span_schema_validation_still_allows_defaults() -> None:
    schema = AgentSpanSchema.model_json_schema(mode="validation")
    required = set(schema.get("required") or [])
    props = set(schema.get("properties") or {})
    assert required == {"project_id", "trace_id", "span_id"}
    assert required < props


def test_agent_query_request_validation_unchanged() -> None:
    for model in (AgentsQueryReq, AgentSpansQueryReq):
        schema = model.model_json_schema(mode="validation")
        assert set(schema.get("required") or []) == {"project_id"}


def test_agent_span_schema_constructor_and_dump_keep_defaults() -> None:
    span = AgentSpanSchema(project_id="p", trace_id="t", span_id="s")
    dumped = span.model_dump()
    assert dumped["parent_span_id"] is None
    assert dumped["finish_reasons"] == []
    assert dumped["input_messages"] == []
