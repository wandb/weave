import datetime

import httpx

import weave
from weave.trace.sampling import (
    SAMPLING_DECISION_ATTRIBUTE,
    decide_project_sampling,
    find_matching_rule,
    xxh64_int,
)
from weave.trace.sampling_client import SamplingClient
from weave.trace_server import trace_server_interface as tsi


def _rule(
    scope: str,
    op_pattern: str,
    rate: float,
    updated_at: datetime.datetime,
) -> tsi.SamplingRuleSchema:
    return tsi.SamplingRuleSchema(
        scope=scope,
        op_pattern=op_pattern,
        rate=rate,
        updated_at=updated_at,
    )


def test_sampling_matcher_hash_and_exemptions():
    project_id = "entity/project"
    now = datetime.datetime.now(datetime.timezone.utc)
    rules = [
        _rule(f"project:{project_id}", "", 0.9, now),
        _rule(f"project:{project_id}", "openai.*", 0.5, now),
        _rule(f"project:{project_id}", "openai.chat.*", 0.25, now),
        _rule(f"project:{project_id}", "openai.chat.create", 0.1, now),
        _rule(f"project:{project_id}", "same.*", 0.4, now),
        _rule(
            f"project:{project_id}",
            "same.?",
            0.3,
            now + datetime.timedelta(seconds=1),
        ),
    ]
    snapshot = tsi.SamplingRulesSnapshotRes(
        project_id=project_id,
        rules=rules,
        etag="sha256-test",
        snapshot_updated_at=now,
    )

    # Specificity: exact, longest glob prefix, empty catch-all, then updated_at tie-break.
    assert find_matching_rule(rules, "openai.chat.create").rate == 0.1
    assert (
        find_matching_rule(
            rules, f"weave:///{project_id}/op/openai.chat.create:deadbeef"
        ).rate
        == 0.1
    )
    assert find_matching_rule(rules, "openai.chat.stream").rate == 0.25
    assert find_matching_rule(rules, "anthropic.messages").rate == 0.9
    assert find_matching_rule(rules, "same.x").rate == 0.3

    # Hash implementation matches the xxh64 seed-0 public empty-string vector.
    assert xxh64_int(b"", seed=0) == 0xEF46DB3751D8E999

    # Server-shipped exemptions keep evaluation traffic regardless of matching rules.
    op_exempt = decide_project_sampling(
        snapshot,
        trace_id="trace-1",
        op_name="weave.Evaluation.predict",
        attributes={},
    )
    attr_exempt = decide_project_sampling(
        snapshot,
        trace_id="trace-1",
        op_name="openai.chat.create",
        attributes={"weave": {"eval": True}},
    )
    assert op_exempt.keep is True
    assert attr_exempt.keep is True
    assert attr_exempt.reason == "exempt"


def test_sdk_sampling_drop_disables_nested_tracing(client):
    client.server.sampling_rules_update(
        tsi.SamplingRulesUpdateReq(
            project_id=client.project_id,
            scope=f"project:{client.project_id}",
            op_pattern="",
            rate=0.0,
            wb_user_id="test-user",
        )
    )
    client.sampling_client._refresh_once()
    snapshot = client.sampling_client._get_snapshot()
    assert snapshot is not None
    assert client.sampling_client._started is True
    assert [(rule.scope, rule.op_pattern, rule.rate) for rule in snapshot.rules] == [
        (f"project:{client.project_id}", "", 0.0)
    ]
    assert (
        decide_project_sampling(
            snapshot,
            trace_id="trace-1",
            op_name="parent",
            attributes={},
        ).keep
        is False
    )

    @weave.op
    def child() -> str:
        return "child"

    @weave.op
    def parent() -> str:
        return child()

    decisions = []
    original_decide_root = client.sampling_client.decide_root

    def recording_decide_root(**kwargs):
        current_snapshot = client.sampling_client._get_snapshot()
        assert current_snapshot is not None
        assert current_snapshot.rules
        decision = original_decide_root(**kwargs)
        decisions.append(decision)
        return decision

    client.sampling_client.decide_root = recording_decide_root
    try:
        assert parent() == "child"
        assert len(decisions) == 1
        assert decisions[0].keep is False
    finally:
        client.sampling_client.decide_root = original_decide_root
    client.flush()
    assert list(client.get_calls()) == []
    assert (
        client.server.objs_query(
            tsi.ObjQueryReq(
                project_id=client.project_id,
                filter=tsi.ObjectVersionFilter(is_op=True),
            )
        ).objs
        == []
    )

    client.server.sampling_rules_update(
        tsi.SamplingRulesUpdateReq(
            project_id=client.project_id,
            scope=f"project:{client.project_id}",
            op_pattern="",
            rate=1.0,
            enabled=False,
            wb_user_id="test-user",
        )
    )
    client.sampling_client._refresh_once()

    assert parent() == "child"
    client.flush()
    calls = list(client.get_calls())
    assert len(calls) == 2
    root = next(call for call in calls if call.parent_id is None)
    assert root.attributes[SAMPLING_DECISION_ATTRIBUTE] == "keep"
    child_call = next(call for call in calls if call.parent_id == root.id)
    assert child_call.attributes[SAMPLING_DECISION_ATTRIBUTE] == "keep"


def test_sampling_client_fails_open_for_http_errors():
    class MissingSamplingEndpointServer:
        def sampling_rules_read(self, req: tsi.SamplingRulesReadReq):
            request = httpx.Request("POST", "http://trace-server/sampling/rules/read")
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError(
                "sampling endpoint missing",
                request=request,
                response=response,
            )

    sampling_client = SamplingClient(MissingSamplingEndpointServer(), "entity/project")
    try:
        decision = sampling_client.decide_root(
            trace_id="trace-1",
            op_name="expensive_op",
            attributes={},
        )
    finally:
        sampling_client.close()

    assert decision.keep is True
