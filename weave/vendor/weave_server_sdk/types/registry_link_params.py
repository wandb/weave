# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["RegistryLinkParams", "Target"]


class RegistryLinkParams(TypedDict, total=False):
    ref: Required[str]

    target: Required[Target]

    aliases: SequenceNotStr[str]


class Target(TypedDict, total=False):
    entity_name: Required[str]

    portfolio_name: Required[str]

    project_name: Required[str]
