import datetime
import uuid

import pytest

from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import RequestTooLarge

MODEL = "gpt-4"
STARTED_AT = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)


@pytest.mark.parametrize("limit", [4, 5, 8])
@pytest.mark.parametrize("include_costs", [False, True])
def test_calls_usage_preserves_complete_traces(
    client: WeaveClient, limit: int, include_costs: bool
) -> None:
    first_root, first_child, first_unfinished = _create_trace(client)
    second_root, _, second_unfinished = _create_trace(client)
    missing_id = str(uuid.uuid4())
    request = tsi.CallsUsageReq(
        project_id=client.project_id,
        call_ids=[first_root, first_child, second_root, missing_id, first_root],
        include_costs=include_costs,
        limit=limit,
    )

    result = client.server.calls_usage(request)

    assert set(result.call_usage) == {
        first_root,
        first_child,
        second_root,
        missing_id,
    }
    assert result.call_usage[missing_id] == {}
    assert set(result.unfinished_call_ids) == {first_unfinished, second_unfinished}
    for call_id in [first_root, first_child, second_root]:
        usage = result.call_usage[call_id][MODEL]
        assert usage.prompt_tokens == 5
        assert usage.completion_tokens == 2
        assert usage.total_tokens == 7
        if include_costs:
            assert usage.prompt_tokens_total_cost is not None
            assert usage.prompt_tokens_total_cost > 0
            assert usage.completion_tokens_total_cost is not None
            assert usage.completion_tokens_total_cost > 0
        else:
            assert usage.prompt_tokens_total_cost is None
            assert usage.completion_tokens_total_cost is None

    complete = client.server.calls_usage(request.model_copy(update={"limit": 8}))
    assert result == complete


def test_calls_usage_rejects_incomplete_single_trace(client: WeaveClient) -> None:
    root_id, child_id, _ = _create_trace(client)

    with pytest.raises(RequestTooLarge, match="single trace exceeds"):
        client.server.calls_usage(
            tsi.CallsUsageReq(
                project_id=client.project_id,
                call_ids=[root_id, child_id],
                limit=3,
            )
        )


def _create_trace(client: WeaveClient) -> tuple[str, str, str]:
    trace_id = str(uuid.uuid4())
    root_id, child_id, leaf_id, unfinished_id = [str(uuid.uuid4()) for _ in range(4)]
    calls = [
        (root_id, str(uuid.uuid4()), 0),
        (child_id, root_id, 2),
        (leaf_id, child_id, 3),
        (unfinished_id, root_id, 0),
    ]

    for index, (call_id, parent_id, prompt_tokens) in enumerate(calls):
        started_at = STARTED_AT + datetime.timedelta(seconds=index)
        client.server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=client.project_id,
                    id=call_id,
                    trace_id=trace_id,
                    parent_id=parent_id,
                    op_name="usage-limit-test",
                    started_at=started_at,
                    attributes={},
                    inputs={},
                )
            )
        )
        if call_id == unfinished_id:
            continue

        summary: tsi.SummaryInsertMap = {}
        if prompt_tokens:
            summary = {
                "usage": {
                    MODEL: {"prompt_tokens": prompt_tokens, "completion_tokens": 1}
                }
            }
        client.server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=client.project_id,
                    id=call_id,
                    ended_at=started_at + datetime.timedelta(seconds=1),
                    summary=summary,
                )
            )
        )

    return root_id, child_id, unfinished_id
