# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["TtlSettingUpdateParams"]


class TtlSettingUpdateParams(TypedDict, total=False):
    project_id: Required[str]

    retention_days: Optional[int]
    """None disables TTL; must be None or >= 1"""

    wb_user_id: Optional[str]
