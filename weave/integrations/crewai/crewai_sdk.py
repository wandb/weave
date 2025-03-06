from __future__ import annotations

import importlib
from typing import Callable

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
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
    print("base settings: ", base)

    kickoff_settings = base.model_copy(
        update={"name": base.name or "crewai.Crew.kickoff"}
    )
    print("kickoff settings: ", kickoff_settings)

    patchers = [
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Crew.kickoff",
            crewai_wrapper(kickoff_settings),
        ),
    ]
    print("patchers: ", patchers)

    _crewai_patcher = MultiPatcher(patchers)

    return _crewai_patcher
