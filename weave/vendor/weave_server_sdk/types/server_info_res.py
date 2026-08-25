# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["ServerInfoRes"]


class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str

    trace_server_version: str
