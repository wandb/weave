# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["ContainsOperation"]


class ContainsOperation(TypedDict, total=False):
    """Case-insensitive substring match.

    Not part of MongoDB. Weave-specific addition.

    Example:
        ```
        {"$contains": {"input": {"$getField": "display_name"}, "substr": {"$literal": "llm"}, "case_insensitive": true}}
        ```
    """

    contains: Required[Annotated["ContainsSpec", PropertyInfo(alias="$contains")]]
    """Specification for the `$contains` operation.

    - `input`: The string to search.
    - `substr`: The substring to search for.
    - `case_insensitive`: If true, match is case-insensitive.
    """


from .contains_spec import ContainsSpec
