"""
PydanticAI integration patcher for Weave tracing.

This module provides a patcher for the PydanticAI Agent class, enabling automatic
instrumentation and OpenTelemetry tracing for PydanticAI calls. The patcher injects
Weave's tracer provider and span exporter, ensuring that all agent runs and instrumented
calls are traced and exported in a way compatible with Weave's trace server.
"""

import importlib
from functools import wraps
from typing import Any, Callable

from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.integrations.pydantic_ai.utils import PydanticAISpanExporter
from weave.trace.autopatch import IntegrationSettings

_pydantic_ai_patcher: MultiPatcher | None = None


def get_pydantic_ai_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    """
    Get a patcher for PydanticAI integration.

    This function returns a patcher that instruments the PydanticAI Agent class
    to use Weave's OpenTelemetry tracer provider and span exporter. If integration
    is disabled in the settings, a NoOpPatcher is returned.

    Args:
        settings: Optional integration settings to configure the patcher.
            If None, default settings will be used.

    Returns:
        MultiPatcher or NoOpPatcher: A patcher that can be used to patch and unpatch
        the PydanticAI integration.
    """
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _pydantic_ai_patcher
    if _pydantic_ai_patcher is not None:
        return _pydantic_ai_patcher

    tracer_provider = trace_sdk.TracerProvider()
    span_processor = SimpleSpanProcessor(PydanticAISpanExporter())
    tracer_provider.add_span_processor(span_processor)

    def agent_init_wrapper(original_init: Callable[..., None]) -> Callable[..., None]:
        """
        Wrap the Agent.__init__ method to inject Weave's instrumentation settings.

        Args:
            original_init: The original __init__ method of the Agent class.

        Returns:
            Callable: The wrapped __init__ method.
        """

        @wraps(original_init)
        def wrapped_init(self: Any, *args: Any, **kwargs: Any) -> None:
            # Only inject instrumentation if not already provided
            if "instrument" not in kwargs or kwargs["instrument"] is None:
                from pydantic_ai.agent import InstrumentationSettings

                instrumentation_settings = InstrumentationSettings(
                    tracer_provider=tracer_provider,
                    event_mode="attributes",
                )
                kwargs["instrument"] = instrumentation_settings
            original_init(self, *args, **kwargs)

        return wrapped_init

    def agent_instrument_all_wrapper(
        original_method: Callable[..., None],
    ) -> Callable[..., None]:
        """
        Wrap the Agent.instrument_all method to inject Weave's instrumentation settings.

        Args:
            original_method: The original instrument_all method of the Agent class.

        Returns:
            Callable: The wrapped instrument_all method.
        """

        @wraps(original_method)
        def wrapped_instrument_all(instrument: Any = True) -> None:
            # If instrument is True (default), replace it with our instrumentation settings
            if instrument is True:
                from pydantic_ai.agent import InstrumentationSettings

                instrument = InstrumentationSettings(
                    tracer_provider=tracer_provider,
                    event_mode="attributes",
                )
            original_method(instrument)

        return wrapped_instrument_all

    # Patch both __init__ and instrument_all of the Agent class
    _pydantic_ai_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("pydantic_ai").Agent,
                "__init__",
                agent_init_wrapper,
            ),
            SymbolPatcher(
                lambda: importlib.import_module("pydantic_ai").Agent,
                "instrument_all",
                agent_instrument_all_wrapper,
            ),
        ]
    )

    return _pydantic_ai_patcher
