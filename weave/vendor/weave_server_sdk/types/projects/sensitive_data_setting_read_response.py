# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["SensitiveDataSettingReadResponse"]


class SensitiveDataSettingReadResponse(BaseModel):
    policy: Literal["off", "pii-v1"]
