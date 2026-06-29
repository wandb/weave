"""Provider adapters for the Weave Conversation SDK.

These modules convert provider-specific wire formats (OpenAI Responses,
Anthropic Messages, etc.) into the provider-agnostic types defined in
``weave.conversation.types``. Each adapter is a leaf module — it imports
types but is not imported by them, so ``types.py`` stays free of
provider knowledge.

The provider SDKs (``openai``, ``anthropic``) are only imported under
``TYPE_CHECKING`` for parameter annotations — adapters can be imported
and called at runtime without those packages installed, as long as the
caller passes a duck-typed object exposing the same attribute shape.
"""
