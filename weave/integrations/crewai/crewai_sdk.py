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


def safe_serialize_crewai_agent(obj):
    result = {
        "type": "Agent",
    }

    # Core identity attributes
    if hasattr(obj, "id"):
        result["id"] = str(obj.id)
    if hasattr(obj, "role"):
        result["role"] = obj.role
    if hasattr(obj, "goal"):
        result["goal"] = obj.goal
    if hasattr(obj, "backstory"):
        result["backstory"] = obj.backstory

    # check if obj has a __dict__ attribute
    if hasattr(obj, "__dict__"):
        attributes = vars(obj)
        for attr, value in attributes.items():
            if not attr.startswith("_"):
                # We don't want to populate the UI with a lot of None values.
                if value is None:
                    continue
                # This is a reference to the crew object itself.
                if attr == "crew":
                    continue
                # Handle international prompt files.
                # https://github.com/crewAIInc/crewAI/blob/00eede0d5d7b9ea591d939689e8e05f89f9d975d/src/crewai/utilities/i18n.py#L9
                if attr == "i18n":
                    if hasattr(value, "prompt_file"):
                        if value.prompt_file is not None:
                            result[attr] = str(value.prompt_file)
                result[attr] = str(value)  # TODO: handle more gracefully.

    return result


def safe_serialize_crewai_object(obj):
    """Safely serialize CrewAI objects to prevent recursion."""
    # Return primitive types directly
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj        

    # Everything else is serialized as a dict
    if hasattr(obj, "__class__") and obj.__class__.__module__.startswith("crewai"):
        if obj.__class__.__name__ == "Agent":
            return safe_serialize_crewai_agent(obj)
        else:
            print("Inside safe_serialize_crewai_object else")
            print("obj: ", obj)
            print("--------------------------------")
            # Return a simplified representation
            result = {
                "type": obj.__class__.__name__,
            }

            # Add important attributes without following references
            safe_attrs = ["name", "description", "role"]
            for attr in safe_attrs:
                if hasattr(obj, attr):
                    result[attr] = getattr(obj, attr)
                    
            return result
    return obj  # Return unchanged if not a CrewAI object


def crewai_postprocess_inputs(inputs):
    """Process CrewAI inputs to prevent recursion."""
    return {k: safe_serialize_crewai_object(v) for k, v in inputs.items()}


def default_call_display_name_execute_task(call: Call) -> str:
    role = call.inputs["self"].get("role", "").strip()
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
    ]

    _crewai_patcher = MultiPatcher(patchers)

    return _crewai_patcher
