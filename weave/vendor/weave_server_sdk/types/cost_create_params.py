# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["CostCreateParams", "Costs"]


class CostCreateParams(TypedDict, total=False):
    costs: Required[Dict[str, Costs]]

    project_id: Required[str]

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""


class Costs(TypedDict, total=False):
    completion_token_cost: Required[float]

    prompt_token_cost: Required[float]

    cache_creation_input_token_cost: float

    cache_read_input_token_cost: float

    completion_token_cost_unit: Optional[str]
    """The unit of the cost for the completion tokens"""

    effective_date: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """
    The date after which the cost is effective for, will default to the current date
    if not provided
    """

    prompt_token_cost_unit: Optional[str]
    """The unit of the cost for the prompt tokens"""

    provider_id: Optional[str]
    """The provider of the LLM, e.g.

    'openai' or 'mistral'. If not provided, the provider_id will be set to 'default'
    """
