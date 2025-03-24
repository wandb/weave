"""
This module provides integrations between Weave and CrewAI, allowing Weave to trace
CrewAI Agents, Tasks, LLM calls, Tools and Flows. For more details on CrewAI, visit:
https://docs.crewai.com/introduction
"""

from __future__ import annotations

import importlib
import warnings
from typing import Any, Callable

import_failed = False

try:
    from crewai.tools.base_tool import BaseTool  # type: ignore
except ImportError:
    import_failed = True

import weave
from weave.integrations.crewai.crewai_utils import (
    crew_kickoff_postprocess_inputs,
    crewai_postprocess_inputs,
    default_call_display_name_execute_sync,
    default_call_display_name_execute_task,
)
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.serialization.serialize import dictify

_crewai_patcher: MultiPatcher | None = None


def crewai_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def flow_decorator_wrapper(op_settings: OpSettings) -> Callable:
    def make_new_value(original_decorator: Callable) -> Callable:
        def wrapped_decorator(*args: Any, **kwargs: Any) -> Callable:
            original_decorated = original_decorator(*args, **kwargs)

            def combined_decorator(fn: Callable) -> Callable:
                # Get the function name for naming the op
                weave_op_name = getattr(fn, "__name__", "unknown_function")

                base_name = op_settings.name or ""
                display_name = (
                    f"{base_name}.{weave_op_name}"
                    if weave_op_name != "unknown_function"
                    else base_name
                )

                op_settings_copy = op_settings.model_copy(
                    update={"call_display_name": display_name}
                )

                # Apply weave.op to the function
                weave_wrapped = weave.op(fn, **op_settings_copy.model_dump())

                # Then apply the original decorator
                return original_decorated(weave_wrapped)

            return combined_decorator

        return wrapped_decorator

    return make_new_value


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

    # Create settings for different Crew methods
    crew_methods = [
        ("crew_kickoff_settings", "kickoff"),
        ("crew_kickoff_async_settings", "kickoff_async"),
        ("crew_kickoff_for_each_settings", "kickoff_for_each"),
        ("kickoff_for_each_async_settings", "kickoff_for_each_async"),
    ]
    crew_settings = {}

    for settings_name, method_name in crew_methods:
        crew_settings[settings_name] = base.model_copy(
            update={
                "name": base.name or f"crewai.Crew.{method_name}",
                "call_display_name": base.call_display_name,
                "postprocess_inputs": crew_kickoff_postprocess_inputs,
            }
        )

    # Create setting for Agent.execute_task
    agent_execute_task_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Agent.execute_task",
            "call_display_name": base.call_display_name
            or default_call_display_name_execute_task,
            "postprocess_inputs": crewai_postprocess_inputs,
        }
    )

    # Create setting for Task.execute_sync
    task_execute_sync_settings = base.model_copy(
        update={
            "name": base.name or "crewai.Task.execute_sync",
            "call_display_name": base.call_display_name
            or default_call_display_name_execute_sync,
            "postprocess_inputs": crewai_postprocess_inputs,
        }
    )

    # Create setting for LLM.call
    llm_call_settings = base.model_copy(
        update={
            "name": base.name or "crewai.LLM.call",
            "call_display_name": base.call_display_name,
        }
    )

    # Create setting for CrewAI Flows
    flow_settings = {}

    flow_kickoff_methods = [
        ("flow_kickoff_settings", "kickoff"),
        ("flow_kickoff_async_settings", "kickoff_async"),
    ]

    for settings_var, method_name in flow_kickoff_methods:
        flow_settings[settings_var] = base.model_copy(
            update={
                "name": base.name or f"crewai.Flow.{method_name}",
                "call_display_name": base.call_display_name,
                "postprocess_inputs": lambda inputs: dictify(inputs),
                "postprocess_output": lambda output: dictify(output),
            }
        )

    flow_functions = [
        ("start_decorator_settings", "start"),
        ("listen_decorator_settings", "listen"),
        ("router_decorator_settings", "router"),
        ("or_function_settings", "or_"),
        ("and_function_settings", "and_"),
    ]

    for settings_var, method_name in flow_functions:
        flow_settings[settings_var] = base.model_copy(
            update={
                "name": base.name or f"crewai.flow.flow.{method_name}",
                "call_display_name": base.call_display_name or f"flow.{method_name}",
            }
        )

    # CrewAI Tools
    tools_settings = {}
    with warnings.catch_warnings():
        old_showwarning = warnings.showwarning
        warnings.showwarning = lambda *args, **kwargs: None
        try:
            crewai_tools_module = importlib.import_module("crewai_tools")
            crewai_tools = dir(crewai_tools_module)
            crewai_tools = [tool for tool in crewai_tools if "Tool" in tool]

            for tool in crewai_tools:
                try:
                    tool_class = getattr(crewai_tools_module, tool)
                    if issubclass(tool_class, BaseTool):
                        tools_settings[tool] = base.model_copy(
                            update={
                                "name": base.name or f"crewai_tools.{tool}._run",
                                "call_display_name": base.call_display_name
                                or f"{tool}._run",
                            }
                        )
                    else:
                        continue
                except (AttributeError, ImportError):
                    continue
        except ImportError:
            # if crewai_tools is not installed, we don't want to raise an error
            pass
        finally:
            # Restore the original showwarning function
            warnings.showwarning = old_showwarning

    crew_patchers = []
    for settings_name, method_name in crew_methods:
        crew_patchers.append(
            SymbolPatcher(
                lambda: importlib.import_module("crewai"),
                f"Crew.{method_name}",
                crewai_wrapper(crew_settings[settings_name]),
            )
        )

    flow_patchers = []
    for settings_var, method_name in flow_kickoff_methods:
        flow_patchers.append(
            SymbolPatcher(
                lambda: importlib.import_module("crewai"),
                f"Flow.{method_name}",
                crewai_wrapper(flow_settings[settings_var]),
            )
        )

    for settings_var, method_name in flow_functions:
        flow_patchers.append(
            SymbolPatcher(
                lambda: importlib.import_module("crewai.flow.flow"),
                f"{method_name}",
                flow_decorator_wrapper(flow_settings[settings_var]),
            )
        )

    tools_patchers = []
    for tool_name, tool_settings in tools_settings.items():
        tools_patchers.append(
            SymbolPatcher(
                lambda: importlib.import_module("crewai_tools"),
                f"{tool_name}._run",
                crewai_wrapper(tool_settings),
            )
        )

    patchers = [
        *crew_patchers,
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
        *flow_patchers,
        *tools_patchers,
    ]

    _crewai_patcher = MultiPatcher(patchers)

    return _crewai_patcher
