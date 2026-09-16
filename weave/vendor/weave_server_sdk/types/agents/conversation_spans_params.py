# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from ..._types import SequenceNotStr
from ..._utils import PropertyInfo

__all__ = ["ConversationSpansParams"]


class ConversationSpansParams(TypedDict, total=False):
    project_id: Required[str]

    conversation_ids: SequenceNotStr[str]

    started_after: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    started_before: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
