import json
import os

import requests


def get_raw_json():
    response = requests.get("https://trace.wandb.ai/openapi.json")
    # Used for Dev
    # response = requests.get("http://trace_server.wandb.test/openapi.json")
    response.raise_for_status()
    return response.json()


def apply_mapper(raw_json, mapper):
    if isinstance(raw_json, dict):
        return mapper({k: apply_mapper(v, mapper) for k, v in raw_json.items()})
    elif isinstance(raw_json, list):
        return mapper([apply_mapper(v, mapper) for v in raw_json])
    else:
        return mapper(raw_json)


def apply_doc_fixes(raw_json):
    # Fix 1: Remove the nasty recursion caused by the Mongo query expr.
    # Fix 1.a: Change the `Query.expr` field to be an object.
    # This stops a deadly recursion in docs gen.
    expr = (
        raw_json.get("components", {})
        .get("schemas", {})
        .get("Query", {})
        .get("properties", {})
        .get("$expr")
    )
    if expr is not None:
        del expr["anyOf"]
        expr["type"] = "object"

    # Fix 1.b: Remove all the operations:
    remove_keys = [
        k
        for k in raw_json.get("components", {}).get("schemas", {}).keys()
        if k.endswith("Operation")
    ]
    for k in remove_keys:
        del raw_json["components"]["schemas"][k]

    def remove_dependencies_mapper(value):
        if (
            isinstance(value, dict)
            and "$ref" in value
            and any(value["$ref"].endswith(k) for k in remove_keys)
        ):
            return {"type": "object"}
        return value

    raw_json = apply_mapper(raw_json, remove_dependencies_mapper)

    # Fix 2: Fix the `anyOf` fields that are not supported by the docs generator.
    # Specifically, when we have Optional[Any] or Optional[Dict] fields, the generator
    # dies.
    def optional_any_fix_mapper(value):
        if (
            isinstance(value, dict)
            and "anyOf" in value
            and value["anyOf"] == [{}, {"type": "null"}]
        ):
            del value["anyOf"]
            value["type"] = "object"
        return value

    raw_json = apply_mapper(raw_json, optional_any_fix_mapper)

    def optional_dict_fix_mapper(value):
        if (
            isinstance(value, dict)
            and "anyOf" in value
            and value["anyOf"] == [{"type": "object"}, {"type": "null"}]
        ):
            del value["anyOf"]
            value["type"] = "object"
        return value

    raw_json = apply_mapper(raw_json, optional_dict_fix_mapper)

    # Fix 3: Fix anyOf arrays that contain empty objects or problematic combinations
    def empty_object_fix_mapper(value):
        if isinstance(value, dict) and isinstance(value.get("anyOf"), list):
            # Filter out empty objects from anyOf arrays
            filtered_any_of = [item for item in value["anyOf"] if item != {}]
            if len(filtered_any_of) != len(value["anyOf"]):
                if len(filtered_any_of) == 0:
                    # If all items were empty, replace with a single object type
                    del value["anyOf"]
                    value["type"] = "object"
                else:
                    value["anyOf"] = filtered_any_of

            # Also handle the case where we only have object and null types
            # This can cause empty tabs in the docs generator
            if len(value["anyOf"]) == 2:
                types = {
                    item["type"]
                    for item in value["anyOf"]
                    if isinstance(item, dict) and "type" in item
                }

                if types == {"object", "null"}:
                    # Replace with just object type to avoid empty tabs
                    del value["anyOf"]
                    value["type"] = "object"
        return value

    raw_json = apply_mapper(raw_json, empty_object_fix_mapper)

    return raw_json


def set_servers(raw_json):
    """I think technically we should be setting this from the server-side,
    but this is a lower-cost solution for now.
    """
    raw_json["servers"] = [{"url": "https://trace.wandb.ai"}]
    return raw_json


def main():
    raw_json = get_raw_json()
    safe_for_docs_json = apply_doc_fixes(raw_json)
    safe_for_docs_json = set_servers(safe_for_docs_json)
    os.makedirs("./scripts/.cache", exist_ok=True)
    with open("./scripts/.cache/service_api_openapi_docs.json", "w") as f:
        json.dump(safe_for_docs_json, f, indent=2)


if __name__ == "__main__":
    main()
