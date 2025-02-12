from __future__ import annotations

import importlib
from typing import Callable

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.weave_client import Call

_crewai_patcher: MultiPatcher | None = None


def crewai_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def default_call_display_name_execute_task(call: Call) -> str:
    role = call.inputs["self"].role.strip()
    return f"crewai.Agent.execute_task - {role}"


def default_call_display_name_execute_sync(call: Call) -> str:
    name = call.inputs["self"].name
    return f"crewai.Task.execute_sync - {name}"


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
    )
    kickoff_for_each_settings = base.model_copy(
        update={"name": base.name or "crewai.Crew.kickoff_for_each"}
    )
    execute_task_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Agent.execute_task",
            "call_display_name": base.call_display_name
            or default_call_display_name_execute_task,
        }
    )
    execute_sync_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Task.execute_sync",
            "call_display_name": base.call_display_name
            or default_call_display_name_execute_sync,
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
            "Crew.kickoff_for_each",
            crewai_wrapper(kickoff_for_each_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Agent.execute_task",
            crewai_wrapper(execute_task_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Task.execute_sync",
            crewai_wrapper(execute_sync_settings),
        ),
    ]

    _crewai_patcher = MultiPatcher(patchers)

    return _crewai_patcher
