# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["FileContentParams"]


class FileContentParams(TypedDict, total=False):
    digest: Required[str]

    project_id: Required[str]
