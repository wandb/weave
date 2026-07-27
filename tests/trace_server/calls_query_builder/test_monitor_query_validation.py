"""Unit tests for saved-Monitor query validation.

Agent monitors (op_names include an agent-span op) validate against the
agent-spans schema, so logical fields like `operation_name` are accepted there
but still rejected on a regular monitor (validated against the calls schema).
"""

import pytest

from weave.flow.monitor import AGENT_SPAN_OP_NAMES as FLOW_AGENT_SPAN_OP_NAMES
from weave.trace_server.agents.constants import AGENT_SPAN_OP_NAMES
from weave.trace_server.calls_query_builder.monitor_query_validation import (
    validate_monitor_query_fields,
)
from weave.trace_server.errors import InvalidFieldError, InvalidRequest

AGENT_OP = next(iter(AGENT_SPAN_OP_NAMES))
# A normalized (non-agent) op-name ref, as a regular monitor stores them.
CALL_OP_REF = "weave:///entity/project/op/my_op:abc123"


def _eq(field: str, value: object) -> dict:
    return {"$expr": {"$eq": [{"$getField": field}, {"$literal": value}]}}


def _monitor_val(*, op_names: list[str], query: object) -> dict:
    return {
        "_type": "Monitor",
        "_class_name": "Monitor",
        "_bases": ["Monitor", "Object", "BaseModel"],
        "op_names": op_names,
        "query": query,
    }


def _validate(val: dict) -> None:
    validate_monitor_query_fields("Monitor", "Monitor", val)


class TestConstantInSync:
    def test_agent_span_op_names_mirror_flow(self) -> None:
        # The trace-server copy is mirrored from weave/flow/monitor.py so the
        # trace server can detect agent monitors without importing weave.flow.
        assert AGENT_SPAN_OP_NAMES == FLOW_AGENT_SPAN_OP_NAMES


class TestAgentMonitorQuery:
    def test_operation_name_filter_accepted(self) -> None:
        # The reported bug: an agent signal filtering on Operation name = "chat"
        # was rejected with a 422 because it was validated against calls_merged.
        _validate(
            _monitor_val(op_names=[AGENT_OP], query=_eq("operation_name", "chat"))
        )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("agent_name", "my-agent"),
            ("agent_version", "v1"),
            ("provider_name", "openai"),
            ("request_model", "gpt-4"),
            ("response_model", "gpt-4"),
            ("tool_name", "search"),
            ("tool_type", "function"),
            ("conversation_id", "conv-1"),
            ("status_code", "OK"),
            ("error_type", "timeout"),
            ("span_kind", "agent"),
            ("wb_run_id", "run-1"),
        ],
    )
    def test_logical_agent_fields_accepted(self, field: str, value: str) -> None:
        _validate(_monitor_val(op_names=[AGENT_OP], query=_eq(field, value)))

    def test_anded_filters_accepted(self) -> None:
        query = {
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "operation_name"}, {"$literal": "chat"}]},
                    {"$eq": [{"$getField": "agent_name"}, {"$literal": "bot"}]},
                ]
            }
        }
        _validate(_monitor_val(op_names=[AGENT_OP], query=query))

    def test_agent_monitor_alongside_other_op_names(self) -> None:
        # Membership is enough; a mixed op_names list still counts as agent.
        _validate(
            _monitor_val(
                op_names=[CALL_OP_REF, AGENT_OP],
                query=_eq("operation_name", "chat"),
            )
        )

    def test_unresolvable_agent_field_rejected(self) -> None:
        # Field-compared-to-field offers no literal type to infer a custom-attr
        # map from, so it can't resolve to a column -> fail loudly.
        query = {
            "$expr": {
                "$eq": [
                    {"$getField": "totally_unknown"},
                    {"$getField": "also_unknown"},
                ]
            }
        }
        with pytest.raises(InvalidRequest):
            _validate(_monitor_val(op_names=[AGENT_OP], query=query))


class TestRegularMonitorQuery:
    def test_calls_field_accepted(self) -> None:
        _validate(_monitor_val(op_names=[CALL_OP_REF], query=_eq("op_name", "foo")))

    def test_attributes_path_accepted(self) -> None:
        _validate(
            _monitor_val(
                op_names=[CALL_OP_REF],
                query=_eq("attributes.weave.operation.name", "chat"),
            )
        )

    def test_logical_agent_field_still_rejected(self) -> None:
        # A non-agent monitor must keep rejecting agent-span logical names; the
        # error carries the allowed-calls-field list (InvalidFieldError).
        with pytest.raises(InvalidFieldError):
            _validate(
                _monitor_val(
                    op_names=[CALL_OP_REF], query=_eq("operation_name", "chat")
                )
            )


class TestNoQuery:
    def test_agent_monitor_without_query_is_noop(self) -> None:
        _validate(_monitor_val(op_names=[AGENT_OP], query=None))

    def test_regular_monitor_without_query_is_noop(self) -> None:
        _validate(_monitor_val(op_names=[CALL_OP_REF], query=None))

    def test_non_monitor_object_ignored(self) -> None:
        # Non-Monitor objects are never validated, even with a Monitor-ish val.
        validate_monitor_query_fields(
            "Scorer",
            "Scorer",
            _monitor_val(op_names=[AGENT_OP], query=_eq("not_a_field", 1)),
        )
