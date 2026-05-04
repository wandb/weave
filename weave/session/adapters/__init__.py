"""Provider adapters for the Weave Session SDK.

These modules convert provider-specific wire formats (OpenAI Responses,
Anthropic Messages, etc.) into the provider-agnostic types defined in
``weave.session.types``. Each adapter is a leaf module — it imports
types but is not imported by them, so ``types.py`` stays free of
provider knowledge.

Adapters are optional: importing ``weave.session.adapters.openai``
requires ``openai`` to be installed; ``weave.session.adapters.anthropic``
requires ``anthropic``. The base ``weave.session`` package has no such
dependency.
"""
