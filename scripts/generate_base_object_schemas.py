import json
from pathlib import Path

from pydantic import create_model

from weave.shared.interface.builtin_object_classes.builtin_object_registry import (
    BUILTIN_OBJECT_REGISTRY,
)

REPO_ROOT = Path(__file__).parent.parent
FILENAME = "generated_builtin_object_class_schemas.json"

# Canonical location, next to the registry the schema is generated from.
OUTPUT_DIR = (
    REPO_ROOT
    / "weave"
    / "shared"
    / "interface"
    / "builtin_object_classes"
    / "generated"
)
OUTPUT_PATH = OUTPUT_DIR / FILENAME

# Legacy location. The frontend schema generator in wandb/core still reads the
# file from here. Drop this copy once core reads the canonical path.
LEGACY_OUTPUT_DIR = (
    REPO_ROOT
    / "weave"
    / "trace_server"
    / "interface"
    / "builtin_object_classes"
    / "generated"
)
LEGACY_OUTPUT_PATH = LEGACY_OUTPUT_DIR / FILENAME

OUTPUT_PATHS = (OUTPUT_PATH, LEGACY_OUTPUT_PATH)


def generate_schemas() -> None:
    """Generate JSON schemas for all registered base objects in BUILTIN_OBJECT_REGISTRY.
    Creates a top-level schema that includes all registered objects and writes it
    to 'generated_builtin_object_class_schemas.json' in every output location.
    """
    # Dynamically create a parent model with all registered objects as properties
    CompositeModel = create_model(  # noqa: N806
        "CompositeBaseObject",
        **{name: (cls, ...) for name, cls in BUILTIN_OBJECT_REGISTRY.items()},
    )

    # Generate the schema using the composite model
    top_level_schema = CompositeModel.model_json_schema(mode="validation")
    serialized = json.dumps(top_level_schema, indent=2)

    print(f"Generated schema for {len(BUILTIN_OBJECT_REGISTRY)} objects")
    for output_path in OUTPUT_PATHS:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized)
        print(f"Wrote schema to {output_path.absolute()}")


if __name__ == "__main__":
    generate_schemas()
