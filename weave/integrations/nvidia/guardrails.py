from typing import Any, Callable
import importlib
import asyncio

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.op_extensions.accumulator import add_accumulator

_guardrails_patcher: MultiPatcher | None = None

def create_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: None,  # No streaming for guardrails
            should_accumulate=lambda inputs: False,
        )
    return wrapper

def create_async_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)

        async def make_accumulator(inputs: Any) -> Any:
            return None

        async def should_accumulate(inputs: Any) -> bool:
            return False

        return add_accumulator(
            op,  # type: ignore
            make_accumulator=make_accumulator,
            should_accumulate=should_accumulate,
        )
    return wrapper

def get_nvidia_guardrails_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()
    
    if not settings.enabled:
        return NoOpPatcher()
        
    global _guardrails_patcher
    if _guardrails_patcher is not None:
        return _guardrails_patcher
        
    base = settings.op_settings
    
    # Define settings for LLMRails.generate and generate_async
    generate_settings = base.model_copy(
        update={"name": base.name or "nemoguardrails.LLMRails.generate"}
    )
    generate_async_settings = base.model_copy(
        update={"name": base.name or "nemoguardrails.LLMRails.generate_async"}
    )
    
    _guardrails_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("nemoguardrails"),
                "LLMRails.generate", 
                create_wrapper(generate_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("nemoguardrails"),
                "LLMRails.generate_async",
                create_async_wrapper(generate_async_settings),
            ),
        ]
    )
    
    return _guardrails_patcher