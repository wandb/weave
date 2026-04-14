from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from weave.trace_server_bindings.create_and_link_weave_asset import (
    LINK_TO_REGISTRY_PATH,
    CreateAndLinkWeaveAssetReq,
    CreateAndLinkWeaveAssetTarget,
    create_and_link_weave_asset,
)


def make_response(status_code: int, json_data: dict) -> httpx.Response:
    """Create an HTTP response for registry-link helper tests."""
    return httpx.Response(
        status_code,
        json=json_data,
        request=httpx.Request("POST", f"http://example.com{LINK_TO_REGISTRY_PATH}"),
    )


@patch(
    "weave.trace_server_bindings.create_and_link_weave_asset.get_wandb_api_context",
    return_value="api-key",
)
@patch(
    "weave.trace_server_bindings.create_and_link_weave_asset.weave_trace_server_url",
    return_value="http://example.com",
)
@patch("weave.trace_server_bindings.create_and_link_weave_asset.http_requests.post")
def test_create_and_link_weave_asset_sends_expected_request(
    mock_post, mock_trace_server_url, mock_api_key
) -> None:
    """Send the expected payload and parse the typed response."""
    req = CreateAndLinkWeaveAssetReq(
        ref="weave:///source-entity/source-project/object/my-prompt:v1",
        target=CreateAndLinkWeaveAssetTarget(
            portfolio_name="prompt-registry",
            entity_name="target-entity",
            project_name="target-project",
        ),
        aliases=["prod", "latest"],
    )
    mock_post.return_value = make_response(
        200,
        {
            "version_index": 7,
        },
    )

    result = create_and_link_weave_asset(req)

    assert result.version_index == 7

    mock_trace_server_url.assert_called_once_with()
    mock_api_key.assert_called_once_with()
    mock_post.assert_called_once()

    assert mock_post.call_args.args[0] == "http://example.com/link_to_registry"
    assert mock_post.call_args.kwargs["auth"] == ("api", "api-key")
    assert mock_post.call_args.kwargs["json"] == req.model_dump(mode="json")


@patch(
    "weave.trace_server_bindings.create_and_link_weave_asset.get_wandb_api_context",
    return_value="api-key",
)
@patch(
    "weave.trace_server_bindings.create_and_link_weave_asset.weave_trace_server_url",
    return_value="http://example.com",
)
@patch("weave.trace_server_bindings.create_and_link_weave_asset.http_requests.post")
def test_create_and_link_weave_asset_defaults_aliases_to_empty_list(
    mock_post, *_unused_mocks
) -> None:
    """Serialize omitted aliases as an empty list."""
    req = CreateAndLinkWeaveAssetReq(
        ref="weave:///source-entity/source-project/object/my-prompt:v1",
        target=CreateAndLinkWeaveAssetTarget(
            portfolio_name="prompt-registry",
            entity_name="target-entity",
            project_name="target-project",
        ),
    )
    mock_post.return_value = make_response(
        200,
        {
            "version_index": None,
        },
    )

    create_and_link_weave_asset(req)

    payload = mock_post.call_args.kwargs["json"]
    assert payload["aliases"] == []


@patch(
    "weave.trace_server_bindings.create_and_link_weave_asset.get_wandb_api_context",
    return_value="api-key",
)
@patch(
    "weave.trace_server_bindings.create_and_link_weave_asset.weave_trace_server_url",
    return_value="http://example.com",
)
@patch("weave.trace_server_bindings.create_and_link_weave_asset.http_requests.post")
def test_create_and_link_weave_asset_surfaces_http_errors(
    mock_post, *_unused_mocks
) -> None:
    """Raise the underlying HTTP status error for non-2xx responses."""
    req = CreateAndLinkWeaveAssetReq(
        ref="weave:///source-entity/source-project/object/my-prompt:v1",
        target=CreateAndLinkWeaveAssetTarget(
            portfolio_name="prompt-registry",
            entity_name="target-entity",
            project_name="target-project",
        ),
    )
    mock_post.return_value = make_response(
        400,
        {"message": "invalid request"},
    )

    with pytest.raises(httpx.HTTPStatusError, match="invalid request"):
        create_and_link_weave_asset(req)
