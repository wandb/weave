from __future__ import annotations

import importlib
from typing import Callable

import_failed = False

try:
    from crewai.tools.base_tool import BaseTool  # type: ignore
except ImportError:
    import_failed = True

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher

from weave.integrations.crewai.crewai_utils import (
    crewai_postprocess_inputs,
    crew_kickoff_postprocess_inputs,
    default_call_display_name_execute_task,
)


_crewai_patcher: MultiPatcher | None = None


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

    # Naming convention -- module_method_settings
    crew_kickoff_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Crew.kickoff",
            "call_display_name": base.call_display_name,
            "postprocess_inputs": crew_kickoff_postprocess_inputs,
        }
    )

    crew_kickoff_for_each_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Crew.kickoff_for_each",
            "call_display_name": base.call_display_name,
            "postprocess_inputs": crew_kickoff_postprocess_inputs,
        }
    )

    # TODOs (ayulockin): kickoff_async and kickoff_for_each_async
    # TODO (ayulockin): replay?

    agent_execute_task_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Agent.execute_task",
            "call_display_name": base.call_display_name
            or default_call_display_name_execute_task,
            "postprocess_inputs": crewai_postprocess_inputs,
        }
    )

    llm_call_settings = base.model_copy(
        update={
            "name": base.name or "crewai.LLM.call",
            "call_display_name": base.call_display_name,
        }
    )

    task_execute_sync_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Task.execute_sync",
            "call_display_name": base.call_display_name,
            "postprocess_inputs": crewai_postprocess_inputs,
        }
    )

    flow_kickoff_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Flow.kickoff",
            "call_display_name": base.call_display_name,
            # "postprocess_inputs": crewai_postprocess_inputs,
        }
    )

    tools_settings = {}
    crewai_tools = dir(importlib.import_module("crewai_tools"))
    crewai_tools = [tool for tool in crewai_tools if "Tool" in tool]

    for tool in crewai_tools:
        try:
            tool_class = getattr(importlib.import_module("crewai_tools"), tool)
            if issubclass(tool_class, BaseTool):
                tools_settings[tool] = base.model_copy(
                    update={
                        "name": base.name or f"crewai_tools.{tool}._run",
                        "call_display_name": base.call_display_name or f"{tool}._run",
                    }
                )
            else:
                continue
        except (AttributeError, ImportError):
            continue

    patchers = [
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Crew.kickoff",
            crewai_wrapper(crew_kickoff_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Crew.kickoff_for_each",
            crewai_wrapper(crew_kickoff_for_each_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Agent.execute_task",
            crewai_wrapper(agent_execute_task_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "LLM.call",
            crewai_wrapper(llm_call_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Task.execute_sync",
            crewai_wrapper(task_execute_sync_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("crewai"),
            "Flow.kickoff",
            crewai_wrapper(flow_kickoff_settings),
        ),
    ]

    for tool_name, tool_settings in tools_settings.items():
        patchers.append(
            SymbolPatcher(
                lambda: importlib.import_module("crewai_tools"),
                f"{tool_name}._run",
                crewai_wrapper(tool_settings),
            )
        )

    _crewai_patcher = MultiPatcher(patchers)

    return _crewai_patcher
