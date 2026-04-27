from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from weave.trace.env import weave_trace_server_url
from weave.trace_server.common_interface import BaseModelStrict
from weave.trace_server_bindings.http_utils import handle_response_error
from weave.utils import http_requests
from weave.wandb_interface.context import get_wandb_api_context

LINK_TO_REGISTRY_PATH = "/link_to_registry"


class LinkAssetToRegistryTarget(BaseModelStrict):
    portfolio_name: str
    entity_name: str
    project_name: str


class LinkAssetToRegistryReq(BaseModelStrict):
    ref: str
    target: LinkAssetToRegistryTarget
    aliases: list[str] = Field(default_factory=list)


class LinkAssetToRegistryRes(BaseModel):
    # Be lenient on responses so older clients tolerate newly added server fields.
    model_config = ConfigDict(extra="ignore")

    version_index: int | None = None


def link_asset_to_registry(
    req: LinkAssetToRegistryReq,
) -> LinkAssetToRegistryRes:
    """Post a `/link_to_registry` request to the trace server.

    Args:
        req: Typed request payload containing the source object ref, destination
            registry target, and optional aliases.

    Returns:
        LinkAssetToRegistryRes: Parsed response from the registry-link endpoint.

    Raises:
        ValueError: If no authenticated API key is available.
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

    return LinkAssetToRegistryRes.model_validate(response.json())
