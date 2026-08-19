# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable
from typing_extensions import Required, TypeAlias, TypedDict

__all__ = [
    "TableUpdateParams",
    "Update",
    "UpdateTableAppendSpec",
    "UpdateTableAppendSpecAppend",
    "UpdateTablePopSpec",
    "UpdateTablePopSpecPop",
    "UpdateTableInsertSpec",
    "UpdateTableInsertSpecInsert",
]


class TableUpdateParams(TypedDict, total=False):
    base_digest: Required[str]

    project_id: Required[str]

    updates: Required[Iterable[Update]]


class UpdateTableAppendSpecAppend(TypedDict, total=False):
    row: Required[Dict[str, object]]


class UpdateTableAppendSpec(TypedDict, total=False):
    append: Required[UpdateTableAppendSpecAppend]


class UpdateTablePopSpecPop(TypedDict, total=False):
    index: Required[int]


class UpdateTablePopSpec(TypedDict, total=False):
    pop: Required[UpdateTablePopSpecPop]


class UpdateTableInsertSpecInsert(TypedDict, total=False):
    index: Required[int]

    row: Required[Dict[str, object]]


class UpdateTableInsertSpec(TypedDict, total=False):
    insert: Required[UpdateTableInsertSpecInsert]


Update: TypeAlias = Union[UpdateTableAppendSpec, UpdateTablePopSpec, UpdateTableInsertSpec]
