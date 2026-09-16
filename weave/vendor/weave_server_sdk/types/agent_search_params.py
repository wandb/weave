# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["AgentSearchParams"]


class AgentSearchParams(TypedDict, total=False):
    project_id: Required[str]

    agent_name: Optional[str]

    conversation_id: Optional[str]

    limit: int

    offset: int

    provider_name: Optional[str]

    query: str

    request_model: Optional[str]

    roles: Optional[List[Literal["", "user", "assistant", "system", "tool", "tool_call", "tool_result"]]]

    started_after: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    started_before: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    trace_id: Optional[str]

    truncate_content: bool
