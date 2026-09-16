# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from ..._models import BaseModel

__all__ = ["TtlSettingReadResponse"]


class TtlSettingReadResponse(BaseModel):
    retention_days: Optional[int] = None
    """None = no TTL (infinite retention)"""
