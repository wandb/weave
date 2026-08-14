import datetime
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel

from weave.trace_server.insights import action_items
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)

BASE_URL = "http://example.com"
NOW = datetime.datetime(2026, 6, 20, tzinfo=datetime.timezone.utc)


@pytest.fixture
def server():
    return RemoteHTTPTraceServer(BASE_URL, should_batch=False)


def _item() -> action_items.ActionItem:
    return action_items.ActionItem(
        project_id="entity/project",
        cluster_run_id="019ff4bc-2ae1-744d-ae3a-285998a90519",
        cluster_id="019ff4bc-2ae1-744d-ae3a-285998a9051a",
        run_window_end=NOW,
        signature_type="failure",
        id="019ff4bc-2ae1-744d-ae3a-285998a9051c",
        action_item_config_sha="cfg-a",
        title="Honor the requested output path",
        description="The agent ignored an explicit output path.",
        evidence_trace_ids=["trace-4"],
        status=action_items.ActionItemStatus.OPEN,
        severity=action_items.ActionItemSeverity.SEVERE,
        inserted_at=NOW,
        expire_at=datetime.datetime(2100, 1, 1, tzinfo=datetime.timezone.utc),
    )


@pytest.mark.parametrize(
    ("method_name", "req", "expected_url", "res_type", "res_json"),
    [
        pytest.param(
            "action_items_batch_upsert",
            action_items.ActionItemsBatchUpsertReq(items=[_item()]),
            "/insights/action-items/batch-upsert",
            action_items.ActionItemsBatchUpsertRes,
            {"ids": [_item().id]},
            id="batch-upsert",
        ),
        pytest.param(
            "action_items_query",
            action_items.ActionItemsQueryReq(
                project_id="entity/project",
                cluster_run_id=_item().cluster_run_id,
                cluster_id=_item().cluster_id,
                statuses=[action_items.ActionItemStatus.OPEN],
                severities=[action_items.ActionItemSeverity.SEVERE],
            ),
            "/insights/action-items/query",
            action_items.ActionItemsQueryRes,
            {"items": [_item().model_dump(mode="json")]},
            id="query",
        ),
        pytest.param(
            "action_item_update",
            action_items.ActionItemUpdateReq(
                project_id="entity/project",
                cluster_run_id=_item().cluster_run_id,
                cluster_id=_item().cluster_id,
                id=_item().id,
                status=action_items.ActionItemStatus.COMPLETED,
                severity=action_items.ActionItemSeverity.MAJOR,
            ),
            "/insights/action-items/update",
            action_items.ActionItemUpdateRes,
            {"item": _item().model_dump(mode="json")},
            id="update",
        ),
    ],
)
def test_action_item_route_posts_complete_request_and_parses_response(
    server: RemoteHTTPTraceServer,
    method_name: str,
    req: BaseModel,
    expected_url: str,
    res_type: type[BaseModel],
    res_json: dict,
) -> None:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = res_json

    with patch.object(server, "post", return_value=response) as mock_post:
        result = getattr(server, method_name)(req)

    mock_post.assert_called_once()
    assert mock_post.call_args[0][0] == expected_url
    assert json.loads(mock_post.call_args[1]["data"]) == json.loads(
        req.model_dump_json(by_alias=True)
    )
    assert isinstance(result, res_type)


def test_action_item_update_requires_an_edit() -> None:
    with pytest.raises(ValueError, match="status or severity is required"):
        action_items.ActionItemUpdateReq(
            project_id="entity/project",
            cluster_run_id=_item().cluster_run_id,
            cluster_id=_item().cluster_id,
            id=_item().id,
        )
