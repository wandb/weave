from __future__ import annotations

import importlib
from typing import Callable

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher

from weave.integrations.crewai.crewai_utils import (
    safe_serialize_crewai_agent,
    safe_serialize_crewai_task,
    default_call_display_name_execute_task,
    default_call_display_name_execute_sync,
)

_crewai_patcher: MultiPatcher | None = None


def safe_serialize_crewai_object(obj):
    """Safely serialize CrewAI objects to prevent recursion."""
    # Return primitive types directly
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj        

    # Everything else is serialized as a dict
    if hasattr(obj, "__class__") and obj.__class__.__module__.startswith("crewai"):
        if obj.__class__.__name__ == "Agent":
            return safe_serialize_crewai_agent(obj)
        elif obj.__class__.__name__ == "Task":
            return safe_serialize_crewai_task(obj)
        else:
            return obj


def crewai_postprocess_inputs(inputs):
    """Process CrewAI inputs to prevent recursion."""
    return {k: safe_serialize_crewai_object(v) for k, v in inputs.items()}


def crewai_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def get_crewai_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _crewai_patcher
    if _crewai_patcher is not None:
        return _crewai_patcher

    base = settings.op_settings

    kickoff_settings = base.model_copy(
        update={"name": base.name or "crewai.Crew.kickoff"}
    )  # TODO: improve the inputs to the kickoff method.

    agent_execute_task_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Agent.execute_task",
            "call_display_name": base.call_display_name
            or default_call_display_name_execute_task,
            "postprocess_inputs": crewai_postprocess_inputs,
            # We don't need to postprocess outputs because the output is always a string.
        }
    )

    llm_settings = base.model_copy(
        update={
            "name": base.name or "crewai.LLM.call",
            # "call_display_name": base.call_display_name
        }
    )

    patchers = [
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Crew.kickoff",
            crewai_wrapper(kickoff_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Agent.execute_task",
            crewai_wrapper(agent_execute_task_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "LLM.call",
            crewai_wrapper(llm_settings),
        ),
    ]

    _crewai_patcher = MultiPatcher(patchers)

    return _crewai_patcher
