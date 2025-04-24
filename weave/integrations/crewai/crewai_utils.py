import warnings
from typing import Any

from weave.trace.serialization.serialize import dictify, stringify
from weave.trace.weave_client import Call

EXCLUDE_TASK_ATTRS = {"agent": True}

EXCLUDE_AGENT_ATTRS = {
    "crew": True,
}


def safe_serialize_crewai_agent(obj: Any) -> dict[str, Any]:
    # Ensure obj is a pydantic BaseModel
    if not hasattr(obj, "model_dump"):
        return {"type": "Agent", "error": "Not a valid Pydantic model"}

    result = {
        "type": "Agent",
    }

    # Core identity attributes. We want to surface these first.
    core_attributes = ["role", "goal", "backstory", "id"]
    for attr in core_attributes:
        if hasattr(obj, attr):
            value = getattr(obj, attr)
            if attr == "id" and value is not None:
                result[attr] = stringify(value)
            elif value is not None:
                result[attr] = value

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        attr_dict = obj.model_dump(
            exclude=EXCLUDE_AGENT_ATTRS,
            exclude_none=True,
        )

    for attr, value in attr_dict.items():
        result[attr] = stringify(value)

    return result


def safe_serialize_crewai_task(obj: Any) -> dict[str, Any]:
    if not hasattr(obj, "model_dump"):
        return {"type": "Task", "error": "Not a valid Pydantic model"}

    result = {
        "type": "Task",
    }

    # Core identity attributes. We want to surface these first.
    core_attributes = ["name", "description", "expected_output", "id"]
    for attr in core_attributes:
        if hasattr(obj, attr):
            value = getattr(obj, attr)
            if attr == "id" and value is not None:
                result[attr] = stringify(value)
            elif value is not None:
                result[attr] = value

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        attr_dict = obj.model_dump(
            exclude=EXCLUDE_TASK_ATTRS,
            exclude_none=True,
        )

    for attr, value in attr_dict.items():
        if attr.startswith("_") or value == "":
            continue
        else:
            result[attr] = stringify(value)

    return result


def safe_serialize_crewai_object(obj: Any) -> Any:
    """Safely serialize CrewAI objects to prevent recursion."""
    # Return primitive types directly
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # Everything else is serialized as a dict
    if hasattr(obj, "__class__"):
        if obj.__class__.__name__ == "Agent":
            return safe_serialize_crewai_agent(obj)
        elif obj.__class__.__name__ == "Task":
            return safe_serialize_crewai_task(obj)
        else:
            return dictify(obj)


def crewai_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Process CrewAI inputs to prevent recursion."""
    return {k: safe_serialize_crewai_object(v) for k, v in inputs.items()}


def crew_kickoff_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Postprocess the inputs to the Crew.kickoff method.

    The method has a self which should be an instance of `Crew` which is a pydantic model.
    The method also has an inputs which is a dict or list[dict] of arguments to pass to the `kickoff` method.
    """
    results = {}
    for k, v in inputs.items():
        if k == "self":
            if hasattr(v, "model_dump"):
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning)
                    crew_dict = v.model_dump()
                    if isinstance(crew_dict, dict):
                        results["self"] = {
                            k2: v2
                            for k2, v2 in crew_dict.items()
                            if v2 is not None
                            and not (isinstance(v2, list) and len(v2) == 0)
                        }
                    else:
                        results["self"] = crew_dict
        if k == "inputs":
            results["inputs"] = dictify(v)

    return results


def default_call_display_name_execute_task(call: Call) -> str:
    role = call.inputs["self"].get("role", "").strip()
    return f"crewai.Agent.execute_task - {role}"


def default_call_display_name_execute_sync(call: Call) -> str:
    name = call.inputs["self"].get("name", "").strip()
    name = name.replace("\n", "").strip()
    if name is None or name == "":
        return "crewai.Task.execute_sync"
    return f"crewai.Task.execute_sync - {name}"
