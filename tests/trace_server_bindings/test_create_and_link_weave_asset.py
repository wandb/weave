from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from weave.trace_server_bindings.create_and_link_weave_asset import (
    LINK_TO_REGISTRY_PATH,
    CreateAndLinkWeaveAssetReq,
    CreateAndLinkWeaveAssetTarget,
    create_and_link_weave_asset,
)

_MODULE = "weave.trace_server_bindings.create_and_link_weave_asset"

DEFAULT_REQ = CreateAndLinkWeaveAssetReq(
    ref="weave:///source-entity/source-project/object/my-prompt:v1",
    target=CreateAndLinkWeaveAssetTarget(
        portfolio_name="prompt-registry",
        entity_name="target-entity",
        project_name="target-project",
    ),
)


def _http_response(status_code: int, json_data: dict) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=json_data,
        request=httpx.Request("POST", f"http://example.com{LINK_TO_REGISTRY_PATH}"),
    )


@pytest.fixture
def mock_post():
    """Patch API key, server URL, and http_requests.post for the transport."""
    with (
        patch(f"{_MODULE}.get_wandb_api_context", return_value="api-key"),
        patch(f"{_MODULE}.weave_trace_server_url", return_value="http://example.com"),
        patch(f"{_MODULE}.http_requests.post") as post,
    ):
        yield post


def test_sends_expected_request(mock_post: MagicMock) -> None:
    """POST the correct URL, auth, and payload; parse the typed response."""
    req = CreateAndLinkWeaveAssetReq(
        ref=DEFAULT_REQ.ref,
        target=DEFAULT_REQ.target,
        aliases=["prod", "latest"],
    )
    mock_post.return_value = _http_response(200, {"version_index": 7})

    result = create_and_link_weave_asset(req)

    assert result.version_index == 7
    mock_post.assert_called_once()
    assert mock_post.call_args.args[0] == "http://example.com/link_to_registry"
    assert mock_post.call_args.kwargs["auth"] == ("api", "api-key")
    assert mock_post.call_args.kwargs["json"] == req.model_dump(mode="json")


def test_defaults_aliases_to_empty_list(mock_post: MagicMock) -> None:
    """Omitted aliases serialize as an empty list."""
    mock_post.return_value = _http_response(200, {"version_index": None})

    create_and_link_weave_asset(DEFAULT_REQ)

    payload = mock_post.call_args.kwargs["json"]
    assert payload["aliases"] == []


def test_surfaces_http_errors(mock_post: MagicMock) -> None:
    """Non-2xx responses raise HTTPStatusError."""
    mock_post.return_value = _http_response(400, {"message": "invalid request"})

    with pytest.raises(httpx.HTTPStatusError, match="invalid request"):
        create_and_link_weave_asset(DEFAULT_REQ)


def test_raises_when_no_api_key() -> None:
    """Raise ValueError when no API key is available."""
    with patch(f"{_MODULE}.get_wandb_api_context", return_value=None):
        with pytest.raises(ValueError, match="No API key found"):
            create_and_link_weave_asset(DEFAULT_REQ)
