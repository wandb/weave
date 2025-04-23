import json
from pathlib import Path

from pydantic import create_model

from weave.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    BUILTIN_OBJECT_REGISTRY,
)

OUTPUT_DIR = (
    Path(__file__).parent.parent
    / "trace_server"
    / "interface"
    / "builtin_object_classes"
    / "generated"
)
OUTPUT_PATH = OUTPUT_DIR / "generated_builtin_object_class_schemas.json"


def generate_schemas() -> None:
    """
    Generate JSON schemas for all registered base objects in BUILTIN_OBJECT_REGISTRY.
    Creates a top-level schema that includes all registered objects and writes it
    to 'generated_builtin_object_class_schemas.json'.
    """
    # Dynamically create a parent model with all registered objects as properties
    CompositeModel = create_model(
        "CompositeBaseObject",
        **{name: (cls, ...) for name, cls in BUILTIN_OBJECT_REGISTRY.items()},
    )

    # Generate the schema using the composite model
    top_level_schema = CompositeModel.model_json_schema(mode="validation")

    # make sure the output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write schema to file
    with OUTPUT_PATH.open("w") as f:
        json.dump(top_level_schema, f, indent=2)

    print(f"Generated schema for {len(BUILTIN_OBJECT_REGISTRY)} objects")
    print(f"Wrote schema to {OUTPUT_PATH.absolute()}")


if __name__ == "__main__":
    generate_schemas()
