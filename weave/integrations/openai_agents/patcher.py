"""Lifecycle patchers for the OpenAI Agents integration.

The patchers install a Weave tracing processor (either the calls-based one
from ``openai_agents.py`` or the OTel-emitting one from ``otel_processor.py``)
into the OpenAI Agents tracing system.

The two variants differ in the processor class they instantiate, and the OTel
variant also installs the tool call id hook that feeds its processor. They're
kept as separate classes (rather than a parameterized base) so each variant's
lifecycle stays trivial to read; the dispatcher in
``weave/integrations/patch.py`` picks which one runs based on
``WEAVE_USE_OTEL_V2``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from agents.tracing import add_trace_processor

from weave.integrations.openai_agents._tool_call_ids import install_tool_call_id_hook
from weave.integrations.openai_agents.openai_agents import WeaveTracingProcessor
from weave.integrations.openai_agents.otel_processor import WeaveOtelTracingProcessor
from weave.integrations.patcher import NoOpPatcher, Patcher
from weave.trace.autopatch import IntegrationSettings

logger = logging.getLogger(__name__)

_openai_agents_patcher: OpenAIAgentsPatcher | None = None
_openai_agents_otel_patcher: OpenAIAgentsOtelPatcher | None = None


def _registered_processors() -> list[Any] | None:
    """Return the current list of installed openai-agents tracing processors.

    The agents SDK doesn't expose a public getter — the only public mutation is
    ``provider.set_processors(list)``, which means we have to read the private
    ``_multi_processor._processors`` tuple to know what's already installed
    (so we don't blow away other integrations' processors during undo_patch).
    Mirrors the same pattern in
    ``opentelemetry.instrumentation.openai_agents_v2``.

    Returns ``None`` if the introspection fails — caller should fall back to a
    no-op uninstall rather than guess at the processor list.
    """
    try:
        from agents.tracing import get_trace_provider

        provider = get_trace_provider()
        multi = provider._multi_processor
        processors = multi._processors
    except Exception:
        return None
    return list(processors)


def _remove_processor(processor: Any) -> bool:
    """Remove a specific processor from the agents tracing pipeline.

    Reads the current processor list, filters ours out, and reinstalls the
    remainder via the public ``set_processors`` API. Then asks our processor
    to shut down so it can flush / release resources. Returns ``True`` on
    success.
    """
    current = _registered_processors()
    if current is None:
        return False
    try:
        from agents.tracing import set_trace_processors
    except Exception:
        return False

    filtered = [p for p in current if p is not processor]
    if len(filtered) == len(current):
        # Processor wasn't installed (or already removed) — still call shutdown
        # so the caller's state is consistent.
        pass
    set_trace_processors(filtered)

    try:
        processor.shutdown()
    except Exception:
        logger.exception("openai_agents processor shutdown raised; continuing")
    return True


class OpenAIAgentsPatcher(Patcher):
    """A patcher for OpenAI Agents that manages the lifecycle of a WeaveTracingProcessor.

    Unlike other patchers that modify function behavior, this patcher installs
    and removes a processor from the OpenAI Agents tracing system.
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
            self.processor = WeaveTracingProcessor()
            add_trace_processor(self.processor)
            self.patched = True
        except Exception:
            self.processor = None
            return False
        else:
            return True

    def undo_patch(self) -> bool:
        """Remove the previously-installed processor from the agents pipeline."""
        if not self.patched or self.processor is None:
            return True
        ok = _remove_processor(self.processor)
        if ok:
            self.processor = None
            self.patched = False
        return ok


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
        self._undo_tool_call_id_hook: Callable[[], None] | None = None

    def attempt_patch(self) -> bool:
        """Install a WeaveOtelTracingProcessor and the tool call id hook that feeds it."""
        if self.patched:
            return True

        try:
            processor = WeaveOtelTracingProcessor()
            self._undo_tool_call_id_hook = install_tool_call_id_hook(
                processor.record_tool_call_id
            )
            add_trace_processor(processor)
            self.processor = processor
            self.patched = True
        except Exception:
            logger.exception("Failed to install the openai_agents OTel processor")
            self._remove_tool_call_id_hook()
            self.processor = None
            return False
        else:
            return True

    def undo_patch(self) -> bool:
        """Remove the previously-installed processor and tool call id hook."""
        if not self.patched or self.processor is None:
            return True
        ok = _remove_processor(self.processor)
        if ok:
            self._remove_tool_call_id_hook()
            self.processor = None
            self.patched = False
        return ok

    def _remove_tool_call_id_hook(self) -> None:
        """Restore `ToolContext.from_agent_context` if this patcher wrapped it."""
        if self._undo_tool_call_id_hook is None:
            return

        self._undo_tool_call_id_hook()
        self._undo_tool_call_id_hook = None


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
