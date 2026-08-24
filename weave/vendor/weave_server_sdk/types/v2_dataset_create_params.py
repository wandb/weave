# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional
from typing_extensions import Required, TypedDict

__all__ = ["V2DatasetCreateParams"]


class V2DatasetCreateParams(TypedDict, total=False):
    entity: Required[str]

    rows: Required[Iterable[Dict[str, object]]]
    """Dataset rows"""

    description: Optional[str]
    """A description of this dataset"""

    name: Optional[str]
    """The name of this dataset.

    Datasets with the same name will be versioned together.
    """
