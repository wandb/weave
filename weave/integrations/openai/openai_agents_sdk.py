from __future__ import annotations

import importlib
from typing import Callable
import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher


_openai_agents_patcher: MultiPatcher | None = None


def openai_agents_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def get_openai_agents_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _openai_agents_patcher
    if _openai_agents_patcher is not None:
        return _openai_agents_patcher

    base = settings.op_settings

    # Naming convention -- module_method_settings
    crew_kickoff_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Crew.kickoff",
            "call_display_name": base.call_display_name,
            "postprocess_inputs": ,
        }
    )

    agent_execute_task_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Agent.execute_task",
            "call_display_name": base.call_display_name
            or default_call_display_name_execute_task,
            "postprocess_inputs": crewai_postprocess_inputs,
        }
    )

    patchers = [
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Crew.kickoff",
            crewai_wrapper(crew_kickoff_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Agent.execute_task",
            crewai_wrapper(agent_execute_task_settings),
        ),
    ]

    _openai_agents_patcher = MultiPatcher(patchers)

    return _openai_agents_patcher
