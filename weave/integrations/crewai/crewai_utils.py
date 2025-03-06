import warnings

from weave.trace.weave_client import Call


def safe_serialize_crewai_agent(obj):
    # Ensure obj is a pydantic BaseModel
    assert hasattr(obj, "model_dump"), "Expected a Pydantic BaseModel with model_dump method"

    result = {
        "type": "Agent",
    }

    # Core identity attributes
    if hasattr(obj, "role"):
        result["role"] = obj.role
    if hasattr(obj, "goal"):
        result["goal"] = obj.goal
    if hasattr(obj, "backstory"):
        result["backstory"] = obj.backstory
    if hasattr(obj, "id"):
        result["id"] = str(obj.id)

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

        result[attr] = str(value)  # TODO: handle more gracefully.

    return result


def safe_serialize_crewai_task(obj):
    result = {
        "type": "Task",
    }

    # Core identity attributes
    if hasattr(obj, "name"):
        result["name"] = obj.name
    if hasattr(obj, "description"):
        result["description"] = obj.description
    if hasattr(obj, "expected_output"):
        result["expected_output"] = obj.expected_output
    if hasattr(obj, "id"):
        result["id"] = str(obj.id)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        attr_dict = obj.model_dump()

    for attr, value in attr_dict.items():
        if attr.startswith("_"):
            continue
        if value is None:
            continue
        if value == "":
            continue
        if attr == "agent":
            result[f"{attr}.role"] = value.get("role", "")

        result[attr] = str(value)

    return result


def default_call_display_name_execute_task(call: Call) -> str:
    role = call.inputs["self"].get("role", "").strip()
    return f"crewai.Agent.execute_task - {role}"


def default_call_display_name_execute_sync(call: Call) -> str:
    name = call.inputs["self"].name
    return f"crewai.Task.execute_sync - {name}"
