from __future__ import annotations

from weave.integrations._llm_provider import Endpoint, LLMProviderPatcher
from weave.integrations.patcher import MultiPatcher, NoOpPatcher
from weave.trace.autopatch import IntegrationSettings

# Cerebras' async client method does not pass ``inspect.iscoroutinefunction``,
# so the async endpoint needs the async passthrough wrapper (async_passthrough).
_CEREBRAS_ENDPOINTS = [
    Endpoint(
        module="cerebras.cloud.sdk.resources.chat",
        symbol="CompletionsResource.create",
        op_name="cerebras.chat.completions.create",
    ),
    Endpoint(
        module="cerebras.cloud.sdk.resources.chat",
        symbol="AsyncCompletionsResource.create",
        op_name="cerebras.chat.completions.create",
        async_passthrough=True,
    ),
]

_cerebras_provider = LLMProviderPatcher(_CEREBRAS_ENDPOINTS)


def get_cerebras_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    return _cerebras_provider.get(settings)
