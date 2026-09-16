# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from ..._models import BaseModel

__all__ = ["IngestSamplingSettingReadResponse"]


class IngestSamplingSettingReadResponse(BaseModel):
    dry_run: bool

    sample_rate: float
