from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

import weave
from weave.prompt.prompt import StringPrompt
from weave.trace import api, weave_client
from weave.trace.context import weave_client_context
from weave.trace.refs import ObjectRef
from weave.trace_server_bindings.link_asset_to_registry import (
    LINK_TO_REGISTRY_PATH,
    LinkAssetToRegistryReq,
    LinkAssetToRegistryRes,
    LinkAssetToRegistryTarget,
    link_asset_to_registry,
)

MOCK_TARGET = "weave.trace.weave_client.link_asset_to_registry"
_TRANSPORT_MODULE = "weave.trace_server_bindings.link_asset_to_registry"

PROMPT_REF = ObjectRef(
    entity="source-entity",
    project="source-project",
    name="my-prompt",
    _digest="v1",
)

DEFAULT_TRANSPORT_REQ = LinkAssetToRegistryReq(
    ref="weave:///source-entity/source-project/object/my-prompt:v1",
    target=LinkAssetToRegistryTarget(
        portfolio_name="prompt-registry",
        entity_name="target-entity",
        project_name="target-project",
    ),
)


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


class DummyServer:
    """Minimal server stub that satisfies WeaveClient.__init__."""

    def projects_info(self, req):
        return []


@pytest.fixture
def client() -> weave_client.WeaveClient:
    """Lightweight client that never touches the network."""
    return weave_client.WeaveClient(
        entity="current-entity",
        project="current-project",
        server=DummyServer(),
        ensure_project_exists=False,
    )


@pytest.fixture
def mock_transport():
    """Patch the transport function and return a canned response."""
    with patch(
        MOCK_TARGET,
        return_value=LinkAssetToRegistryRes(version_index=2),
    ) as m:
        yield m


def _published_prompt() -> StringPrompt:
    prompt = StringPrompt("Hello {name}")
    prompt.ref = PROMPT_REF
    return prompt


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
        patch(f"{_TRANSPORT_MODULE}.get_wandb_api_context", return_value="api-key"),
        patch(
            f"{_TRANSPORT_MODULE}.weave_trace_server_url",
            return_value="http://example.com",
        ),
        patch(f"{_TRANSPORT_MODULE}.http_requests.post") as post,
    ):
        yield post


# ---------------------------------------------------------------------------
# Client-level tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prompt_input", "aliases", "expected_aliases"),
    [
        pytest.param(_published_prompt(), None, [], id="published-prompt"),
        pytest.param(PROMPT_REF, ["prod"], ["prod"], id="object-ref"),
        pytest.param(
            PROMPT_REF.uri, ("prod", "latest"), ["prod", "latest"], id="uri-string"
        ),
    ],
)
def test_resolves_input_and_builds_request(
    client, mock_transport, prompt_input, aliases, expected_aliases
):
    """Each accepted input type resolves to the same ref and builds a correct request."""
    result = client.link_prompt_to_registry(
        prompt_input,
        target_path="wandb-registry-prompts/my-prompt-collection",
        aliases=aliases,
    )

    assert result.version_index == 2

    req = mock_transport.call_args.args[0]
    assert req.ref == PROMPT_REF.uri
    assert req.target.entity_name == "current-entity"
    assert req.target.project_name == "wandb-registry-prompts"
    assert req.target.portfolio_name == "my-prompt-collection"
    assert req.aliases == expected_aliases


def test_rejects_unpublished_prompt(client):
    """Raise before making the transport call when the prompt has no ref."""
    with patch(MOCK_TARGET) as transport:
        with pytest.raises(ValueError, match="published prompt"):
            client.link_prompt_to_registry(
                StringPrompt("Hello {name}"),
                target_path="wandb-registry-prompts/my-prompt-collection",
            )

    transport.assert_not_called()


def test_rejects_published_non_prompt_object(client):
    """Reject published non-prompt objects before making the transport call."""
    obj = weave.Object(name="not-a-prompt")
    obj.ref = PROMPT_REF

    with patch(MOCK_TARGET) as transport:
        with pytest.raises(ValueError, match="published prompt"):
            client.link_prompt_to_registry(
                obj,
                target_path="wandb-registry-prompts/my-prompt-collection",
            )

    transport.assert_not_called()


