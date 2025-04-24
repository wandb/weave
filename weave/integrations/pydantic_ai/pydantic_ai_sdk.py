from typing import Callable, Any
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
import importlib
from functools import wraps

from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.integrations.pydantic_ai.utils import PydanticAISpanExporter
from weave.trace.autopatch import IntegrationSettings

_pydantic_ai_patcher: MultiPatcher | None = None


def get_pydantic_ai_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    """
    Get a patcher for PydanticAI integration.

    Args:
        settings: Optional integration settings to configure the patcher.
            If None, default settings will be used.

    Returns:
        A patcher that can be used to patch and unpatch the PydanticAI integration.
    """
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _pydantic_ai_patcher
    if _pydantic_ai_patcher is not None:
        return _pydantic_ai_patcher

    # Create a tracer provider and span processor for PydanticAI
    tracer_provider = trace_sdk.TracerProvider()
    span_processor = SimpleSpanProcessor(PydanticAISpanExporter())
    tracer_provider.add_span_processor(span_processor)

    # Create a wrapper function for Agent.__init__
    def agent_init_wrapper(original_init: Callable) -> Callable:
        @wraps(original_init)
        def wrapped_init(self: Any, *args: Any, **kwargs: Any) -> None:
            # Check if instrument is already set in kwargs
            if "instrument" not in kwargs or kwargs["instrument"] is None:
                # Create instrumentation settings using our tracer provider
                from pydantic_ai.agent import InstrumentationSettings

                instrumentation_settings = InstrumentationSettings(
                    tracer_provider=tracer_provider,
                    event_mode="attributes",
                )
                kwargs["instrument"] = instrumentation_settings

            # Call the original __init__ method
            original_init(self, *args, **kwargs)

        return wrapped_init

    # Create a wrapper function for Agent.instrument_all
    def agent_instrument_all_wrapper(original_method: Callable) -> Callable:
        @wraps(original_method)
        def wrapped_instrument_all(instrument=True) -> None:
            # If instrument is True (default), replace it with our instrumentation settings
            if instrument is True:
                from pydantic_ai.agent import InstrumentationSettings

                instrument = InstrumentationSettings(
                    tracer_provider=tracer_provider,
                    event_mode="attributes",
                )

            # Call the original method
            original_method(instrument)

        return wrapped_instrument_all

    # Create patchers for the Agent class
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
