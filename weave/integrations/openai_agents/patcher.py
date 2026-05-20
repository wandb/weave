"""Lifecycle patchers for the OpenAI Agents integration.

The patchers install a Weave tracing processor (either the calls-based one
from ``openai_agents.py`` or the OTel-emitting one from ``otel_processor.py``)
into the OpenAI Agents tracing system.

The two variants are intentionally near-identical — only the processor class
they instantiate differs. They're kept as separate classes (rather than a
parameterized base) so each variant's lifecycle stays trivial to read; the
dispatcher in ``weave/integrations/patch.py`` picks which one runs based on
``WEAVE_USE_OTEL_V2``.
"""

from __future__ import annotations

from weave.integrations.openai_agents.openai_agents import WeaveTracingProcessor
from weave.integrations.openai_agents.otel_processor import WeaveOtelTracingProcessor
from weave.integrations.patcher import NoOpPatcher, Patcher
from weave.trace.autopatch import IntegrationSettings

_openai_agents_patcher: OpenAIAgentsPatcher | None = None
_openai_agents_otel_patcher: OpenAIAgentsOtelPatcher | None = None


class OpenAIAgentsPatcher(Patcher):
    """A patcher for OpenAI Agents that manages the lifecycle of a WeaveTracingProcessor.

    Unlike other patchers that modify function behavior, this patcher installs and
    removes a processor from the OpenAI Agents tracing system.
    """

    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings
        self.patched = False
        self.processor: WeaveTracingProcessor | None = None

    def attempt_patch(self) -> bool:
        """Install a WeaveTracingProcessor in the OpenAI Agents tracing system."""
        if self.patched:
            return True

        try:
            from agents.tracing import add_trace_processor

            self.processor = WeaveTracingProcessor()
            add_trace_processor(self.processor)
            self.patched = True
        except Exception:
            self.processor = None
            return False
        else:
            return True

    def undo_patch(self) -> bool:
        # OpenAI Agents doesn't have a way to de-register a processor yet...
        return True


def get_openai_agents_patcher(
    settings: IntegrationSettings | None = None,
) -> OpenAIAgentsPatcher | NoOpPatcher:
    """Get a patcher for OpenAI Agents integration.

    Args:
        settings: Optional integration settings to configure the patcher.
            If None, default settings will be used.

    Returns:
        A patcher that can be used to patch and unpatch the OpenAI Agents integration.
    """
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _openai_agents_patcher  # noqa: PLW0603
    if _openai_agents_patcher is not None:
        return _openai_agents_patcher

    _openai_agents_patcher = OpenAIAgentsPatcher(settings)

    return _openai_agents_patcher


class OpenAIAgentsOtelPatcher(Patcher):
    """Sibling of ``OpenAIAgentsPatcher`` that installs the OTel processor instead.

    Selected by the dispatcher in ``weave/integrations/patch.py`` when
    ``WEAVE_USE_OTEL_V2=true``, or by direct caller via
    ``patch_openai_agents_otel(...)``.
    """

    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings
        self.patched = False
        self.processor: WeaveOtelTracingProcessor | None = None

    def attempt_patch(self) -> bool:
        """Install a WeaveOtelTracingProcessor in the OpenAI Agents tracing system."""
        if self.patched:
            return True

        try:
            from agents.tracing import add_trace_processor

            self.processor = WeaveOtelTracingProcessor()
            add_trace_processor(self.processor)
            self.patched = True
        except Exception:
            self.processor = None
            return False
        else:
            return True

    def undo_patch(self) -> bool:
        # OpenAI Agents doesn't have a way to de-register a processor yet...
        return True


def get_openai_agents_otel_patcher(
    settings: IntegrationSettings | None = None,
) -> OpenAIAgentsOtelPatcher | NoOpPatcher:
    """Get a patcher for the OTel variant of the OpenAI Agents integration.

    Args:
        settings: Optional integration settings to configure the patcher.
            If None, default settings will be used.

    Returns:
        A patcher that installs the OTel tracing processor.
    """
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _openai_agents_otel_patcher  # noqa: PLW0603
    if _openai_agents_otel_patcher is not None:
        return _openai_agents_otel_patcher

    _openai_agents_otel_patcher = OpenAIAgentsOtelPatcher(settings)

    return _openai_agents_otel_patcher
