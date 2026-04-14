from __future__ import annotations

from unittest.mock import patch

import pytest

from weave.prompt.prompt import StringPrompt
from weave.trace import api, weave_client
from weave.trace.context import weave_client_context
from weave.trace.refs import ObjectRef
from weave.trace_server_bindings.create_and_link_weave_asset import (
    CreateAndLinkWeaveAssetRes,
)

MOCK_TARGET = "weave.trace.weave_client.create_and_link_weave_asset"
PROMPT_REF = ObjectRef(
    entity="source-entity",
    project="source-project",
    name="my-prompt",
    _digest="v1",
)


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
    """Patch the transport and return a canned response."""
    with patch(
        MOCK_TARGET,
        return_value=CreateAndLinkWeaveAssetRes(version_index=2),
    ) as m:
        yield m


def _published_prompt() -> StringPrompt:
    prompt = StringPrompt("Hello {name}")
    prompt.ref = PROMPT_REF
    return prompt


@pytest.mark.parametrize(
    ("prompt_input", "aliases", "expected_aliases"),
    [
        pytest.param(_published_prompt(), None, [], id="published-prompt"),
        pytest.param(PROMPT_REF, ["prod"], ["prod"], id="object-ref"),
        pytest.param(PROMPT_REF.uri, ("prod", "latest"), ["prod", "latest"], id="uri-string"),
    ],
)
def test_link_prompt_to_registry_resolves_input_and_builds_request(
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


def test_link_prompt_to_registry_rejects_unpublished_prompt(client):
    """Raise before making the transport call when the prompt has no ref."""
    with patch(MOCK_TARGET) as transport:
        with pytest.raises(ValueError, match="published prompt or object"):
            client.link_prompt_to_registry(
                StringPrompt("Hello {name}"),
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
def test_link_prompt_to_registry_rejects_invalid_target_paths(client, target_path):
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


def test_api_link_prompt_to_registry_delegates_to_active_client(client):
    """The top-level API function delegates to the active WeaveClient."""
    expected = CreateAndLinkWeaveAssetRes(version_index=0)

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
