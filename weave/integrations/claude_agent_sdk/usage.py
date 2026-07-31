"""Usage normalization shared by Claude Agent SDK tracing variants."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def total_input_tokens(usage: Mapping[str, Any] | None) -> int:
    """Return Weave's gross prompt count for an Anthropic usage payload.

    Anthropic reports fresh input tokens separately from cache-read and
    cache-creation tokens. Weave records those cache counts as subsets of the
    full prompt, so its input token count must include all three values.
    """
    raw = usage or {}
    return (
        int(raw.get("input_tokens", 0) or 0)
        + int(raw.get("cache_read_input_tokens", 0) or 0)
        + int(raw.get("cache_creation_input_tokens", 0) or 0)
    )
