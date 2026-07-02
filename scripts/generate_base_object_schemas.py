import json
from pathlib import Path

from pydantic import create_model

from weave.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    BUILTIN_OBJECT_REGISTRY,
)

OUTPUT_DIR = (
    Path(__file__).parent.parent
    / "weave"
    / "trace_server"
    / "interface"
    / "builtin_object_classes"
    / "generated"
)
OUTPUT_PATH = OUTPUT_DIR / "generated_builtin_object_class_schemas.json"

JSONValue = dict[str, "JSONValue"] | list["JSONValue"] | str | int | float | bool | None


def build_schema() -> dict[str, JSONValue]:
    """Build the canonical JSON schema for all registered builtin object classes."""
    CompositeModel = create_model(  # noqa: N806
        "CompositeBaseObject",
        **{name: (cls, ...) for name, cls in BUILTIN_OBJECT_REGISTRY.items()},
    )
    schema = CompositeModel.model_json_schema(mode="validation")
    _canonicalize_self_refs(schema, set(schema.get("$defs", {})))
    return schema


def generate_schemas() -> None:
    """Generate and write JSON schemas for all registered builtin object classes."""
    schema = build_schema()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w") as f:
        json.dump(schema, f, indent=2)
    print(f"Generated schema for {len(BUILTIN_OBJECT_REGISTRY)} objects")
    print(f"Wrote schema to {OUTPUT_PATH.absolute()}")


def _canonicalize_self_refs(node: JSONValue, defs: set[str]) -> None:
    """Rewrite pydantic's degenerate self-ref union members ({"title": X}) to stable {"$ref": "#/$defs/X"}."""
    if isinstance(node, dict):
        members = node.get("anyOf")
        if isinstance(members, list):
            for i, member in enumerate(members):
                if (
                    isinstance(member, dict)
                    and member.keys() == {"title"}
                    and member["title"] in defs
                ):
                    members[i] = {"$ref": f"#/$defs/{member['title']}"}
        for value in node.values():
            _canonicalize_self_refs(value, defs)
    elif isinstance(node, list):
        for value in node:
            _canonicalize_self_refs(value, defs)


if __name__ == "__main__":
    generate_schemas()
