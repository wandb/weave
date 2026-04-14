from __future__ import annotations

from pydantic import BaseModel, Field

from weave.trace.env import weave_trace_server_url
from weave.trace_server.common_interface import BaseModelStrict
from weave.trace_server_bindings.http_utils import handle_response_error
from weave.utils import http_requests
from weave.wandb_interface.context import get_wandb_api_context

LINK_TO_REGISTRY_PATH = "/link_to_registry"


class CreateAndLinkWeaveAssetTarget(BaseModelStrict):
    portfolio_name: str
    entity_name: str
    project_name: str


class CreateAndLinkWeaveAssetReq(BaseModelStrict):
    ref: str
    target: CreateAndLinkWeaveAssetTarget
    aliases: list[str] = Field(default_factory=list)


class CreateAndLinkWeaveAssetRes(BaseModel):
    version_index: int | None = None


def create_and_link_weave_asset(
    req: CreateAndLinkWeaveAssetReq,
) -> CreateAndLinkWeaveAssetRes:
    """Post a `/link_to_registry` request to the trace server.

    Args:
        req: Typed request payload containing the source object ref, destination
            registry target, and optional aliases.

    Returns:
        CreateAndLinkWeaveAssetRes: Parsed response from the registry-link endpoint.
    """
    api_key = get_wandb_api_context()
    if api_key is None:
        raise ValueError("No API key found")

    url = f"{weave_trace_server_url()}{LINK_TO_REGISTRY_PATH}"
    response = http_requests.post(
        url,
        json=req.model_dump(mode="json"),
        auth=("api", api_key),
    )
    handle_response_error(response, url)

    return CreateAndLinkWeaveAssetRes.model_validate(response.json())
