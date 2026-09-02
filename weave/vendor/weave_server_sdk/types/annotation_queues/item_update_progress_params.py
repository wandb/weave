# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["ItemUpdateProgressParams"]


class ItemUpdateProgressParams(TypedDict, total=False):
    queue_id: Required[str]

    annotation_state: Required[str]
    """New state: 'in_progress', 'completed', or 'skipped'"""

    project_id: Required[str]
