import json
from pathlib import Path

from weave.trace_server.interface.base_object_classes.base_object_registry import (
    REGISTRY,
    CompositeBaseObject,
)

OUTPUT_PATH = Path(__file__).parent / "generated_base_object_class_schemas.json"


def generate_schemas() -> None:
    """
    Generate JSON schemas for all registered base objects in REGISTRY.
    Creates a top-level union type of all registered objects and writes the schemas
    to a file named 'base_object_schemas.json'.
    """
    top_level_schema = CompositeBaseObject.model_json_schema(mode="validation")

    # Write schemas to file
    with OUTPUT_PATH.open("w") as f:
        json.dump(top_level_schema, f, indent=2)

    print(f"Generated union schema for {len(REGISTRY)} objects")
    print(f"Wrote schema to {OUTPUT_PATH.absolute()}")


if __name__ == "__main__":
    generate_schemas()
