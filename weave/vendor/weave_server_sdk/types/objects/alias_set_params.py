# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from ..._types import SequenceNotStr

__all__ = ["AliasSetParams"]


class AliasSetParams(TypedDict, total=False):
    aliases: Required[SequenceNotStr[str]]

    digest: Required[str]

    project_id: Required[str]
