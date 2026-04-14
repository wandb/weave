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


class DummyServer:
    """Minimal server stub for WeaveClient tests."""

    def projects_info(self, req):
        _ = req
        return []


def make_client() -> weave_client.WeaveClient:
    """Create a lightweight client without touching the network."""
    return weave_client.WeaveClient(
        entity="current-entity",
        project="current-project",
        server=DummyServer(),
        ensure_project_exists=False,
    )


@pytest.fixture
def client() -> weave_client.WeaveClient:
    """Provide a lightweight client for registry-link helper tests."""
    return make_client()


def make_response() -> CreateAndLinkWeaveAssetRes:
    """Create a typed response for registry-link helper tests."""
    return CreateAndLinkWeaveAssetRes(
        version_index=2,
    )


def make_prompt_ref() -> ObjectRef:
    """Create a published prompt ref for registry-link helper tests."""
    return ObjectRef(
        entity="source-entity",
        project="source-project",
        name="my-prompt",
        _digest="v1",
    )


def test_weave_client_link_prompt_to_registry_uses_current_project_for_prompt_input(
    client,
):
    """Resolve a published prompt object and default the target entity."""
    prompt = StringPrompt("Hello {name}")
    prompt.ref = make_prompt_ref()

    with patch(
        "weave.trace.weave_client.create_and_link_weave_asset",
        return_value=make_response(),
    ) as mock_transport:
        result = client.link_prompt_to_registry(
            prompt,
            target_path="wandb-registry-prompts/my-prompt-collection",
        )

    assert result.version_index == 2

    req = mock_transport.call_args.args[0]
    assert req.ref == prompt.ref.uri
    assert req.target.portfolio_name == "my-prompt-collection"
    assert req.target.entity_name == "current-entity"
    assert req.target.project_name == "wandb-registry-prompts"
    assert req.aliases == []


def test_weave_client_link_prompt_to_registry_normalizes_ref_string_and_aliases(
    client,
):
    """Use fully qualified ref strings and normalize aliases."""
    prompt_ref = make_prompt_ref()

    with patch(
        "weave.trace.weave_client.create_and_link_weave_asset",
        return_value=make_response(),
    ) as mock_transport:
        client.link_prompt_to_registry(
            prompt_ref.uri,
            target_path="wandb-registry-prompts/my-prompt-collection",
            aliases=("prod", "latest"),
        )

    req = mock_transport.call_args.args[0]
    assert req.ref == prompt_ref.uri
    assert req.target.entity_name == "current-entity"
    assert req.target.project_name == "wandb-registry-prompts"
    assert req.target.portfolio_name == "my-prompt-collection"
    assert req.aliases == ["prod", "latest"]


def test_weave_client_link_prompt_to_registry_accepts_object_ref_input(client):
    """Accept an ObjectRef directly and normalize aliases."""
    prompt_ref = make_prompt_ref()

    with patch(
        "weave.trace.weave_client.create_and_link_weave_asset",
        return_value=make_response(),
    ) as mock_transport:
        result = client.link_prompt_to_registry(
            prompt_ref,
            target_path="wandb-registry-prompts/my-prompt-collection",
            aliases=["prod"],
        )

    assert result.version_index == 2

    req = mock_transport.call_args.args[0]
    assert req.ref == prompt_ref.uri
    assert req.target.entity_name == "current-entity"
    assert req.target.project_name == "wandb-registry-prompts"
    assert req.target.portfolio_name == "my-prompt-collection"
    assert req.aliases == ["prod"]


def test_weave_client_link_prompt_to_registry_rejects_unpublished_prompt(client):
    """Raise a clear error before making the transport call."""
    prompt = StringPrompt("Hello {name}")

    with patch("weave.trace.weave_client.create_and_link_weave_asset") as mock_transport:
        with pytest.raises(ValueError, match="published prompt or object"):
            client.link_prompt_to_registry(
                prompt,
                target_path="wandb-registry-prompts/my-prompt-collection",
            )

    mock_transport.assert_not_called()


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
def test_weave_client_link_prompt_to_registry_rejects_invalid_target_paths(
    client, target_path
):
    """Reject invalid W&B-style target paths before making the transport call."""
    prompt_ref = make_prompt_ref()

    with patch("weave.trace.weave_client.create_and_link_weave_asset") as mock_transport:
        with pytest.raises(
            ValueError,
            match=(
                r"target_path must match '<registry_project>/<portfolio_name>' "
                r"where registry_project starts with 'wandb-registry-'"
            ),
        ):
            client.link_prompt_to_registry(
                prompt_ref,
                target_path=target_path,
            )

    mock_transport.assert_not_called()


def test_api_link_prompt_to_registry_uses_active_client(client):
    """Delegate to the active client from `weave.trace.api`."""
    expected = make_response()

    weave_client_context.set_weave_client_global(client)
    try:
        with patch.object(
            client,
            "link_prompt_to_registry",
            return_value=expected,
        ) as mock_method:
            result = api.link_prompt_to_registry(
                "weave:///source-entity/source-project/object/my-prompt:v1",
                target_path="wandb-registry-prompts/my-prompt-collection",
            )
    finally:
        weave_client_context.set_weave_client_global(None)

    assert result == expected
    mock_method.assert_called_once_with(
        "weave:///source-entity/source-project/object/my-prompt:v1",
        target_path="wandb-registry-prompts/my-prompt-collection",
        aliases=None,
    )
