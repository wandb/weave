# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional
from typing_extensions import Required, TypedDict

__all__ = ["V2RuntimeApplyParams", "RuntimeID"]


class V2RuntimeApplyParams(TypedDict, total=False):
    entity: Required[str]

    project: Required[str]

    base_url: Required[str]
    """Public OpenAI-compatible endpoint base URL"""

    runtime_ids: Required[Iterable[RuntimeID]]
    """Complete desired list of IDs exposed by the endpoint"""

    api_key_secret: Optional[str]
    """Team secret name used as the endpoint API key; never the secret value"""

    headers: Dict[str, str]
    """Literal headers forwarded to the endpoint"""


class RuntimeID(TypedDict, total=False):
    id: Required[str]
    """Value sent in the OpenAI-compatible request model field"""

    max_tokens: int
    """Maximum tokens supported by this runtime ID"""