@pytest.mark.parametrize(
    "target_path",
    [
        "",
        "wandb-registry-prompts",
        "wandb-registry-/my-prompt-collection",
        "wandb-registry-prompts/",
        "prompts/my-prompt-collection",
        "wandb-registry-prompts/my-prompt-collection/extra",
    ],
)
def test_rejects_invalid_target_paths(client, target_path):
    """Reject malformed target paths before making the transport call."""
    with patch(MOCK_TARGET) as transport:
        with pytest.raises(
            ValueError,
            match=r"target_path must match .* 'wandb-registry-'",
        ):
            client.link_prompt_to_registry(
                PROMPT_REF,
                target_path=target_path,
            )

    transport.assert_not_called()


def test_api_delegates_to_active_client(client):
    """The top-level API function delegates to the active WeaveClient."""
    expected = LinkAssetToRegistryRes(version_index=0)

    weave_client_context.set_weave_client_global(client)
    try:
        with patch.object(
            client,
            "link_prompt_to_registry",
            return_value=expected,
        ) as mock_method:
            result = api.link_prompt_to_registry(
                PROMPT_REF.uri,
                target_path="wandb-registry-prompts/my-prompt-collection",
            )
    finally:
        weave_client_context.set_weave_client_global(None)

    assert result == expected
    mock_method.assert_called_once_with(
        PROMPT_REF.uri,
        target_path="wandb-registry-prompts/my-prompt-collection",
        aliases=None,
    )


def test_top_level_weave_exports_link_prompt_to_registry():
    """Ensure weave.link_prompt_to_registry is re-exported from the top-level package."""
    assert weave.link_prompt_to_registry is api.link_prompt_to_registry


# ---------------------------------------------------------------------------
# Transport-level tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("req", "response_json", "expected_index", "expected_aliases"),
    [
        pytest.param(
            LinkAssetToRegistryReq(
                ref=DEFAULT_TRANSPORT_REQ.ref,
                target=DEFAULT_TRANSPORT_REQ.target,
                aliases=["prod", "latest"],
            ),
            {"version_index": 7},
            7,
            ["prod", "latest"],
            id="explicit-aliases",
        ),
        pytest.param(
            DEFAULT_TRANSPORT_REQ,
            {"version_index": None},
            None,
            [],
            id="default-aliases",
        ),
        pytest.param(
            DEFAULT_TRANSPORT_REQ,
            {"version_index": 7, "server_metadata": {"source": "future-server"}},
            7,
            [],
            id="ignores-extra-response-fields",
        ),
    ],
)
def test_transport_sends_expected_request(
    mock_post: MagicMock,
    req: LinkAssetToRegistryReq,
    response_json: dict,
    expected_index: int | None,
    expected_aliases: list[str],
) -> None:
    """POST the correct URL, auth, and payload; default aliases to empty list."""
    mock_post.return_value = _http_response(200, response_json)

    result = link_asset_to_registry(req)

    assert result.version_index == expected_index
    assert mock_post.call_args.args[0] == "http://example.com/link_to_registry"
    assert mock_post.call_args.kwargs["auth"] == ("api", "api-key")
    assert mock_post.call_args.kwargs["json"] == req.model_dump(mode="json")
    assert mock_post.call_args.kwargs["json"]["aliases"] == expected_aliases


def test_transport_surfaces_http_errors(mock_post: MagicMock) -> None:
    """Non-2xx responses raise HTTPStatusError."""
    mock_post.return_value = _http_response(400, {"message": "invalid request"})

    with pytest.raises(httpx.HTTPStatusError, match="invalid request"):
        link_asset_to_registry(DEFAULT_TRANSPORT_REQ)


def test_transport_raises_when_no_api_key() -> None:
    """Raise ValueError when no API key is available."""
    with patch(f"{_TRANSPORT_MODULE}.get_wandb_api_context", return_value=None):
        with pytest.raises(ValueError, match="No API key found"):
            link_asset_to_registry(DEFAULT_TRANSPORT_REQ)
