# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional
from typing_extensions import Required, TypedDict

__all__ = ["TableCreateParams", "Table"]


class TableCreateParams(TypedDict, total=False):
    table: Required[Table]


class Table(TypedDict, total=False):
    project_id: Required[str]

    rows: Required[Iterable[Dict[str, object]]]

    expected_digest: Optional[str]
    """Client-computed table digest for server-side validation."""
