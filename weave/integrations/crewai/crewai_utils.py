import copy
import warnings
from typing import Any

from weave.trace.weave_client import Call


def safe_serialize_crewai_agent(obj: Any) -> dict[str, Any]:
    # Ensure obj is a pydantic BaseModel
    if not hasattr(obj, "model_dump"):
        return {"type": "Agent", "error": "Not a valid Pydantic model"}

    result = {
        "type": "Agent",
    }

    # Core identity attributes
    core_attributes = ["role", "goal", "backstory", "id"]
    for attr in core_attributes:
        if hasattr(obj, attr):
            value = getattr(obj, attr)
            if attr == "id" and value is not None:
                result[attr] = str(value)
            elif value is not None:
                result[attr] = value

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        attr_dict = obj.model_dump()

    for attr, value in attr_dict.items():
        if value is None:
            continue
        if attr == "crew":
            continue

        if attr == "i18n":
            if value.get("prompt_file", None):
                result[f"{attr}.prompt_file"] = str(value.get("prompt_file"))
        else:
            try:
                result[attr] = str(value)
            except Exception as e:
                result[attr] = f"Unable to serialize {attr}: {e}"

    return result


def safe_serialize_crewai_task(obj: Any) -> dict[str, Any]:
    if not hasattr(obj, "model_dump"):
        return {"type": "Task", "error": "Not a valid Pydantic model"}

    result = {
        "type": "Task",
    }

    # Core identity attributes
    core_attributes = ["name", "description", "expected_output", "id"]
    for attr in core_attributes:
        if hasattr(obj, attr):
            value = getattr(obj, attr)
            if attr == "id" and value is not None:
                result[attr] = str(value)
            elif value is not None:
                result[attr] = value

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        attr_dict = obj.model_dump()

    for attr, value in attr_dict.items():
        if attr.startswith("_") or value is None or value == "":
            continue
        if attr == "agent" and isinstance(value, dict):
            result[f"{attr}.role"] = value.get("role", "")
        else:
            try:
                result[attr] = str(value)
            except Exception as e:
                result[attr] = f"Unable to serialize {attr}: {e}"

    return result


def safe_serialize_crewai_object(obj: Any) -> Any:
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


def crewai_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Process CrewAI inputs to prevent recursion."""
    return {k: safe_serialize_crewai_object(v) for k, v in inputs.items()}


def crew_kickoff_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    results = {}
    for k, v in inputs.items():
        if k == "self":
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning)
                results["self"] = v.model_dump()
            for k2, v2 in copy.deepcopy(results["self"]).items():
                if v2 is None:
                    results["self"].pop(k2)
                if isinstance(v2, list) and len(v2) == 0:
                    results["self"].pop(k2)
        if k == "inputs":
            if isinstance(v, dict):
                results["inputs"] = {
                    k: safe_serialize_crewai_object(v) for k, v in v.items()
                }
            elif isinstance(v, list):
                results["inputs"] = [
                    {k: safe_serialize_crewai_object(v) for k, v in item.items()}
                    for item in v
                ]
            else:
                results["inputs"] = v

    return results


def default_call_display_name_execute_task(call: Call) -> str:
    role = call.inputs["self"].get("role", "").strip()
    return f"crewai.Agent.execute_task - {role}"


def default_call_display_name_execute_sync(call: Call) -> str:
    name = call.inputs["self"].name
    return f"crewai.Task.execute_sync - {name}"
