"""Adapters from Anthropic's wire format to the Weave Conversation SDK types.

Use these when manually instrumenting calls to ``client.messages.create``
(the autopatched Anthropic integration handles conversion automatically).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from weave.conversation.types import Usage

if TYPE_CHECKING:
    from anthropic.types import Message as AnthropicMessage

__all__ = ["usage_from_anthropic"]


def usage_from_anthropic(message: AnthropicMessage) -> Usage:
    """Extract usage from an Anthropic Messages API ``Message``.

    Anthropic types the cache fields as ``Optional[int]``; ``None`` is
    equivalent to zero for our purposes.
    """
    usage = message.usage
    return Usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
        cache_read_input_tokens=usage.cache_read_input_tokens or 0,
    )
